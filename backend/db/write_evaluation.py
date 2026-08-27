"""Records evaluate.py / evaluate_cross_dataset.py results in two places:

1. `model/checkpoints/evaluation_metrics.json` -- a small file that IS
   committed to git, alongside the checkpoint it describes.
2. The `evaluation_metrics` table, so the app has something to show
   (Checkpoint 7 in TODO.md).

(1) exists because of how (2) fails on a fresh machine. Regenerating the
rows requires model/evaluate.py, which requires the 84k-image dataset that
is deliberately not in the repo -- so anyone who clones the project can
never populate the metrics page, and the project's headline evidence is
missing exactly where an examiner would look for it. Exporting the numbers
next to the weights makes them travel with the repo; see
backend/db/seed_metrics.py, which loads them into an empty database at
startup.

The DB write is best-effort and never raises -- the evaluation scripts must
still work standalone (printing/saving their .txt and .png reports) when
Postgres isn't running, e.g. outside Docker. The JSON export is attempted
first for the same reason: it needs no database at all.
"""

import json
import os
import sys
import traceback

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXPORT_PATH = os.path.join(ROOT_DIR, "model", "checkpoints", "evaluation_metrics.json")


def export_evaluation_metric(
    checkpoint_path,
    val_macro_f1,
    dataset_split: str,
    payload: dict,
    export_path: str = EXPORT_PATH,
) -> bool:
    """Merges one split's results into the committed JSON export.

    Merges rather than overwrites: evaluate.py and evaluate_cross_dataset.py
    are separate runs writing different splits, and whichever ran second must
    not erase the other's numbers. If the checkpoint's fingerprint has changed
    (i.e. the model was retrained), previously exported splits are dropped --
    they describe a model that no longer exists here, and keeping them would
    silently attribute old numbers to new weights.
    """
    try:
        from backend.db.model_version import checkpoint_fingerprint

        fingerprint = checkpoint_fingerprint(checkpoint_path)
        if fingerprint is None:
            return False

        document = {"checkpoint_fingerprint": fingerprint, "val_macro_f1": val_macro_f1, "metrics": {}}
        if os.path.isfile(export_path):
            try:
                with open(export_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                if existing.get("checkpoint_fingerprint") == fingerprint:
                    document = existing
                    document["val_macro_f1"] = val_macro_f1
            except (json.JSONDecodeError, OSError):
                pass  # corrupt or unreadable -- just rewrite it

        document.setdefault("metrics", {})[dataset_split] = payload

        os.makedirs(os.path.dirname(export_path), exist_ok=True)
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(document, f, indent=2)
        print(f"Evaluation metrics exported to {export_path} (split='{dataset_split}')")
        return True
    except Exception:
        print(f"Warning: could not export evaluation metrics for split '{dataset_split}'.", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return False


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
    """Upserts one EvaluationMetric row (model_version_id, dataset_split) and
    exports the same numbers to the committed JSON. Returns True on a
    successful DB write, False if it was skipped/failed -- callers should
    treat that as non-fatal. The export happens either way."""
    payload = {
        "accuracy": accuracy,
        "precision_macro": precision_macro,
        "recall_macro": recall_macro,
        "f1_macro": f1_macro,
        "per_class_metrics": per_class_metrics,
        "confusion_matrix": confusion_matrix,
    }
    export_evaluation_metric(checkpoint_path, val_macro_f1, dataset_split, payload)

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

            db.add(EvaluationMetric(model_version_id=version.id, dataset_split=dataset_split, **payload))
            db.commit()
            return True
        finally:
            db.close()
    except Exception:
        print(
            f"Warning: could not write evaluation metrics to the database for split '{dataset_split}' "
            "(is Postgres/Docker running? see backend/db/session.py). Continuing -- "
            ".txt/.png reports and the JSON export are unaffected.",
            file=sys.stderr,
        )
        traceback.print_exc(file=sys.stderr)
        return False
