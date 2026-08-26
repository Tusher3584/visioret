"""scans.anon_session -- session-scoped anonymous history

Anonymous scans were previously pooled: every unauthenticated visitor could
see every other unauthenticated visitor's scans, which for medical images is
not an acceptable default. This adds an opaque per-session id so an anonymous
visitor sees only their own scans, for the life of that browser session.

Existing anonymous rows get NULL, which no session id can ever match, so the
previously-pooled history becomes visible to nobody. Those rows are left in
place rather than deleted here -- removing image files is not something a
schema migration should be doing. Use backend/purge_anonymous.py to clear
them out along with their files on disk.

Revision ID: c6c94791979f
Revises: b2abbe5bc236
Create Date: 2026-08-26 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c6c94791979f'
down_revision: Union[str, Sequence[str], None] = 'b2abbe5bc236'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("scans", sa.Column("anon_session", sa.String(length=64), nullable=True))
    op.create_index("ix_scans_anon_session", "scans", ["anon_session"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_scans_anon_session", table_name="scans")
    op.drop_column("scans", "anon_session")
