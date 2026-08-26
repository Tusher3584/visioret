"""SQLAlchemy models -- one class per entity in the ER diagram drafted
earlier (USER, SCAN, MODEL_VERSION, PREDICTION, GRADCAM_RESULT, FEEDBACK,
EVALUATION_METRIC).
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    # "viewer" or "reviewer" -- see backend/auth.py for what each may do.
    # Always created as viewer; promotion is an out-of-band admin action.
    role: Mapped[str] = mapped_column(String(30), default="viewer")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    scans: Mapped[list["Scan"]] = relationship(back_populates="user")


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    # Opaque per-browser-session id for scans submitted without an account.
    # Lets an anonymous visitor see their own scans for the life of that
    # session and nobody else's; the id lives in sessionStorage, so closing
    # the browser ends the session and the history becomes unreachable.
    # NULL for signed-in scans (ownership is user_id) and for legacy rows
    # predating this column, which are therefore visible to nobody.
    anon_session: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    file_path: Mapped[str] = mapped_column(String(500))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped["User | None"] = relationship(back_populates="scans")
    predictions: Mapped[list["Prediction"]] = relationship(back_populates="scan")


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version_label: Mapped[str] = mapped_column(String(120), unique=True)
    checkpoint_path: Mapped[str] = mapped_column(String(500))
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    val_macro_f1: Mapped[float | None] = mapped_column(Float, nullable=True)

    predictions: Mapped[list["Prediction"]] = relationship(back_populates="model_version")
    evaluation_metrics: Mapped[list["EvaluationMetric"]] = relationship(back_populates="model_version")


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("scans.id"))
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.id"))
    predicted_class: Mapped[str] = mapped_column(String(30))
    confidence: Mapped[float] = mapped_column(Float)
    class_probabilities: Mapped[dict] = mapped_column(JSON)
    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    scan: Mapped["Scan"] = relationship(back_populates="predictions")
    model_version: Mapped["ModelVersion"] = relationship(back_populates="predictions")
    gradcam_result: Mapped["GradcamResult | None"] = relationship(
        back_populates="prediction", uselist=False, cascade="all, delete-orphan"
    )
    feedback: Mapped["Feedback | None"] = relationship(
        back_populates="prediction", uselist=False, cascade="all, delete-orphan"
    )


class GradcamResult(Base):
    __tablename__ = "gradcam_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prediction_id: Mapped[int] = mapped_column(ForeignKey("predictions.id"), unique=True)
    heatmap_path: Mapped[str] = mapped_column(String(500))
    alpha: Mapped[float] = mapped_column(Float, default=0.45)
    explanation: Mapped[str] = mapped_column(String(1000))

    prediction: Mapped["Prediction"] = relationship(back_populates="gradcam_result")


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prediction_id: Mapped[int] = mapped_column(ForeignKey("predictions.id"), unique=True)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    # Distinguishes "confirmed correct" (True, corrected_class NULL) from
    # "flagged incorrect" (False, corrected_class set) -- presence of a
    # Feedback row alone means "reviewed" either way.
    is_correct: Mapped[bool] = mapped_column(Boolean)
    corrected_class: Mapped[str | None] = mapped_column(String(30), nullable=True)
    comment: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    prediction: Mapped["Prediction"] = relationship(back_populates="feedback")
    reviewer: Mapped["User | None"] = relationship(foreign_keys=[reviewed_by])


class EvaluationMetric(Base):
    __tablename__ = "evaluation_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.id"))
    dataset_split: Mapped[str] = mapped_column(String(30))
    accuracy: Mapped[float] = mapped_column(Float)
    precision_macro: Mapped[float] = mapped_column(Float)
    recall_macro: Mapped[float] = mapped_column(Float)
    f1_macro: Mapped[float] = mapped_column(Float)
    # {class_name: {precision, recall, f1_score, support}}
    per_class_metrics: Mapped[dict] = mapped_column(JSON)
    # {"labels": [...], "matrix": [[...], ...]} -- matrix[i][j] = count of
    # true label i predicted as label j
    confusion_matrix: Mapped[dict] = mapped_column(JSON)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    model_version: Mapped["ModelVersion"] = relationship(back_populates="evaluation_metrics")
