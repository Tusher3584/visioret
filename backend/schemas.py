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


class FeedbackCreate(BaseModel):
    # is_correct=True means the prediction was right -- corrected_class is
    # only meaningful (and required) when is_correct is False.
    is_correct: bool
    corrected_class: str | None = None
    comment: str | None = None


class FeedbackResponse(BaseModel):
    is_correct: bool
    corrected_class: str | None
    comment: str | None
    reviewed_at: datetime
    reviewer_name: str | None = None


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


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
    owner_name: str | None = None


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
    feedback: FeedbackResponse | None = None
    owner_name: str | None = None
    # Whether *this* caller may record a correction on this scan.
    can_review: bool = False
