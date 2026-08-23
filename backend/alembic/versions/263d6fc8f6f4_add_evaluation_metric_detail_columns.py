"""add evaluation_metrics detail columns

Revision ID: 263d6fc8f6f4
Revises: f4d872cf777a
Create Date: 2026-08-23 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '263d6fc8f6f4'
down_revision: Union[str, Sequence[str], None] = 'f4d872cf777a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('evaluation_metrics', sa.Column('per_class_metrics', sa.JSON(), nullable=False, server_default='{}'))
    op.add_column('evaluation_metrics', sa.Column('confusion_matrix', sa.JSON(), nullable=False, server_default='{}'))
    op.add_column('evaluation_metrics', sa.Column('evaluated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.alter_column('evaluation_metrics', 'per_class_metrics', server_default=None)
    op.alter_column('evaluation_metrics', 'confusion_matrix', server_default=None)
    op.alter_column('evaluation_metrics', 'evaluated_at', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('evaluation_metrics', 'evaluated_at')
    op.drop_column('evaluation_metrics', 'confusion_matrix')
    op.drop_column('evaluation_metrics', 'per_class_metrics')
