"""Optional manually assigned EDC project number."""
from alembic import op
import sqlalchemy as sa

revision = 'project_number_20261109'
down_revision = 'workflow_20261022'
branch_labels = None
depends_on = None


def upgrade():
    if 'edc_project_number' not in {c['name'] for c in sa.inspect(op.get_bind()).get_columns('patients')}:
        op.add_column('patients', sa.Column('edc_project_number', sa.String(50), nullable=True))


def downgrade():
    raise RuntimeError('项目编号包含业务记录，不自动删除。回退程序时可保留此字段。')
