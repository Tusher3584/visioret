"""Delete anonymous scans and their image files.

Anonymous history is session-scoped: the session id lives in the browser's
sessionStorage, so closing the browser makes those scans unreachable to
everyone (reviewers and admins excepted, who see all scans by design). But
unreachable is not the same as gone -- the rows and the JPEGs are still on
disk. This removes them for real.

Nothing deletes them automatically, because the server has no reliable way to
know a browser has closed. Run this periodically, or before handing the
machine to someone else.

Usage (from the project root):

    # what would be removed, without touching anything
    docker compose exec backend python -m backend.purge_anonymous --dry-run

    # anonymous scans older than 24 hours (default)
    docker compose exec backend python -m backend.purge_anonymous

    # every anonymous scan regardless of age
    docker compose exec backend python -m backend.purge_anonymous --all
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

from backend.db.models import Feedback, GradcamResult, Prediction, Scan
from backend.db.session import SessionLocal
from backend.storage import MEDIA_DIR


def _media_path(url_path: str | None) -> str | None:
    """'/media/scans/<file>' -> absolute path on disk."""
    if not url_path:
        return None
    return os.path.join(MEDIA_DIR, os.path.basename(url_path))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--older-than-hours",
        type=float,
        default=24.0,
        help="Only purge anonymous scans older than this many hours (default: 24).",
    )
    parser.add_argument(
        "--all", action="store_true", help="Purge every anonymous scan regardless of age."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Report what would be removed, change nothing."
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        query = db.query(Scan).filter(Scan.user_id.is_(None))
        if not args.all:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=args.older_than_hours)
            query = query.filter(Scan.uploaded_at < cutoff)

        scans = query.order_by(Scan.id).all()
        if not scans:
            print("No anonymous scans match. Nothing to do.")
            return 0

        print(f"{'Would remove' if args.dry_run else 'Removing'} {len(scans)} anonymous scan(s):")

        removed_files = 0
        for scan in scans:
            paths = [_media_path(scan.file_path)]
            for prediction in scan.predictions:
                if prediction.gradcam_result:
                    paths.append(_media_path(prediction.gradcam_result.heatmap_path))

            print(f"  #{scan.id}  {scan.uploaded_at:%Y-%m-%d %H:%M}  {os.path.basename(scan.file_path)}")

            if args.dry_run:
                continue

            # Children first -- Prediction has no cascade to Scan, so deleting
            # the scan alone would leave orphaned predictions behind.
            for prediction in list(scan.predictions):
                db.query(Feedback).filter_by(prediction_id=prediction.id).delete()
                db.query(GradcamResult).filter_by(prediction_id=prediction.id).delete()
                db.query(Prediction).filter_by(id=prediction.id).delete()
            db.delete(scan)

            for path in paths:
                if path and os.path.isfile(path):
                    try:
                        os.remove(path)
                        removed_files += 1
                    except OSError as exc:
                        print(f"    could not delete {path}: {exc}", file=sys.stderr)

        if args.dry_run:
            print("\nDry run -- nothing was changed.")
            return 0

        db.commit()
        print(f"\nRemoved {len(scans)} scan(s) and {removed_files} image file(s).")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
