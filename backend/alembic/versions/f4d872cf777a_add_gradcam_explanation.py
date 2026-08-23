"""add gradcam_results.explanation

Revision ID: f4d872cf777a
Revises: f0a32a0b30dd
Create Date: 2026-08-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4d872cf777a'
down_revision: Union[str, Sequence[str], None] = 'f0a32a0b30dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'gradcam_results',
        sa.Column('explanation', sa.String(length=1000), nullable=False, server_default=''),
    )
    op.alter_column('gradcam_results', 'explanation', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('gradcam_results', 'explanation')
