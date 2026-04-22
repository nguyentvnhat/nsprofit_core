# core/services/profit_configuration_service.py
from sqlalchemy.orm import Session
from app.models.profit_configuration import ProfitConfiguration
from app.models.store import Store

def get_profit_configuration(
    db: Session,
    store_id: int,
    config_id: int | None = None,
) -> ProfitConfiguration | None:
    """Get profit configuration for a store."""
    if config_id:
        return db.query(ProfitConfiguration).filter(
            ProfitConfiguration.id == config_id,
            ProfitConfiguration.store_id == store_id,
        ).first()
    
    # Return default configuration for store
    return db.query(ProfitConfiguration).filter(
        ProfitConfiguration.store_id == store_id,
        ProfitConfiguration.is_default == True,
    ).first()


def create_profit_configuration(
    db: Session,
    store_id: int,
    name: str,
    cogs_mode: str | None = None,
    cogs_value: float | None = None,
    shipping_mode: str | None = None,
    shipping_value: float | None = None,
    transaction_fee_mode: str | None = None,
    transaction_fee_value: float | None = None,
    custom_costs: list | None = None,
    is_default: bool = False,
) -> ProfitConfiguration:
    """Create a new profit configuration."""
    config = ProfitConfiguration(
        store_id=store_id,
        name=name,
        cogs_mode=cogs_mode,
        cogs_value=cogs_value,
        shipping_mode=shipping_mode,
        shipping_value=shipping_value,
        transaction_fee_mode=transaction_fee_mode,
        transaction_fee_value=transaction_fee_value,
        custom_costs=custom_costs,
        is_default=is_default,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def update_profit_configuration(
    db: Session,
    config_id: int,
    **kwargs,
) -> ProfitConfiguration | None:
    """Update an existing profit configuration."""
    config = db.query(ProfitConfiguration).filter(ProfitConfiguration.id == config_id).first()
    if not config:
        return None
    
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
    
    db.commit()
    db.refresh(config)
    return config


def delete_profit_configuration(db: Session, config_id: int) -> bool:
    """Delete a profit configuration."""
    config = db.query(ProfitConfiguration).filter(ProfitConfiguration.id == config_id).first()
    if not config:
        return False
    
    db.delete(config)
    db.commit()
    return True


def set_default_configuration(db: Session, store_id: int, config_id: int) -> ProfitConfiguration | None:
    """Set a configuration as default for the store."""
    # Remove default from all other configs
    db.query(ProfitConfiguration).filter(
        ProfitConfiguration.store_id == store_id,
        ProfitConfiguration.is_default == True,
    ).update({"is_default": False})
    
    # Set new default
    config = db.query(ProfitConfiguration).filter(
        ProfitConfiguration.id == config_id,
        ProfitConfiguration.store_id == store_id,
    ).first()
    
    if config:
        config.is_default = True
        db.commit()
        db.refresh(config)
    
    return config