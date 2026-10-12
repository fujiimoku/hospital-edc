"""Add CRF fields without reinterpreting historical values.

Revision ID: crf_20261012
Revises: 49e1ff22eafe
"""
from alembic import op
import sqlalchemy as sa

revision = "crf_20261012"
down_revision = "49e1ff22eafe"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    additions = {
        "cost_indicators": [("crf_version", sa.Integer())],
        "questionnaires": [("crf_version", sa.Integer())],
        "patients": [("study_group", sa.String(32)), ("smoking_history", sa.Integer()),
                     ("drinking_history", sa.Integer())],
        "comorbidities": [("hypertension_cause", sa.String(500)), ("ckd_cause", sa.String(500))],
    }
    for table, fields in additions.items():
        existing = {c["name"] for c in sa.inspect(bind).get_columns(table)}
        for name, type_ in fields:
            if name not in existing:
                op.add_column(table, sa.Column(name, type_, nullable=True))
    indexes = {i["name"] for i in sa.inspect(bind).get_indexes("patients")}
    if "ix_patients_study_group" not in indexes:
        op.create_index("ix_patients_study_group", "patients", ["study_group"])
    if "followup_safety" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "followup_safety",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("visit_id", sa.Integer(), sa.ForeignKey("visits.id"), nullable=False, unique=True),
            sa.Column("hypoglycemia", sa.Integer(), nullable=True),
            *(sa.Column(k, sa.Boolean(), nullable=True) for k in
              ("symptomatic", "nocturnal", "severe", "gastrointestinal", "allergy")),
            sa.Column("other", sa.Text(), nullable=True),
        )
    if bind.dialect.name == "mysql":
        op.alter_column("visits", "visit_type",
                        existing_type=sa.Enum("baseline", "M6", "M12", "M18", "M24"),
                        type_=sa.Enum("baseline", "W12", "W26", "interim", "M6", "M12", "M18", "M24"),
                        existing_nullable=False)


def downgrade():
    raise RuntimeError("此迁移保留研究数据，不自动删除新增字段；回退应用前请核对新访视类型。")
