"""Patient-level follow-up labels, independent of visit approval."""
from alembic import op
import sqlalchemy as sa

revision = 'workflow_20261022'
down_revision = 'entry_20261017'
branch_labels = None
depends_on = None


def upgrade():
    if 'tracking_status' not in {c['name'] for c in sa.inspect(op.get_bind()).get_columns('patients')}:
        op.add_column('patients', sa.Column('tracking_status', sa.String(16), nullable=False, server_default='pending'))


def downgrade():
    raise RuntimeError('追踪标签包含业务记录，不自动删除，请先核对回退方案')
