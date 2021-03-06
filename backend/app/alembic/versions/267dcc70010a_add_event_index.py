"""Add event index

Revision ID: 267dcc70010a
Revises: b133fdee97b8
Create Date: 2020-10-27 18:12:09.012343

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '267dcc70010a'
down_revision = 'b133fdee97b8'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index(op.f('ix_track_event'), 'track', ['event'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_track_event'), table_name='track')
    # ### end Alembic commands ###
