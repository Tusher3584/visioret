"""Response-time and concurrency measurement for POST /api/predict.

Not part of the pytest suite: it measures a RUNNING deployment over real
HTTP, which is what the performance requirement (NFR1) and midterm test case
T7 are about. Every upload carries one random anonymous session id, so the
test scans can be found and removed afterwards without touching anyone
else's data.

Usage:
    python tests/perf/perf_predict.py https://visioret.eastasia.cloudapp.azure.com

Prints a JSON summary, including the session id used.
"""

import json
import os
import statistics
import sys
import threading
import time
import uuid

import httpx

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SAMPLES = {
    "CNV": "cnv_sample.jpg",
    "DME": "dme_sample.jpg",
    "DRUSEN": "drusen_sample.jpg",
    "NORMAL": "normal_sample.jpg",
}
DATA = {c: open(os.path.join(ROOT, "samples", f), "rb").read() for c, f in SAMPLES.items()}


def one_upload(client, base, session, cls):
    t0 = time.perf_counter()
    r = client.post(
        f"{base}/api/predict",
        files={"file": (SAMPLES[cls], DATA[cls], "image/jpeg")},
        headers={"X-Anon-Session": session},
    )
    elapsed = time.perf_counter() - t0
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    return {
        "expected": cls,
        "status": r.status_code,
        "predicted": body.get("predicted_class"),
        "scan_id": body.get("scan_id"),
        "seconds": round(elapsed, 3),
    }


def pct(values, p):
    s = sorted(values)
    k = max(0, min(len(s) - 1, round(p / 100 * (len(s) - 1))))
    return round(s[k], 3)


def summarise(rows):
    secs = [r["seconds"] for r in rows]
    return {
        "n": len(rows),
        "all_200": all(r["status"] == 200 for r in rows),
        "all_correct": all(r["predicted"] == r["expected"] for r in rows),
        "unique_scan_ids": len({r["scan_id"] for r in rows}) == len(rows),
        "min_s": round(min(secs), 3),
        "median_s": round(statistics.median(secs), 3),
        "p95_s": pct(secs, 95),
        "max_s": round(max(secs), 3),
    }


def main(base):
    session = "perftest-" + uuid.uuid4().hex[:16]
    classes = list(SAMPLES)
    out = {"base_url": base, "session": session}

    with httpx.Client(timeout=120) as client:
        # Health latency with the server idle -- the floor for any request.
        t0 = time.perf_counter()
        client.get(f"{base}/api/health")
        out["health_idle_s"] = round(time.perf_counter() - t0, 3)

        one_upload(client, base, session, "CNV")  # warm-up, not counted

        # 1) Sequential: 12 uploads, one at a time (3 per class).
        seq = [one_upload(client, base, session, classes[i % 4]) for i in range(12)]
        out["sequential"] = summarise(seq)

    # 2) Concurrent: 4 clients upload at the same instant, 3 rounds.
    conc_rows, walls, health_during = [], [], []
    for _ in range(3):
        rows = [None] * 4
        barrier = threading.Barrier(5)

        def worker(i):
            with httpx.Client(timeout=120) as c:
                barrier.wait()
                rows[i] = one_upload(c, base, session, classes[i])

        def health_probe():
            # How long does a trivial request wait while predictions run?
            with httpx.Client(timeout=120) as c:
                barrier.wait()
                time.sleep(0.3)  # land in the middle of the burst
                t = time.perf_counter()
                c.get(f"{base}/api/health")
                health_during.append(round(time.perf_counter() - t, 3))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
        threads.append(threading.Thread(target=health_probe))
        t0 = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        walls.append(round(time.perf_counter() - t0, 3))
        conc_rows.extend(rows)

    out["concurrent"] = summarise(conc_rows)
    out["concurrent"]["wall_clock_per_burst_of_4_s"] = walls
    out["concurrent"]["throughput_req_per_s"] = round(len(conc_rows) / sum(walls), 2)
    out["health_during_burst_s"] = health_during
    out["rows"] = {"sequential": seq, "concurrent": conc_rows}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost")
