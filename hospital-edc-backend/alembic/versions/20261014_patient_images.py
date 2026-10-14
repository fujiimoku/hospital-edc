"""Patient images and treatment subgroups; preserve existing data and group keys."""
from alembic import op
import sqlalchemy as sa

revision = 'images_20261014'
down_revision = 'crf_20261012'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if 'study_subgroup' not in {c['name'] for c in sa.inspect(bind).get_columns('patients')}:
        op.add_column('patients', sa.Column('study_subgroup', sa.String(32), nullable=True))
    if 'patient_images' not in sa.inspect(bind).get_table_names():
        op.create_table('patient_images',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('patient_id', sa.Integer(), sa.ForeignKey('patients.id'), nullable=False),
            sa.Column('storage_key', sa.String(64), unique=True, nullable=False),
            sa.Column('media_type', sa.String(32), nullable=False),
            sa.Column('size_bytes', sa.Integer(), nullable=False),
            sa.Column('sha256', sa.String(64), nullable=False),
            sa.Column('uploaded_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False))
    if 'ix_patient_images_patient_id' not in {i['name'] for i in sa.inspect(bind).get_indexes('patient_images')}:
        op.create_index('ix_patient_images_patient_id', 'patient_images', ['patient_id'])


def downgrade():
    raise RuntimeError('不自动删除患者图片或细分组别，请先核对数据和回退方案')
