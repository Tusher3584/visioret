"""Loads committed evaluation results into an empty database at startup.

Why this exists
---------------
/api/metrics filters strictly by the active model version, and the rows it
needs are produced by model/evaluate.py -- which needs the 84k-image Kermany
dataset that is deliberately not in the repo. So on any machine that just
clones the project and runs `docker compose up`, the metrics page had nothing
to show and no local way to fix it. The project's headline evidence was
missing precisely where a new reader would look for it.

model/checkpoints/evaluation_metrics.json is written by the evaluation
scripts and committed alongside the checkpoint. This seeds those numbers into
a fresh database.

Two safety properties:
  - It only ever INSERTS splits that are missing. It never overwrites a row
    produced by an actual local evaluation run, so real results always win
    over seeded ones.
  - It refuses to seed if the export's checkpoint fingerprint doesn't match
    the checkpoint on disk. Showing metrics from a different model would be
    worse than showing none.
"""

import json
import os
import sys

from sqlalchemy.orm import Session

from backend.db.model_version import checkpoint_fingerprint
from backend.db.models import EvaluationMetric

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXPORT_PATH = os.path.join(ROOT_DIR, "model", "checkpoints", "evaluation_metrics.json")


def seed_evaluation_metrics(
    db: Session, checkpoint_path: str, model_version_id: int, export_path: str = EXPORT_PATH
) -> int:
    """Inserts any missing evaluation splits for this model version from the
    committed export. Returns how many rows were inserted. Never raises --
    a failure here must not stop the API from starting."""
    try:
        if not os.path.isfile(export_path):
            return 0

        with open(export_path, "r", encoding="utf-8") as f:
            document = json.load(f)

        fingerprint = checkpoint_fingerprint(checkpoint_path)
        exported_fingerprint = document.get("checkpoint_fingerprint")
        if fingerprint is None or exported_fingerprint != fingerprint:
            print(
                f"Skipping metric seeding: {os.path.basename(export_path)} describes checkpoint "
                f"'{exported_fingerprint}' but the checkpoint on disk is '{fingerprint}'. "
                "Re-run model/evaluate.py to regenerate it.",
                file=sys.stderr,
            )
            return 0

        existing_splits = {
            row.dataset_split
            for row in db.query(EvaluationMetric.dataset_split)
            .filter_by(model_version_id=model_version_id)
            .all()
        }

        inserted = 0
        for dataset_split, payload in (document.get("metrics") or {}).items():
            if dataset_split in existing_splits:
                continue
            db.add(
                EvaluationMetric(
                    model_version_id=model_version_id,
                    dataset_split=dataset_split,
                    accuracy=payload["accuracy"],
                    precision_macro=payload["precision_macro"],
                    recall_macro=payload["recall_macro"],
                    f1_macro=payload["f1_macro"],
                    per_class_metrics=payload["per_class_metrics"],
                    confusion_matrix=payload["confusion_matrix"],
                )
            )
            inserted += 1

        if inserted:
            db.commit()
            print(f"Seeded {inserted} evaluation metric row(s) from {os.path.basename(export_path)}")
        return inserted
    except Exception as exc:
        db.rollback()
        print(f"Warning: could not seed evaluation metrics ({exc}). The metrics page may be empty.", file=sys.stderr)
        return 0
