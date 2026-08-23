"""Writes evaluate.py / evaluate_cross_dataset.py results into the
evaluation_metrics table, so the frontend has something to show (see
Checkpoint 7 in TODO.md). Kept separate from model/evaluate*.py's core
logic and best-effort (never raises) -- those scripts should still work
standalone, printing/saving their .txt and .png reports, even if Postgres
isn't running (e.g. outside Docker).
"""

import sys
import traceback


def write_evaluation_metric(
    checkpoint_path,
    val_macro_f1,
    dataset_split: str,
    accuracy: float,
    precision_macro: float,
    recall_macro: float,
    f1_macro: float,
    per_class_metrics: dict,
    confusion_matrix: dict,
) -> bool:
    """Upserts one EvaluationMetric row (model_version_id, dataset_split).
    Returns True on success, False if the DB write was skipped/failed --
    callers should treat that as non-fatal."""
    try:
        from backend.db.model_version import get_or_create_model_version
        from backend.db.models import EvaluationMetric
        from backend.db.session import SessionLocal

        db = SessionLocal()
        try:
            version = get_or_create_model_version(db, checkpoint_path, val_macro_f1)
            existing = (
                db.query(EvaluationMetric)
                .filter_by(model_version_id=version.id, dataset_split=dataset_split)
                .first()
            )
            if existing:
                db.delete(existing)
                db.flush()

            db.add(
                EvaluationMetric(
                    model_version_id=version.id,
                    dataset_split=dataset_split,
                    accuracy=accuracy,
                    precision_macro=precision_macro,
                    recall_macro=recall_macro,
                    f1_macro=f1_macro,
                    per_class_metrics=per_class_metrics,
                    confusion_matrix=confusion_matrix,
                )
            )
            db.commit()
            return True
        finally:
            db.close()
    except Exception:
        print(
            f"Warning: could not write evaluation metrics to the database for split '{dataset_split}' "
            "(is Postgres/Docker running? see backend/db/session.py). Continuing -- "
            ".txt/.png reports are unaffected.",
            file=sys.stderr,
        )
        traceback.print_exc(file=sys.stderr)
        return False
