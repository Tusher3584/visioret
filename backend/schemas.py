"""Pydantic request/response models for the Visioret API.

Length limits on request models are not decoration: every bounded field here
mirrors a bounded column in backend/db/models.py. Without them, an
over-length value reaches Postgres, raises StringDataRightTruncation, and
surfaces to the caller as a 500 -- an input error reported as a server
failure. Declaring the bound here turns each of those into a 422 with a
message naming the field, and documents the limit in the OpenAPI schema for
free.
"""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

# Mirrors backend/db/models.py column widths. Keep in sync -- if a column
# grows, the bound here has to grow with it.
NAME_MAX = 120
EMAIL_MAX = 255
COMMENT_MAX = 1000
CLASS_NAME_MAX = 30
ROLE_MAX = 30

# bcrypt operates on at most 72 BYTES and version 5.x raises ValueError
# rather than silently truncating, so an over-long password was reaching
# hash_password() and 500-ing. 72 is a hard ceiling, not a style choice.
# (backend/auth.py enforces the byte-accurate check; this catches the common
# case early and puts the limit in the API docs.)
PASSWORD_MIN = 8
PASSWORD_MAX = 72


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
    corrected_class: str | None = Field(default=None, max_length=CLASS_NAME_MAX)
    comment: str | None = Field(default=None, max_length=COMMENT_MAX)


class FeedbackResponse(BaseModel):
    is_correct: bool
    corrected_class: str | None
    comment: str | None
    reviewed_at: datetime
    reviewer_name: str | None = None


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=NAME_MAX)
    # EmailStr rather than str: registration previously accepted
    # "definitely-not-an-email" and created the account.
    email: EmailStr = Field(max_length=EMAIL_MAX)
    password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)


class LoginRequest(BaseModel):
    # Deliberately NOT EmailStr, and no length bounds beyond the sane cap:
    # login must treat a malformed address exactly like a wrong password, or
    # the validation error itself tells an attacker which addresses are even
    # possible. Bounds here only stop absurd payloads.
    email: str = Field(max_length=EMAIL_MAX)
    password: str = Field(max_length=PASSWORD_MAX)


class ProfileUpdate(BaseModel):
    """Partial update of the signed-in account. Every field optional; a
    password change additionally requires the current password."""

    name: str | None = Field(default=None, max_length=NAME_MAX)
    current_password: str | None = Field(default=None, max_length=PASSWORD_MAX)
    new_password: str | None = Field(default=None, min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str


class AdminUserRow(BaseModel):
    """One account as seen from the admin user list."""

    id: int
    name: str
    email: str
    role: str
    created_at: datetime
    scans_submitted: int
    reviews_recorded: int
    # True for the requesting admin's own row -- the UI disables self-editing,
    # and the server rejects it regardless.
    is_self: bool
    # False when the row cannot be edited through the API at all (other admins).
    is_editable: bool


class RoleUpdate(BaseModel):
    role: str = Field(max_length=ROLE_MAX)


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
