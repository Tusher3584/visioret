"""Integration tests: the prediction pipeline end to end over HTTP --
validation, the OOD gate, classification, Grad-CAM, persistence, media."""

import io
import os

import pytest
from PIL import Image

from conftest import MEDIA_DIR, SAMPLE_FILES, chart_bytes, colour_photo_bytes, sample_bytes, upload


@pytest.mark.parametrize("cls", ["CNV", "DME", "DRUSEN", "NORMAL"])
def test_known_sample_is_classified_correctly(client, cls):
    """Midterm T3/T4: a known sample of each class gets its own label."""
    r = upload(client, sample_bytes(cls), filename=SAMPLE_FILES[cls])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["predicted_class"] == cls
    assert body["confidence"] >= 0.5
    probs = body["probabilities"]
    assert set(probs) == {"CNV", "DME", "DRUSEN", "NORMAL"}
    assert abs(sum(probs.values()) - 1.0) < 1e-4
    assert body["confidence"] == pytest.approx(max(probs.values()))
    assert body["explanation"]


def test_prediction_images_are_stored_and_served(client):
    """Midterm T5/T6 (API half): both images exist, are served, and the
    overlay has the scan's own dimensions."""
    data = sample_bytes("CNV")
    r = upload(client, data)
    body = r.json()
    original_size = Image.open(io.BytesIO(data)).size

    for key in ("original_image_url", "gradcam_overlay_url"):
        url = body[key]
        assert url.startswith("/media/scans/")
        assert os.path.isfile(os.path.join(MEDIA_DIR, os.path.basename(url)))
        served = client.get(url)
        assert served.status_code == 200
        assert served.headers["content-type"] == "image/jpeg"
        assert Image.open(io.BytesIO(served.content)).size == original_size


def test_prediction_is_persisted_with_model_version(client, reviewer):
    from conftest import auth

    r = upload(client, sample_bytes("NORMAL"), headers=auth(reviewer))
    scan_id = r.json()["scan_id"]
    detail = client.get(f"/api/scans/{scan_id}", headers=auth(reviewer)).json()
    assert detail["predicted_class"] == "NORMAL"
    assert detail["model_version_label"].startswith("resnet50_oct_")  # SHA-256-keyed version
    assert detail["gradcam_overlay_url"] == r.json()["gradcam_overlay_url"]


def test_text_file_renamed_to_jpg_is_rejected(client):
    """Midterm T2."""
    r = upload(client, b"this is not an image, just text", filename="notes.jpg")
    assert r.status_code == 400
    assert "image" in r.json()["detail"].lower()


def test_wrong_content_type_is_rejected(client):
    r = upload(client, b"%PDF-1.4 ...", filename="scan.pdf", content_type="application/pdf")
    assert r.status_code == 400


def test_truncated_jpeg_is_rejected(client):
    data = sample_bytes("CNV")
    assert upload(client, data[: len(data) // 3]).status_code == 400


def test_oversized_upload_is_rejected(client):
    big = b"\xff\xd8" + b"0" * (12 * 1024 * 1024 + 10)
    assert upload(client, big).status_code == 413


def test_decompression_bomb_is_rejected(client):
    # Small file, enormous declared dimensions.
    buf = io.BytesIO()
    Image.new("L", (12000, 12000)).save(buf, format="PNG", optimize=True)
    r = upload(client, buf.getvalue(), filename="bomb.png", content_type="image/png")
    assert r.status_code == 400


def _scan_count(db_session):
    from backend.db.models import Scan

    db_session.expire_all()
    return db_session.query(Scan).count()


def test_colour_photo_rejected_by_ood_gate_without_diagnosis(client, db_session):
    before = _scan_count(db_session)
    r = upload(client, colour_photo_bytes(), filename="photo.jpg")
    assert r.status_code == 422
    assert "doesn't look like a retinal OCT scan" in r.json()["detail"]
    assert "predicted_class" not in r.json()
    assert _scan_count(db_session) == before  # nothing persisted, no diagnosis on record


def test_chart_rejected_by_clip_stage(client, db_session):
    """Regression (R5): a grayscale chart was once accepted and 'diagnosed'."""
    before = _scan_count(db_session)
    r = upload(client, chart_bytes(), filename="chart.png", content_type="image/png")
    assert r.status_code == 422
    assert _scan_count(db_session) == before


def test_rapid_successive_requests_are_not_mixed_up(client):
    """Midterm T7 (sequential burst half; true concurrency is measured
    separately against the deployed stack)."""
    expected = ["CNV", "DME", "DRUSEN", "NORMAL"] * 2
    results = [upload(client, sample_bytes(c)).json() for c in expected]
    assert [r["predicted_class"] for r in results] == expected
    assert len({r["scan_id"] for r in results}) == len(expected)
