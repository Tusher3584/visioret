"""add users.password_hash

Revision ID: e96f48ad79fb
Revises: 53b8feed0825
Create Date: 2026-08-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e96f48ad79fb'
down_revision: Union[str, Sequence[str], None] = '53b8feed0825'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # users table is empty in every environment this has run in so far
    # (auth didn't exist before this migration) -- no default needed.
    op.add_column('users', sa.Column('password_hash', sa.String(length=255), nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'password_hash')
