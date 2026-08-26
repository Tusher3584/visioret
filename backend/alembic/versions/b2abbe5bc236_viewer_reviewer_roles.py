"""viewer/reviewer roles

Replaces the single placeholder role ("researcher", which was stored but
never checked anywhere) with the two roles the app actually enforces:

  viewer   -- own scans only, no corrections, no metrics
  reviewer -- sees all scans, may record corrections, may see metrics

Existing accounts are migrated to reviewer. They were created before roles
meant anything and could already do everything, so demoting them would
silently remove access they currently have.

Revision ID: b2abbe5bc236
Revises: e96f48ad79fb
Create Date: 2026-08-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2abbe5bc236'
down_revision: Union[str, Sequence[str], None] = 'e96f48ad79fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("UPDATE users SET role = 'reviewer' WHERE role = 'researcher'")
    # Anything else unrecognised becomes the least-privileged role.
    op.execute("UPDATE users SET role = 'viewer' WHERE role NOT IN ('viewer', 'reviewer')")
    op.alter_column("users", "role", server_default="viewer")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("UPDATE users SET role = 'researcher'")
    op.alter_column("users", "role", server_default="researcher")
