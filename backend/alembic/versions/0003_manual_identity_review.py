"""Add shelter-operated identity review and reconciliation candidates."""

from sqlalchemy import Column, String, Uuid, inspect

from alembic import op
from app.models import IdentityMatchCandidate

revision = "0003_manual_identity_review"
down_revision = "0002_stripe_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("identity_inquiries")}
    additions = (
        Column("reviewing_shelter_id", Uuid, nullable=True),
        Column("submitted_by_user_id", String(200), nullable=True),
        Column("submitted_display_name", String(200), nullable=True),
        Column("match_classification", String(40), nullable=True),
    )
    with op.batch_alter_table("identity_inquiries") as batch:
        for column in additions:
            if column.name not in columns:
                batch.add_column(column)
    foreign_keys = inspect(bind).get_foreign_keys("identity_inquiries")
    has_shelter_foreign_key = any(
        constraint.get("constrained_columns") == ["reviewing_shelter_id"]
        and constraint.get("referred_table") == "shelters"
        for constraint in foreign_keys
    )
    if not has_shelter_foreign_key:
        with op.batch_alter_table("identity_inquiries") as batch:
            batch.create_foreign_key(
                "fk_identity_inquiries_reviewing_shelter",
                "shelters",
                ["reviewing_shelter_id"],
                ["id"],
                ondelete="RESTRICT",
            )
    indexes = {index["name"] for index in inspect(bind).get_indexes("identity_inquiries")}
    if "ix_identity_inquiries_reviewing_shelter_id" not in indexes:
        op.create_index(
            "ix_identity_inquiries_reviewing_shelter_id",
            "identity_inquiries",
            ["reviewing_shelter_id"],
        )

    constraints = {
        constraint["name"]
        for constraint in inspect(bind).get_unique_constraints("identity_signals")
    }
    if "uq_identity_signal_inquiry_type" in constraints:
        with op.batch_alter_table("identity_signals") as batch:
            batch.drop_constraint("uq_identity_signal_inquiry_type", type_="unique")
    if "uq_identity_signal_inquiry_type_value" not in constraints:
        with op.batch_alter_table("identity_signals") as batch:
            batch.create_unique_constraint(
                "uq_identity_signal_inquiry_type_value",
                ["identity_inquiry_id", "signal_type", "value_hash"],
            )
    IdentityMatchCandidate.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    IdentityMatchCandidate.__table__.drop(bind=bind, checkfirst=True)
    constraints = {
        constraint["name"]
        for constraint in inspect(bind).get_unique_constraints("identity_signals")
    }
    with op.batch_alter_table("identity_signals") as batch:
        if "uq_identity_signal_inquiry_type_value" in constraints:
            batch.drop_constraint("uq_identity_signal_inquiry_type_value", type_="unique")
        batch.create_unique_constraint(
            "uq_identity_signal_inquiry_type", ["identity_inquiry_id", "signal_type"]
        )
    indexes = {index["name"] for index in inspect(bind).get_indexes("identity_inquiries")}
    if "ix_identity_inquiries_reviewing_shelter_id" in indexes:
        op.drop_index("ix_identity_inquiries_reviewing_shelter_id", table_name="identity_inquiries")
    for name in (
        "match_classification",
        "submitted_display_name",
        "submitted_by_user_id",
        "reviewing_shelter_id",
    ):
        op.drop_column("identity_inquiries", name)
