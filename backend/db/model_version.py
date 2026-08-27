"""Shared helper for resolving/creating the ModelVersion row for whatever
checkpoint is currently on disk. Used by backend/main.py (at API startup)
and by model/evaluate.py / model/evaluate_cross_dataset.py (when writing
evaluation results) -- kept out of backend/main.py so the evaluation
scripts don't have to import the FastAPI app to use it.
"""

import hashlib
import os

from sqlalchemy.orm import Session

from backend.db.models import ModelVersion

UNTRAINED_LABEL = "untrained-imagenet-backbone"


def checkpoint_fingerprint(checkpoint_path: str) -> str | None:
    """Short SHA-256 of the checkpoint's bytes, or None if it isn't there.

    This identifies the model by its CONTENT, not by where or when the file
    happens to sit on disk. That distinction matters: this used to key on the
    file's mtime, which meant a `git clone` -- writing the same 94 MB of
    weights with a fresh timestamp -- produced a brand new version label. Any
    evaluation results already recorded were keyed to the old label, so
    /api/metrics (which filters strictly by the active version) returned an
    empty list. On a fresh machine the metrics page showed nothing, and could
    not be repaired locally either, because regenerating the rows needs the
    84k-image dataset that is deliberately not in the repo.

    A content hash is stable across clones, copies and machines, so the same
    weights are the same version everywhere.
    """
    if not os.path.isfile(checkpoint_path):
        return None
    digest = hashlib.sha256()
    with open(checkpoint_path, "rb") as f:
        # Chunked: the checkpoint is ~94 MB and there is no reason to hold it
        # all in memory just to hash it.
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]


def get_or_create_model_version(db: Session, checkpoint_path: str, val_macro_f1) -> ModelVersion:
    """One ModelVersion row per distinct checkpoint file, keyed by a hash of
    its contents -- so retraining (which changes the weights) gets its own
    row and predictions/evaluations stay attributable to the exact model that
    made them, while merely moving or re-cloning the same file does not."""
    fingerprint = checkpoint_fingerprint(checkpoint_path)
    version_label = UNTRAINED_LABEL if fingerprint is None else f"resnet50_oct_{fingerprint}"

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
