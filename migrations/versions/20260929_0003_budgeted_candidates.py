"""Add budgeted candidate provenance."""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260929_0003"
down_revision: str | None = "20260929_0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_columns = {column["name"] for column in inspector.get_columns("candidates")}
    existing_indexes = {index["name"] for index in inspector.get_indexes("candidates")}
    with op.batch_alter_table("candidates") as batch:
        if "method_kind" not in existing_columns:
            batch.add_column(
                sa.Column("method_kind", sa.String(32), nullable=False, server_default="classical")
            )
        if "job_id" not in existing_columns:
            batch.add_column(sa.Column("job_id", sa.String(36), nullable=True))
        if "requested_budget" not in existing_columns:
            batch.add_column(
                sa.Column("requested_budget", sa.JSON(), nullable=False, server_default="{}")
            )
        if "resolved_vertex_budget" not in existing_columns:
            batch.add_column(sa.Column("resolved_vertex_budget", sa.Integer(), nullable=True))
        if "source_mapping" not in existing_columns:
            batch.add_column(
                sa.Column("source_mapping", sa.JSON(), nullable=False, server_default="[]")
            )
        if "provenance" not in existing_columns:
            batch.add_column(
                sa.Column("provenance", sa.JSON(), nullable=False, server_default="{}")
            )
        if "diagnostics" not in existing_columns:
            batch.add_column(
                sa.Column("diagnostics", sa.JSON(), nullable=False, server_default="{}")
            )
        if "ix_candidates_job_id" not in existing_indexes:
            batch.create_index("ix_candidates_job_id", ["job_id"])
        if "ix_candidates_resolved_vertex_budget" not in existing_indexes:
            batch.create_index("ix_candidates_resolved_vertex_budget", ["resolved_vertex_budget"])

    rows = connection.execute(sa.text("SELECT id, parameters FROM candidates")).mappings()
    for row in rows:
        parameters = row["parameters"]
        if isinstance(parameters, str):
            parameters = json.loads(parameters)
        vertex_budget = (parameters or {}).get("vertex_budget")
        if vertex_budget is None:
            continue
        connection.execute(
            sa.text(
                "UPDATE candidates SET requested_budget = :requested, "
                "resolved_vertex_budget = :resolved WHERE id = :id"
            ),
            {
                "id": row["id"],
                "requested": json.dumps({"kind": "vertex-count", "value": vertex_budget}),
                "resolved": vertex_budget,
            },
        )


def downgrade() -> None:
    with op.batch_alter_table("candidates") as batch:
        batch.drop_index("ix_candidates_resolved_vertex_budget")
        batch.drop_index("ix_candidates_job_id")
        batch.drop_column("diagnostics")
        batch.drop_column("provenance")
        batch.drop_column("source_mapping")
        batch.drop_column("resolved_vertex_budget")
        batch.drop_column("requested_budget")
        batch.drop_column("job_id")
        batch.drop_column("method_kind")
