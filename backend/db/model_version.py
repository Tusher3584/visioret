"""Shared helper for resolving/creating the ModelVersion row for whatever
checkpoint is currently on disk. Used by backend/main.py (at API startup)
and by model/evaluate.py / model/evaluate_cross_dataset.py (when writing
evaluation results) -- kept out of backend/main.py so the evaluation
scripts don't have to import the FastAPI app to use it.
"""

import os

from sqlalchemy.orm import Session

from backend.db.models import ModelVersion


def get_or_create_model_version(db: Session, checkpoint_path: str, val_macro_f1) -> ModelVersion:
    """One ModelVersion row per distinct checkpoint file (keyed by its mtime,
    so retraining -- which produces a new file mtime -- gets its own row and
    predictions/evaluations stay attributable to the exact model that made
    them)."""
    if not os.path.isfile(checkpoint_path):
        version_label = "untrained-imagenet-backbone"
    else:
        mtime = int(os.path.getmtime(checkpoint_path))
        version_label = f"resnet50_oct_{mtime}"

    existing = db.query(ModelVersion).filter_by(version_label=version_label).first()
    if existing:
        return existing

    version = ModelVersion(
        version_label=version_label, checkpoint_path=checkpoint_path, val_macro_f1=val_macro_f1
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version
