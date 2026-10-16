"""Associate newly uploaded cost photos with a visit; keep old patient archives."""
from alembic import op
import sqlalchemy as sa

revision = 'feedback_20261016'
down_revision = 'images_20261014'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if 'visit_id' not in {c['name'] for c in sa.inspect(bind).get_columns('patient_images')}:
        with op.batch_alter_table('patient_images') as batch:
            batch.add_column(sa.Column('visit_id', sa.Integer(), nullable=True))
    if not any(f['constrained_columns'] == ['visit_id'] and f['referred_table'] == 'visits' for f in sa.inspect(bind).get_foreign_keys('patient_images')):
        with op.batch_alter_table('patient_images') as batch:
            batch.create_foreign_key('fk_patient_images_visit_id', 'visits', ['visit_id'], ['id'])
    if 'ix_patient_images_visit_id' not in {i['name'] for i in sa.inspect(bind).get_indexes('patient_images')}:
        op.create_index('ix_patient_images_visit_id', 'patient_images', ['visit_id'])


def downgrade():
    raise RuntimeError('费用照片已关联访视，请核对数据后制定回退方案')
