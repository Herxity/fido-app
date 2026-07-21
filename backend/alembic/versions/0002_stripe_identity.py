"""Add Stripe Identity provider fields and privacy-preserving match signals."""

from sqlalchemy import Column, String, inspect, text

from alembic import op
from app.models import IdentitySignal

revision = "0002_stripe_identity"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("identity_inquiries")}
    if "provider" not in columns:
        op.add_column(
            "identity_inquiries",
            Column("provider", String(30), nullable=True, server_default="stripe"),
        )
    if "provider_session_id" not in columns:
        op.add_column(
            "identity_inquiries", Column("provider_session_id", String(200), nullable=True)
        )
    if "provider_report_id" not in columns:
        op.add_column(
            "identity_inquiries", Column("provider_report_id", String(200), nullable=True)
        )
    if "persona_inquiry_id" in columns:
        bind.execute(
            text(
                "UPDATE identity_inquiries SET provider = 'persona', "
                "provider_session_id = persona_inquiry_id, "
                "provider_report_id = workflow_reference "
                "WHERE provider_session_id IS NULL"
            )
        )
    if bind.dialect.name == "postgresql":
        if "persona_inquiry_id" in columns:
            op.alter_column("identity_inquiries", "persona_inquiry_id", nullable=True)
        op.alter_column("identity_inquiries", "provider", nullable=False)
        op.alter_column("identity_inquiries", "provider_session_id", nullable=False)
    indexes = {index["name"] for index in inspect(bind).get_indexes("identity_inquiries")}
    if "uq_identity_inquiries_provider_session_id" not in indexes:
        op.create_index(
            "uq_identity_inquiries_provider_session_id",
            "identity_inquiries",
            ["provider_session_id"],
            unique=True,
        )
    IdentitySignal.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    IdentitySignal.__table__.drop(bind=bind, checkfirst=True)
    columns = {column["name"] for column in inspect(bind).get_columns("identity_inquiries")}
    indexes = {index["name"] for index in inspect(bind).get_indexes("identity_inquiries")}
    if "uq_identity_inquiries_provider_session_id" in indexes:
        op.drop_index("uq_identity_inquiries_provider_session_id", table_name="identity_inquiries")
    for name in ("provider_report_id", "provider_session_id", "provider"):
        if name in columns:
            op.drop_column("identity_inquiries", name)
