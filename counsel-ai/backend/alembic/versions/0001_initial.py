"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-01-01

Creates the full production schema from the SQLAlchemy metadata. Later
migrations are hand-written deltas; this one stays in sync with models/db.py.
"""

from alembic import op

from app.models.db import Base

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
