"""TrackCall table

Revision ID: 83fcbeb5dcd4
Revises: 18bfff6fee6c
Create Date: 2021-07-13 19:02:22.599242

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '83fcbeb5dcd4'
down_revision = '18bfff6fee6c'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('track_call',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('call_id', sa.String(length=64), nullable=False),
    sa.Column('call_from', sa.String(length=15), nullable=False),
    sa.Column('call_to', sa.String(length=15), nullable=False),
    sa.Column('number_context', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    mysql_charset='utf8',
    mysql_engine='InnoDB'
    )
    op.create_index(op.f('ix_track_call_call_from'), 'track_call', ['call_from'], unique=False)
    op.create_index(op.f('ix_track_call_call_id'), 'track_call', ['call_id'], unique=False)
    op.create_index(op.f('ix_track_call_created_at'), 'track_call', ['created_at'], unique=False)
    op.drop_index('ix_pool_created_at', table_name='pools')
    op.create_index(op.f('ix_pools_created_at'), 'pools', ['created_at'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_pools_created_at'), table_name='pools')
    op.create_index('ix_pool_created_at', 'pools', ['created_at'], unique=False)
    op.drop_index(op.f('ix_track_call_created_at'), table_name='track_call')
    op.drop_index(op.f('ix_track_call_call_id'), table_name='track_call')
    op.drop_index(op.f('ix_track_call_call_from'), table_name='track_call')
    op.drop_table('track_call')
    # ### end Alembic commands ###
