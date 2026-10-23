"""Enforce one administrator in databases created before the staff role guard.

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if 'admin_slot' in {column['name'] for column in sa.inspect(bind).get_columns('users')}:
        return  # The initial migration created the current schema for a fresh database.
    if bind.execute(sa.text("SELECT COUNT(*) FROM users WHERE role = 'admin'")).scalar_one() > 1:
        raise RuntimeError('Resolve duplicate administrators before applying the single-admin migration')
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('admin_slot', sa.Integer(), nullable=True))
    bind.execute(sa.text("UPDATE users SET admin_slot = 1 WHERE role = 'admin'"))
    with op.batch_alter_table('users') as batch:
        batch.create_unique_constraint('uq_users_admin_slot', ['admin_slot'])
        batch.create_check_constraint('ck_users_staff_role',
            "(role = 'admin' AND admin_slot = 1) OR (role = 'teacher' AND admin_slot IS NULL)")


def downgrade():
    if 'admin_slot' not in {column['name'] for column in sa.inspect(op.get_bind()).get_columns('users')}:
        return
    with op.batch_alter_table('users') as batch:
        batch.drop_constraint('ck_users_staff_role', type_='check')
        batch.drop_constraint('uq_users_admin_slot', type_='unique')
        batch.drop_column('admin_slot')
