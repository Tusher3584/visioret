"""Visioret backend -- FastAPI service wrapping model/inference.py.

Run with (from the project root):
    uvicorn backend.main:app --reload --port 8000
"""

import io
import os
import sys
from contextlib import asynccontextmanager

import torch
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from model.inference import (  # noqa: E402
    generate_gradcam,
    load_model,
    overlay_gradcam,
    predict,
    preprocess_image,
)
from model.explanations import build_explanation  # noqa: E402
from model.ood_detector import check_is_oct, load_ood_stats  # noqa: E402

from backend.db.model_version import get_or_create_model_version  # noqa: E402
from backend.db.models import EvaluationMetric, GradcamResult, Prediction, Scan  # noqa: E402
from backend.db.session import get_db  # noqa: E402
from backend.schemas import (  # noqa: E402
    EvaluationMetricResponse,
    HealthResponse,
    PredictionResponse,
    ScanDetail,
    ScanSummary,
)
from backend.storage import MEDIA_DIR, new_scan_id, save_scan_images  # noqa: E402

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECKPOINT_PATH = os.path.join(ROOT_DIR, "model", "checkpoints", "resnet50_oct.pth")

model_state = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, checkpoint_loaded, classes, val_macro_f1 = load_model(CHECKPOINT_PATH, device)
    model_state["model"] = model
    model_state["device"] = device
    model_state["checkpoint_loaded"] = checkpoint_loaded
    model_state["classes"] = classes
    model_state["ood_stats"] = load_ood_stats()

    from backend.db.session import SessionLocal

    db = SessionLocal()
    try:
        version = get_or_create_model_version(db, CHECKPOINT_PATH, val_macro_f1)
        model_state["model_version_id"] = version.id
        model_state["model_version_label"] = version.version_label
    finally:
        db.close()

    yield
    model_state.clear()


app = FastAPI(title="Visioret API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(MEDIA_DIR, exist_ok=True)
app.mount("/media", StaticFiles(directory=os.path.dirname(MEDIA_DIR)), name="media")


@app.get("/api/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="ok",
        device=model_state["device"].type,
        checkpoint_loaded=model_state["checkpoint_loaded"],
        classes=model_state["classes"],
        ood_gate_active=model_state["ood_stats"] is not None,
    )


DATASET_SPLIT_LABELS = {
    "kermany_test": "In-distribution (Kermany OCT2017 held-out test)",
    "external_test": "Cross-dataset generalization (Noor Eye Hospital + OCTDL + Duke, held-out)",
}


@app.get("/api/metrics", response_model=list[EvaluationMetricResponse])
def get_metrics(db: Session = Depends(get_db)):
    """Latest evaluation results for the currently deployed model, one row
    per dataset split that's been evaluated (see model/evaluate.py and
    model/evaluate_cross_dataset.py -- neither runs automatically, so this
    reflects whenever those were last run against the current checkpoint)."""
    version_id = model_state.get("model_version_id")
    if version_id is None:
        return []
    metrics = (
        db.query(EvaluationMetric)
        .filter_by(model_version_id=version_id)
        .order_by(EvaluationMetric.dataset_split)
        .all()
    )
    return [
        EvaluationMetricResponse(
            dataset_split=m.dataset_split,
            dataset_split_label=DATASET_SPLIT_LABELS.get(m.dataset_split, m.dataset_split),
            accuracy=m.accuracy,
            precision_macro=m.precision_macro,
            recall_macro=m.recall_macro,
            f1_macro=m.f1_macro,
            per_class_metrics=m.per_class_metrics,
            confusion_matrix=m.confusion_matrix,
            evaluated_at=m.evaluated_at,
            model_version_label=model_state["model_version_label"],
        )
        for m in metrics
    ]


@app.post("/api/predict", response_model=PredictionResponse)
async def predict_endpoint(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if file.content_type not in ("image/jpeg", "image/png"):
        raise HTTPException(status_code=400, detail="File must be a JPEG or PNG image.")

    contents = await file.read()
    try:
        image = Image.open(io.BytesIO(contents))
        image.load()
    except UnidentifiedImageError:
        raise HTTPException(status_code=400, detail="Could not read file as an image.")

    model = model_state["model"]
    device = model_state["device"]
    classes = model_state["classes"]

    image_tensor = preprocess_image(image)

    is_oct, reason, detail = check_is_oct(image, image_tensor, model, device, model_state["ood_stats"])
    if not is_oct:
        raise HTTPException(
            status_code=422,
            detail=(
                "This doesn't look like a retinal OCT scan, so no diagnosis was made. "
                "Please upload an OCT B-scan image (JPEG/PNG)."
            ),
        )

    class_name, confidence, probabilities = predict(model, image_tensor, device, class_names=classes)
    class_index = classes.index(class_name)
    heatmap = generate_gradcam(model, image_tensor, class_index, device)
    overlay = overlay_gradcam(image, heatmap)
    explanation = build_explanation(class_name, heatmap)

    file_id = new_scan_id()
    original_url, overlay_url = save_scan_images(file_id, image, overlay)

    scan = Scan(file_path=original_url)
    db.add(scan)
    db.flush()  # assigns scan.id without committing yet

    prediction = Prediction(
        scan_id=scan.id,
        model_version_id=model_state["model_version_id"],
        predicted_class=class_name,
        confidence=confidence,
        class_probabilities=probabilities,
    )
    db.add(prediction)
    db.flush()

    db.add(GradcamResult(prediction_id=prediction.id, heatmap_path=overlay_url, explanation=explanation))
    db.commit()

    return PredictionResponse(
        scan_id=scan.id,
        predicted_class=class_name,
        confidence=confidence,
        probabilities=probabilities,
        original_image_url=original_url,
        gradcam_overlay_url=overlay_url,
        explanation=explanation,
    )


@app.get("/api/scans", response_model=list[ScanSummary])
def list_scans(db: Session = Depends(get_db), limit: int = 50):
    scans = db.query(Scan).order_by(Scan.uploaded_at.desc()).limit(limit).all()
    results = []
    for scan in scans:
        if not scan.predictions:
            continue
        latest = max(scan.predictions, key=lambda p: p.predicted_at)
        results.append(
            ScanSummary(
                scan_id=scan.id,
                uploaded_at=scan.uploaded_at,
                predicted_class=latest.predicted_class,
                confidence=latest.confidence,
                original_image_url=scan.file_path,
            )
        )
    return results


@app.get("/api/scans/{scan_id}", response_model=ScanDetail)
def get_scan(scan_id: int, db: Session = Depends(get_db)):
    scan = db.query(Scan).filter_by(id=scan_id).first()
    if not scan or not scan.predictions:
        raise HTTPException(status_code=404, detail="Scan not found.")

    latest = max(scan.predictions, key=lambda p: p.predicted_at)
    if not latest.gradcam_result:
        raise HTTPException(status_code=500, detail="Scan has no Grad-CAM result on record.")

    return ScanDetail(
        scan_id=scan.id,
        uploaded_at=scan.uploaded_at,
        predicted_class=latest.predicted_class,
        confidence=latest.confidence,
        probabilities=latest.class_probabilities,
        original_image_url=scan.file_path,
        gradcam_overlay_url=latest.gradcam_result.heatmap_path,
        explanation=latest.gradcam_result.explanation,
        model_version_label=latest.model_version.version_label,
    )
