"""Add contextual scenes and reviews."""

from collections.abc import Sequence

from alembic import op

revision: str = "20260929_0002"
down_revision: str | None = "20260928_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    from geoscalex.storage.models import Base

    connection = op.get_bind()
    tables = ["scenes", "scene_features", "scene_reviews"]
    Base.metadata.create_all(
        bind=connection,
        checkfirst=True,
        tables=[Base.metadata.tables[table] for table in tables],
    )


def downgrade() -> None:
    from geoscalex.storage.models import Base

    connection = op.get_bind()
    tables = ["scene_reviews", "scene_features", "scenes"]
    Base.metadata.drop_all(
        bind=connection,
        checkfirst=True,
        tables=[Base.metadata.tables[table] for table in tables],
    )
