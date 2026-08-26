"""Grant or revoke the reviewer role.

Roles are deliberately NOT self-assignable through the API: registration
always creates a viewer, so nobody can hand themselves the ability to write
correction labels. Promotion is an administrative action performed
out-of-band, which is how real systems bootstrap privileged accounts.

Usage (from the project root):

    # inside Docker
    docker compose exec backend python -m backend.grant_role --list
    docker compose exec backend python -m backend.grant_role user@example.com reviewer

    # against a local Postgres
    python -m backend.grant_role user@example.com reviewer
"""

import argparse
import sys

from backend.auth import ROLE_REVIEWER, ROLE_VIEWER
from backend.db.models import User
from backend.db.session import SessionLocal

ROLES = (ROLE_VIEWER, ROLE_REVIEWER)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("email", nargs="?", help="Email address of the account to change.")
    parser.add_argument("role", nargs="?", choices=ROLES, help="Role to assign.")
    parser.add_argument("--list", action="store_true", help="List all accounts and their roles, then exit.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.list:
            users = db.query(User).order_by(User.id).all()
            if not users:
                print("No accounts registered yet.")
                return 0
            width = max(len(u.email) for u in users)
            print(f"{'ID':<4} {'EMAIL':<{width}}  ROLE")
            for user in users:
                print(f"{user.id:<4} {user.email:<{width}}  {user.role}")
            return 0

        if not args.email or not args.role:
            parser.error("provide EMAIL and ROLE, or use --list")

        user = db.query(User).filter_by(email=args.email).first()
        if user is None:
            print(f"No account with email '{args.email}'.", file=sys.stderr)
            return 1

        if user.role == args.role:
            print(f"{user.email} is already '{args.role}'. Nothing to do.")
            return 0

        previous = user.role
        user.role = args.role
        db.commit()
        print(f"{user.email}: {previous} -> {args.role}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
