"""add feedback.is_correct

Revision ID: 53b8feed0825
Revises: 263d6fc8f6f4
Create Date: 2026-08-23 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '53b8feed0825'
down_revision: Union[str, Sequence[str], None] = '263d6fc8f6f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('feedback', sa.Column('is_correct', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column('feedback', 'is_correct', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('feedback', 'is_correct')
