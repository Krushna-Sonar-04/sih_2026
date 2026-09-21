"""local auth users, cached post embeddings, audit hash chain

Revision ID: 0002_auth_embeddings
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_auth_embeddings"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_user",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("email", sa.String(length=200), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_app_user_email", "app_user", ["email"], unique=True)

    op.create_table(
        "post_embedding",
        sa.Column("post_id", sa.String(length=80), nullable=False),
        sa.Column("watch_id", sa.String(length=80), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("vector", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["post.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("post_id"),
    )
    op.create_index("ix_post_embedding_watch_id", "post_embedding", ["watch_id"])

    op.add_column("audit_event", sa.Column("prev_hash", sa.String(length=64), nullable=False, server_default=""))
    op.add_column("audit_event", sa.Column("record_hash", sa.String(length=64), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("audit_event", "record_hash")
    op.drop_column("audit_event", "prev_hash")
    op.drop_index("ix_post_embedding_watch_id", table_name="post_embedding")
    op.drop_table("post_embedding")
    op.drop_index("ix_app_user_email", table_name="app_user")
    op.drop_table("app_user")
