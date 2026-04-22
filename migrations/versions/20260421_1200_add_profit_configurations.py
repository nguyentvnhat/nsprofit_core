# core/migrations/versions/20250421_1200_add_profit_configurations.py
"""Add profit_configurations table

Revision ID: 20250421_1200
Revises: (previous_revision_id)
Create Date: 2026-04-21 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import JSON

# revision identifiers, used by Alembic.
revision = '20250421_1200'
down_revision = None  # Replace with your previous revision ID
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create profit_configurations table
    op.create_table(
        'profit_configurations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('store_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False, server_default='Default'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='0'),
        
        # COGS
        sa.Column('cogs_mode', sa.String(length=32), nullable=True),
        sa.Column('cogs_value', sa.Float(), nullable=True),
        
        # Shipping
        sa.Column('shipping_mode', sa.String(length=32), nullable=True),
        sa.Column('shipping_value', sa.Float(), nullable=True),
        
        # Transaction fees
        sa.Column('transaction_fee_mode', sa.String(length=32), nullable=True),
        sa.Column('transaction_fee_value', sa.Float(), nullable=True),
        
        # Custom costs
        sa.Column('custom_costs', JSON, nullable=True),
        
        # Metadata
        sa.Column('completeness', sa.String(length=32), nullable=False, server_default='basic'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'), nullable=False),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
    )
    
    # Create indexes
    op.create_index('ix_profit_configurations_store_id', 'profit_configurations', ['store_id'])
    op.create_index('ix_profit_configurations_is_default', 'profit_configurations', ['is_default'])
    
    # Add profit_configuration_id to stores? (optional)
    # op.add_column('stores', sa.Column('default_profit_configuration_id', sa.Integer(), nullable=True))
    # op.create_foreign_key('fk_stores_profit_configuration', 'stores', 'profit_configurations', ['default_profit_configuration_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    # op.drop_constraint('fk_stores_profit_configuration', 'stores', type_='foreignkey')
    # op.drop_column('stores', 'default_profit_configuration_id')
    op.drop_index('ix_profit_configurations_is_default', table_name='profit_configurations')
    op.drop_index('ix_profit_configurations_store_id', table_name='profit_configurations')
    op.drop_table('profit_configurations')