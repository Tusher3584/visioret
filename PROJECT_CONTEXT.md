# Visioret — Full Project Context (session handoff)

Read this entire file before doing anything else. It exists so a fresh
session with zero memory of prior conversations can pick up exactly where
things left off, as if it had the full chat history. Originally written
2026-08-20, right after Checkpoint 1 (OOD detection) shipped and was
verified; revised 2026-08-26 during the pre-defense review.

> **How to read this file.** It is a *decision log*, not a specification —
> it deliberately records dead ends and superseded designs alongside the
> current one, because the reasoning behind an abandoned approach is the
> part that gets asked about in a defense. Sections that no longer describe
> the running system are marked **SUPERSEDED** and are followed by what
> replaced them. For a straight statement of what the system does today,
> read `README.md` (setup and usage) or `FEATURES.md` (complete inventory).

---

## 1. What this project is

**Visioret** — explainable AI for retinal OCT (optical coherence tomography)
disease classification. A bachelor's 4th-year final project (SPL3) at the
Institute of Information Technology (IIT), University of Dhaka.

- Student: Rifat Ahmed Tushar, roll 1451
- Supervisor: Dr. Sumon Ahmed
- The user in this chat is the student. They are hands-on, review everything,
  and push back hard when quality isn't there yet — see §7.

**Original proposal scope:** classify OCT B-scans into 4 classes (CNV, DME,
DRUSEN, NORMAL) using ResNet50 transfer learning, explain predictions with
Grad-CAM, serve it through a React + Tailwind frontend backed by FastAPI and
PostgreSQL, trained/evaluated on the Kermany OCT2017 dataset. Docker was
listed as optional.

**This is explicitly NOT meant to look like a first-year-student project.**
The user has said this directly — professionalism and rigor matter, not just
"does it technically work."

---

## 2. Current status (one-liner)

Full stack (model + FastAPI backend + PostgreSQL + React frontend, all
wired together via Docker Compose) is built, tested, and running. A
post-completion review surfaced real gaps and new requirements (see §4);
these are now being worked through one at a time via `TODO.md`.
**Checkpoint 1 (out-of-distribution detection) is done and verified.**
Checkpoint 2 (OCT-specific preprocessing) is next, not yet started.

**Read `TODO.md` right after this file** — it's the authoritative, living
checkpoint list with checkboxes. This document explains the *why* behind
everything; `TODO.md` tracks the *what's left*.

---

## 3. How the project got here (chronological)

### Stage 1 — One-day midterm demo
Built fast: a minimal Streamlit app (`app.py`), `model/inference.py`
(preprocessing, prediction, manual Grad-CAM), `model/train_quick.py` (a
400-image quick fine-tune, head-only). No backend, no database, no frontend
framework — explicitly out of scope for that deadline. Pushed to GitHub at
github.com/Tusher3584/visioret (co-author trailer was removed from the
commit afterward for academic-integrity reasons — the user was firm about
this).

### Stage 2 — "Turn this into the final working product"
The user decided the demo wasn't the deliverable — they wanted the real
system from the original proposal. Planned as 5 phases, each built and
verified in its own sitting:

- **Phase A — full model training.** Trained on the complete ~83k-image
  Kermany OCT2017 dataset (not the 400-image demo subset). Along the way:
  - **Found and fixed a real data-leakage bug in the official dataset
    split**: ~85% of the official `test/` folder's patients also appear in
    the official `train/` folder (verified directly). Fixed by pooling all
    of train+val+test (84,484 images, 5,718 unique patients) and re-splitting
    by **patient ID** into a proper 70/15/15 train/val/test, persisted once
    to `model/checkpoints/patient_split.json` so it never changes across
    reruns.
  - Unfroze `layer3`+`layer4`+`fc` (not just the head), class-weighted loss,
    mixed precision, `ReduceLROnPlateau`, early stopping.
  - Survived a **real power outage mid-training** — this exposed that the
    training script only saved best-model weights, not full resumable state.
    Fixed by adding a `--resume` flag with full optimizer/scheduler/epoch
    state saved every epoch, plus automatic warm-start from an existing
    checkpoint when not resuming.
  - Also hardened checkpoint saving with a retry wrapper after hitting a
    **recurring transient Windows file-lock error** on `torch.save()` (looked
    like antivirus briefly locking freshly-written large files) — happened 3
    times before the fix.
  - **Final result: 95.5% accuracy / 92.8% macro-F1** on a genuinely
    patient-disjoint held-out test set (13,146 images). Confusion matrix
    shows the main weak spot is CNV↔DRUSEN confusion (243 CNV images
    misclassified as DRUSEN) — DRUSEN precision is only 77% despite 90%
    recall, plausibly because DRUSEN is the smallest class by patient count.
- **Phase B — FastAPI backend** wrapping `model/inference.py` (no logic
  duplicated). `/api/predict`, model loaded once at startup.
- **Phase C — PostgreSQL + SQLAlchemy + Alembic**, full 7-entity schema
  (USER, SCAN, MODEL_VERSION, PREDICTION, GRADCAM_RESULT, FEEDBACK,
  EVALUATION_METRIC) drafted earlier in the project as an ER diagram. Only
  SCAN/PREDICTION/GRADCAM_RESULT/MODEL_VERSION are actually wired into the
  running app — USER, FEEDBACK, EVALUATION_METRIC tables exist in the schema
  but nothing reads or writes them yet (this is one of the open gaps, see
  §4). Docker introduced here for Postgres; **hit a real port conflict** — a
  pre-existing native Windows PostgreSQL service already owned port 5432, so
  our container's connections were silently landing on the wrong server.
  Diagnosed properly (not guessed) and remapped to host port **5433**.
- **Phase D — React + TypeScript + Tailwind v4 frontend** (Vite). Predict /
  History / Detail views, typed API client matching the backend's Pydantic
  schemas.
- **Phase E — Docker Compose integration.** All 3 services (db, backend,
  frontend) up with one `docker compose up`. Found and fixed two real bugs
  by testing the actual deployed containers (not just build success):
  1. nginx doesn't know about React Router's client-side routes by default
     → direct navigation to `/history` or `/scans/1` 404'd. Fixed with an
     nginx `try_files` fallback to `index.html`.
  2. No persistent volume for the PyTorch model cache → every container
     restart re-downloaded the ~98MB ImageNet weights. Fixed with a named
     volume.
  Backend Docker image is **CPU-only by default** (matches what
  `requirements.txt` installs without a special index URL) — deliberate,
  for portability to a presentation machine with no GPU. `model/` and
  `backend/media/` are volume-mounted into the backend container, not baked
  into the image, so retraining/recalibrating never requires a rebuild.

### Stage 3 — Post-completion review (where we are now)
The user came back after Phase E and asked for a full "promised vs.
delivered" report before continuing. Findings (verified against the actual
code, not from memory):
- Evaluation metrics (precision/recall/F1/confusion matrix) exist only as
  offline files (`evaluate.py` output) — never integrated into the running
  app or database.
- `Feedback` and `EvaluationMetric` DB tables are defined but never used
  anywhere in `backend/main.py` (grepped to confirm).
- No user accounts — every scan's `user_id` is always `NULL`.
- UI was called out directly as "horrible" — functionally correct but
  generic-Tailwind-looking, no real design pass.
- Accessibility was never explicitly scoped or addressed.
- No deployment attempted (stayed local-only, which was always fine per
  scope — "if I can, that's a plus").

Then the user added five more requirements from real-world testing and
feedback from their professor/teachers:
1. **Grad-CAM needs to be more accurate.**
2. **A section explaining *why* Grad-CAM points where it points** (clinical
   context for the highlighted region).
3. **Critical/dangerous bug**: uploading a non-OCT image (the user tested
   with a full-body photo) produced a confident, completely wrong disease
   diagnosis. The model has no notion of "I don't know."
4. **Professor**: use data from more sources for generalization testing —
   currently only ever trained/evaluated on Kermany OCT2017.
5. **A different teacher's critique** (from an earlier presentation): the
   pipeline (resize → normalize → ResNet50) isn't exclusive to OCT — the
   exact same code would work for any image classification task. To make it
   genuinely OCT-specific, the *preprocessing* needs OCT-domain steps that
   wouldn't make sense for other imaging modalities.

All of this was consolidated into **`TODO.md`** as 11 ordered checkpoints,
explicitly to be tackled one at a time, not as one big attempt (the user was
clear about this pacing preference).

### Checkpoint 1 — done (this session, most recent work)
Out-of-distribution (OOD) detection, so the app can say "this doesn't look
like an OCT scan" instead of forcing a diagnosis.

**Approach actually used** (differs from the original TODO.md plan — see the
note inside `TODO.md`'s Checkpoint 1 section): originally planned to train a
binary OCT-vs-not classifier against downloaded CIFAR-10 negative images.
**That download was extremely slow** (a specific torchvision mirror serving
at ~15KB/s — confirmed general internet was fine via a fast pytorch.org
test, so it was mirror-specific, not a connectivity problem). Abandoned that
and pivoted to something better-suited anyway: **feature-space anomaly
detection**, which needs zero negative training images.

> ⚠️ **SUPERSEDED — read the "current design" box below before acting on
> anything in this subsection.** The three-stage design described next was
> the *original* Checkpoint 1 implementation. Stages 2 and 3 were retired
> in commit `16a728b` ("fixed the ood gate"). The paragraphs are kept
> because the reasoning behind the retirement is a defensible experimental
> result and is likely to be asked about — not because they describe the
> running system.

Originally, three stages, cheapest first, all in `model/ood_detector.py`:
1. **Color heuristic** — real OCT B-scans are near-grayscale (R≈G≈B per
   pixel); an actual color photo fails this instantly, before any model
   runs.
2. **Brightness heuristic** — OCT B-scans are dominated by black background,
   so mean brightness is characteristically low (calibrated threshold:
   99th percentile of real OCT training brightness ≈ 109 on a 0-255 scale).
   Catches grayscale non-OCT images (e.g. a B&W photo) that pass stage 1.
3. **Feature-space distance** — extracts the *already-trained disease
   model's* own penultimate-layer features (via a forward hook on
   `model.avgpool`, reusing the model already loaded for prediction — no
   extra network) and measures normalized distance from the centroid of real
   OCT training images in that space. Threshold calibrated as the 99th
   percentile of intra-OCT distances (~1.45) from 1,600 real training images.

Calibration for stages 2–3 came from `model/compute_ood_stats.py`, saved to
`model/checkpoints/ood_stats.pth`.

**Why stages 2 and 3 were retired.** Both were calibrated against 1,600
**Kermany-only** images, which made "is this an OCT scan?" quietly collapse
into "does this look like a *Kermany* OCT scan?". Once real Noor Eye
Hospital scans were tested, the gate rejected **3 of 5** genuine CNV
images — a different scanner produces legitimately different brightness and
feature statistics, and the calibration had no way to know that. A gate that
refuses real patient data is worse than no gate.

### Current design (this is what runs)

Two stages, cheapest first, entry point still `model/ood_detector.py`'s
`check_is_oct()`:
1. **Grayscale heuristic** — unchanged from stage 1 above
   (`is_grayscale_heuristic`, threshold 12.0 mean channel difference).
2. **CLIP zero-shot semantic check** — `model/clip_ood.py`, using
   `openai/clip-vit-base-patch32`. The image is scored against 8 text
   prompts; index 0 is the only accepting prompt ("an OCT scan"), the other
   seven cover people, objects, animals, natural photographs, X-ray/CT,
   abstract art and gradients. The OCT prompt must win the **argmax** —
   there is deliberately **no tuned probability threshold**, because a tuned
   threshold is exactly what failed before.

CLIP needs no per-dataset calibration, so it generalizes to scanners it has
never seen. **Validated 45/45 correct**: 30 real OCT images spanning all four
datasets (including the exact Noor images the old gate rejected) plus 15 real
non-OCT photographs.

Consequences for anyone working on this:
- `model/compute_ood_stats.py`, `ood_stats.pth`, and
  `compute_ood_stats`/`ood_distance`/`load_ood_stats` inside
  `ood_detector.py` are **inert**. `check_is_oct` does not call them.
- Retraining the disease model **no longer requires recalibrating the OOD
  gate**, because the gate no longer depends on the disease model's feature
  space at all. (Under the old design it did, and forgetting to recalibrate
  after a retrain was a real bug — see TODO.md.)
- CLIP weights are downloaded from HuggingFace on first use and cached in
  the `visioret_hf_cache` Docker volume.

Integrated into `backend/main.py` (`/api/predict` returns **HTTP 422** with
a clear message on rejection, checked via `check_is_oct()` before running
the disease classifier) and into `app.py` (Streamlit demo) for consistency.
Frontend (`UploadPredict.tsx`) shows this as a distinct **amber** notice
(not red) — it's a valid system decision, not an error; `ApiError` in
`api/client.ts` now carries the HTTP status so the frontend can branch on
`status === 422` specifically.

**Verified working through the actual running Docker stack** (not just
local testing): a real OCT sample predicts normally (200), a real
downloaded non-OCT photo is correctly rejected (422) with no diagnosis
produced.

---

## 4. Full checkpoint list status

See `TODO.md` for the authoritative, checkbox-tracked version. Summary:

| # | Checkpoint | Status |
|---|---|---|
| 1 | Input validation / OOD detection | ✅ Done — later **redesigned** (feature-distance → CLIP), see §3 |
| 2 | OCT-specific preprocessing pipeline | ✅ Done — **negative result, reverted**; code kept as evidence |
| 3 | Grad-CAM accuracy | ✅ Assessed — 10 overlays reviewed, no change needed |
| 4 | Grad-CAM "why" explanation section | ✅ Done (`model/explanations.py`) |
| 5 | Additional data sources / generalization | ✅ Done — Noor + OCTDL + Duke, 82.0% → 88.1% external |
| 6 | UI redesign | ✅ Done — full structural redesign (took three attempts) |
| 7 | Evaluation metrics integrated into the app | ✅ Done (`/api/metrics`, metrics page) |
| 8 | Feedback/correction workflow | ✅ Done (reviewer-gated) |
| 9 | User accounts | ✅ Done — bcrypt + JWT, viewer/reviewer/admin RBAC |
| 10 | Accessibility pass | ✅ Done — contrast computed, 320px verified |
| 11 | Deployment | ⬜ Not started (stretch, do last) |

Pre-defense review of the whole project is tracked separately in
`REVIEW_CHECKPOINTS.md` (R1–R9).

Recommended order is safety → scientific rigor → explainability → product
polish → completeness → stretch, but this was explicitly left open to
reordering by the user.

---

## 5. Architecture reference

```
visioret/
  app.py                        # Streamlit demo (still maintained, has OOD gate too)
  model/
    inference.py                 # preprocessing, predict(), manual Grad-CAM, load_model()
    dataset.py                    # patient-grouped dataset/split helpers + 4 dataset collectors
    train_full.py                  # real training script: full dataset, resume/warm-start, patient split
    evaluate.py                    # precision/recall/F1/confusion matrix on held-out test set
    evaluate_cross_dataset.py       # external-generalization eval (Noor + OCTDL + Duke)
    audit_patient_leakage.py         # R2: quantifies the class-prefixed grouping flaw
    explanations.py                  # Checkpoint 4: clinical text + heatmap-geometry description
    ood_detector.py                   # OOD gate entry point: grayscale -> CLIP (see §3)
    clip_ood.py                        # Checkpoint 1 (redesigned): CLIP zero-shot OCT check
    oct_preprocessing.py                # RETIRED experiment (Checkpoint 2), kept as evidence
    compute_ood_stats.py                 # RETIRED: calibration for the old feature-distance stage
    train_quick.py                        # LEGACY: original 400-image demo fine-tune
    checkpoints/
      resnet50_oct.pth               # THE trained model (94MB) -- committed to git
      patient_split.json              # persisted train/val/test patient-id split
      external_patient_split.json      # same, for the three external datasets
      evaluation_metrics.json           # committed metrics export, seeds a fresh DB
      evaluation_report.txt             # in-distribution eval (shown in-app via /api/metrics)
      cross_dataset_evaluation_report.txt
      confusion_matrix.png / cross_dataset_confusion_matrix.png
      train_full.log                   # training log
  backend/
    main.py                        # FastAPI app, all 12 endpoints, OOD gate wired in
    auth.py                         # bcrypt hashing, JWT, role dependencies (viewer/reviewer/admin)
    schemas.py                       # Pydantic request/response models
    storage.py                        # saves scan images to backend/media/
    grant_role.py                      # role CLI -- the ONLY way to create an admin
    purge_anonymous.py                  # deletes anonymous scans + their image files
    db/
      models.py                      # SQLAlchemy models, all 7 entities
      session.py                      # DB engine/session, reads DATABASE_URL
      model_version.py                 # shared get_or_create_model_version
      write_evaluation.py               # best-effort metric write from eval scripts
    alembic/versions/               # 7 migrations, chain intact
    Dockerfile                      # CPU-only, model/ volume-mounted not baked in
  frontend/
    src/
      api/client.ts                  # typed fetch wrapper, ApiError carries HTTP status
      api/types.ts                    # types matching backend Pydantic schemas
      context/                         # AuthContext, ThemeContext
      lib/                              # identicon, anonSession, motion, classColors, format
      components/
        layout/                        # Header, UserMenu, Avatar, ThemeToggle, SystemStatus,
                                       #   PageHeader, LogoMark
        analysis/                       # ScanAnalysis (the workspace), ImagePane,
                                        #   ScanComparison, ImageLightbox, PredictionSummary,
                                        #   ProbabilityDistribution, ExplanationPanel, ReviewPanel
        archive/                         # ScanArchive, ArchiveToolbar
        metrics/                          # MetricsSection, PerClassTable, ConfusionMatrix
        upload/                            # UploadWorkspace
        ui/ states/                         # Button, AnimatedNumber, loading/error/empty states
      pages/                          # Predict, History, ScanDetail, Metrics, Login,
                                      #   Profile, Admin, NotFound (7 + catch-all)
      index.css                        # Tailwind v4 @theme semantic design tokens
    Dockerfile                      # multi-stage: node build -> nginx serve
    nginx.conf                      # SPA fallback routing fix
  docker-compose.yml               # db (port 5433) + backend (8000) + frontend (5173)
  .env.example                     # copy to .env; JWT_SECRET_KEY is REQUIRED
  README.md                        # setup, usage, results, limitations
  FEATURES.md                      # complete feature inventory + all known gaps
  REVIEW_CHECKPOINTS.md            # pre-defense review plan R1-R9 and findings
  TODO.md                          # the living checkpoint list -- READ THIS TOO
  PROJECT_CONTEXT.md               # this file
```

**How to run the whole thing:**
```bash
docker compose up -d --build   # first time or after code changes
```
Then open http://localhost:5173. Docker Desktop is often NOT running when a
session starts on this machine — check with `docker info`, and if it's down,
either ask the user to start it or launch
`"/c/Program Files/Docker/Docker/Docker Desktop.exe"` and wait via
`until docker info >/dev/null 2>&1; do sleep 3; done`.

**Dataset locations:** all four datasets live outside the repo on this
machine (none are part of git), and their paths are constants at the top of
`model/dataset.py`:

| Dataset | Path |
|---|---|
| Kermany OCT2017 | `G:\Download\archive\OCT2017\{train,test,val}` |
| Noor Eye Hospital | `G:\Download\archive\NoorEyeHospital\extracted\NEH_UT_2021RetinalOCTDataset` |
| OCTDL | `G:\Download\archive\OCTDL\extracted\OCTDL` |
| Duke (Srinivasan 2014) | `G:\Download\archive\DukeSrinivasan2014\extracted\Publication_Dataset` |

Needed by `train_full.py`, `evaluate.py` and `evaluate_cross_dataset.py`.
The OOD gate no longer needs them at all — CLIP requires no calibration
against project data.

**Local (non-Docker) dev/testing:** the Python venv at `venv/` has
everything installed (CUDA-enabled torch on this machine). Useful for fast
iteration without waiting on Docker rebuilds — e.g. run
`venv/Scripts/python.exe -m uvicorn backend.main:app --port 8001` pointed at
the same Postgres (exposed on host port 5433 by the running `db` container)
for near-instant testing of backend code changes, then only rebuild the
Docker image once confident it's correct.

---

## 6. Key technical decisions and their reasoning

- **CPU-only backend in Docker**: portability. The user will present on a
  different laptop that has no GPU. `torch.device('cuda' if available else
  'cpu')` throughout means this "just works" either way.
- **Patient-level splitting everywhere**: the Kermany filenames encode
  patient IDs (`CLASS-patientID-index.jpeg`). Never split by image — always
  by patient, or the same patient's correlated images can leak across
  train/val/test and inflate reported accuracy (this is a real, verified
  issue in the *official* dataset split, not just theoretical caution).
- **`patient_split.json` is persisted once and never re-randomized** — if
  you ever touch `train_full.py`'s split logic, do NOT delete/regenerate
  this file casually; the held-out test set integrity depends on it staying
  fixed across all training runs so far.
- **Model files are volume-mounted, not baked into Docker images** — lets
  retraining or recalibration take effect without an image rebuild.
- **`ModelVersion` DB rows are keyed by checkpoint file mtime** — so
  retraining automatically gets its own row and predictions stay
  attributable to the exact model that made them, with no manual versioning
  needed.
- **OOD detection needs no negative training data** by design (see §3) —
  this was a deliberate, justified pivot away from the original plan, not a
  compromise. Worth explaining this reasoning if it comes up in a defense.
- **`robust_torch_save()` retry wrapper** in `train_full.py` — a genuine,
  repeatedly-observed Windows issue (large freshly-written files transiently
  locked, likely antivirus), not defensive over-engineering.

---

## 7. Working with this user

- **Pacing**: explicitly wants checkpoints tackled one at a time, "not one
  big attempt." Don't jump ahead to the next checkpoint without them saying
  go, even if the current one is clearly finished.
- **Mode**: chose "you build it, I review" over the earlier teaching/
  pair-programming style — proceed with reasonable default technical
  decisions rather than asking permission for every sub-choice, but always
  explain the *why* clearly afterward, especially for anything that deviates
  from an earlier stated plan (see the OOD approach pivot as the template
  for how to communicate this).
- **Standards**: this is a final-year bachelor's defense project — quality
  and rigor matter, explicitly not "like first year students." Don't paper
  over gaps; call them out directly (the user responded well to the honest
  "UI looks generic" acknowledgment rather than defensiveness).
- **Verify, don't assume**: this user has caught real bugs by testing things
  themselves (the full-body-photo OOD failure was found by the user, not by
  me). When claiming something works, it should be verified against the
  actual running system, not just "the code looks right."
- **Time-conscious**: has interrupted work to ask "how long will this take"
  and asked to kill background processes when short on time. Always give an
  honest time estimate when something might take a while (large downloads,
  Docker rebuilds), and don't be precious about killing/restarting
  processes — checkpointed work (git, TODO.md, saved model weights) is
  designed to survive that.
- **Autonomy boundaries learned the hard way**: early in this project the
  user gave broad "don't ask, just do it" authorization while away, and I
  overstepped by starting a new phase without explicit sign-off — was
  corrected immediately. Since then: proceed within an already-agreed
  checkpoint/phase without friction, but always stop and report at its
  natural completion boundary rather than auto-continuing to the next one.
- **Git**: the user sometimes commits directly themselves (not always
  through this chat) — don't assume the working tree matches the last known
  git state without checking `git log`/`git status` first. Never push
  without explicit confirmation each time.
- **Environment quirks worth knowing** (all encountered and solved once
  already, don't rediscover them the hard way):
  - Docker Desktop is frequently not running at session start.
  - Port 5432 is taken by a separate native Postgres service on this
    machine — this project's Postgres is intentionally on 5433.
  - Some individual download mirrors (a torchvision CIFAR-10 mirror, seen
    once) can be extremely slow even when general internet is fast — test
    with a small request before committing to a large download, and have a
    fallback plan.
  - Killing a background task via the harness's task-tracking can leave a
    spawned subprocess alive (seen with `docker-compose`/`docker-buildx`) —
    verify with `tasklist`/`docker ps` after stopping something, don't just
    trust the tracker.
  - Browser automation cannot drive native file-picker uploads (browser
    security) — verify upload-dependent flows via direct `curl` to the
    backend instead, and say so explicitly rather than claiming full
    UI-level verification.
