# core/models/profit_configuration.py
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Boolean, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .base import Base

class ProfitConfiguration(Base):
    """Lưu cấu hình profit (COGS, shipping, fees) cho từng store."""
    __tablename__ = "profit_configurations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(Integer, ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False, default="Default")
    is_default = Column(Boolean, default=False, index=True)
    
    # COGS configuration
    cogs_mode = Column(String(32), nullable=True)  # 'percentage', 'fixed', 'none'
    cogs_value = Column(Float, nullable=True)  # percentage (0-100) or fixed amount
    
    # Shipping costs
    shipping_mode = Column(String(32), nullable=True)  # 'percentage', 'fixed', 'none'
    shipping_value = Column(Float, nullable=True)
    
    # Transaction fees
    transaction_fee_mode = Column(String(32), nullable=True)  # 'percentage', 'fixed', 'none'
    transaction_fee_value = Column(Float, nullable=True)
    
    # Custom costs (JSON)
    custom_costs = Column(JSON, nullable=True)  # [{"name": "handling", "type": "fixed", "value": 2.00}, ...]
    
    # Completeness level
    completeness = Column(String(32), default="basic")  # 'basic', 'partial', 'complete'
    
    # Metadata
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    store = relationship("Store", back_populates="profit_configurations")

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict for API."""
        return {
            "id": self.id,
            "store_id": self.store_id,
            "name": self.name,
            "is_default": self.is_default,
            "cogs": {
                "mode": self.cogs_mode,
                "value": self.cogs_value,
            },
            "shipping_costs": {
                "mode": self.shipping_mode,
                "value": self.shipping_value,
            },
            "transaction_fees": {
                "mode": self.transaction_fee_mode,
                "value": self.transaction_fee_value,
            },
            "custom_costs": self.custom_costs or [],
            "completeness": self.completeness,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def to_profit_config_json(self) -> dict:
        """Convert to format expected by discount_recommendation_service."""
        return {
            "cogs": {
                "mode": self.cogs_mode or "none",
                "value": self.cogs_value or 0,
            },
            "shipping_costs": {
                "mode": self.shipping_mode or "none",
                "value": self.shipping_value or 0,
            },
            "transaction_fees": {
                "mode": self.transaction_fee_mode or "none",
                "value": self.transaction_fee_value or 0,
            },
            "custom_costs": self.custom_costs or [],
        }


# Cập nhật Store model (thêm relationship)
# core/models/store.py
"""
Thêm vào class Store:
    profit_configurations = relationship("ProfitConfiguration", back_populates="store")
"""