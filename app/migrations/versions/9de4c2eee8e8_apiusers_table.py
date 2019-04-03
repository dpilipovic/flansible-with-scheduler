"""apiusers table

Revision ID: 9de4c2eee8e8
Revises: 
Create Date: 2019-03-01 19:25:00.558062

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9de4c2eee8e8'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('apiusers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=64), nullable=False),
    sa.Column('email', sa.String(length=120), nullable=False),
    sa.Column('password_hash', sa.String(length=128), nullable=True),
    sa.Column('notify', sa.Boolean(), nullable=False),
    sa.Column('ldap_user', sa.String(length=64), nullable=True),
    sa.Column('created', sa.DateTime(), nullable=True),
    sa.Column('updated', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_apiusers_email'), 'apiusers', ['email'], unique=False)
    op.create_index(op.f('ix_apiusers_username'), 'apiusers', ['username'], unique=True)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_apiusers_username'), table_name='apiusers')
    op.drop_index(op.f('ix_apiusers_email'), table_name='apiusers')
    op.drop_table('apiusers')
    # ### end Alembic commands ###
