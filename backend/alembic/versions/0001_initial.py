"""Initial Fido schema and append-only custody guard."""

from alembic import op
from app.models import Base

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, checkfirst=False)
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION fido_reject_custody_mutation() RETURNS trigger AS $$
            BEGIN
              RAISE EXCEPTION 'custody_events are append-only' USING ERRCODE = '55000';
            END;
            $$ LANGUAGE plpgsql;
            CREATE TRIGGER custody_events_append_only
            BEFORE UPDATE OR DELETE ON custody_events
            FOR EACH ROW EXECUTE FUNCTION fido_reject_custody_mutation();
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS custody_events_append_only ON custody_events")
        op.execute("DROP FUNCTION IF EXISTS fido_reject_custody_mutation()")
    Base.metadata.drop_all(bind=bind, checkfirst=True)
