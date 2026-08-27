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
    """Upgrade schema.

    Three steps rather than one. The original version added the column as
    NOT NULL with no default, on the assumption -- stated in a comment -- that
    the users table was empty everywhere this would ever run. That assumption
    held once and is not a property of the migration. Verified by replaying
    the chain against a database with a single user row:

        Running upgrade 53b8feed0825 -> e96f48ad79fb, add users.password_hash
        psycopg2.errors.NotNullViolation: column "password_hash" of relation
        "users" contains null values

    i.e. anyone restoring a backup taken before this revision could not
    upgrade at all. The add-nullable / backfill / set-not-null pattern below
    works on an empty table and on a populated one.

    Backfilling with '' is deliberate: rows predating this migration never had
    a password, so no value could be correct. An empty hash matches nothing
    (backend/auth.py's verify_password returns False for it rather than
    raising), which leaves those accounts unable to sign in until a password
    is set -- the honest outcome, and better than inventing a credential.
    """
    op.add_column('users', sa.Column('password_hash', sa.String(length=255), nullable=True))
    op.execute("UPDATE users SET password_hash = '' WHERE password_hash IS NULL")
    op.alter_column('users', 'password_hash', existing_type=sa.String(length=255), nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'password_hash')
