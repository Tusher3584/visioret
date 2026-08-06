"""Pydantic request/response models for the Visioret API."""

from datetime import datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    device: str
    checkpoint_loaded: bool
    classes: list[str]


class PredictionResponse(BaseModel):
    scan_id: int
    predicted_class: str
    confidence: float
    probabilities: dict[str, float]
    original_image_url: str
    gradcam_overlay_url: str


class ScanSummary(BaseModel):
    scan_id: int
    uploaded_at: datetime
    predicted_class: str
    confidence: float
    original_image_url: str


class ScanDetail(BaseModel):
    scan_id: int
    uploaded_at: datetime
    predicted_class: str
    confidence: float
    probabilities: dict[str, float]
    original_image_url: str
    gradcam_overlay_url: str
    model_version_label: str
