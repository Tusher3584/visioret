"""Pydantic request/response models for the Visioret API."""

from datetime import datetime

from pydantic import BaseModel


class PerClassMetric(BaseModel):
    precision: float
    recall: float
    f1_score: float
    support: int


class ConfusionMatrix(BaseModel):
    labels: list[str]
    matrix: list[list[int]]


class EvaluationMetricResponse(BaseModel):
    dataset_split: str
    dataset_split_label: str
    accuracy: float
    precision_macro: float
    recall_macro: float
    f1_macro: float
    per_class_metrics: dict[str, PerClassMetric]
    confusion_matrix: ConfusionMatrix
    evaluated_at: datetime
    model_version_label: str


class HealthResponse(BaseModel):
    status: str
    device: str
    checkpoint_loaded: bool
    classes: list[str]
    ood_gate_active: bool


class PredictionResponse(BaseModel):
    scan_id: int
    predicted_class: str
    confidence: float
    probabilities: dict[str, float]
    original_image_url: str
    gradcam_overlay_url: str
    explanation: str


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
    explanation: str
    model_version_label: str
