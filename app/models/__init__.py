"""ORM package — import all models so metadata registers on Base."""

from app.models.base import Base
from app.models.customer import Customer
from app.models.data_source import DataSource
from app.models.insight import Insight
from app.models.metric_snapshot import MetricSnapshot
from app.models.order import Order
from app.models.order_adjustment import OrderAdjustment
from app.models.order_fulfillment import OrderFulfillment
from app.models.order_item import OrderItem
from app.models.order_transaction import OrderTransaction
from app.models.ai_campaign_log import AiCampaignLog
from app.models.merchant import Merchant
from app.models.promotion_draft import PromotionDraft
from app.models.raw_order import RawOrder
from app.models.raw_payload import RawPayload
from app.models.rule_definition import RuleDefinition
from app.models.signal_event import SignalEvent
from app.models.store import Store
from app.models.sync_session import SyncSession
from app.models.upload import Upload

__all__ = [
    "Base",
    "Upload",
    "RawOrder",
    "RawPayload",
    "Store",
    "DataSource",
    "SyncSession",
    "Customer",
    "Order",
    "OrderItem",
    "OrderAdjustment",
    "OrderTransaction",
    "OrderFulfillment",
    "AiCampaignLog",
    "Merchant",
    "MetricSnapshot",
    "SignalEvent",
    "Insight",
    "PromotionDraft",
    "RuleDefinition",
]
