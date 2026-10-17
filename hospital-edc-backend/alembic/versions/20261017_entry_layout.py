"""Free-text comorbidity details, preserving all historical flags."""
from alembic import op
import sqlalchemy as sa

revision = 'entry_20261017'
down_revision = 'feedback_20261016'
branch_labels = None
depends_on = None


def upgrade():
    if 'other_conditions' not in {c['name'] for c in sa.inspect(op.get_bind()).get_columns('comorbidities')}:
        op.add_column('comorbidities', sa.Column('other_conditions', sa.Text(), nullable=True))


def downgrade():
    raise RuntimeError('不自动删除医院填写的其他病情，请先核对数据和回退方案')
