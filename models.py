from typing import Any, Literal, Optional
from pydantic import Field
from openenv.core.env_server.types import Action, Observation, State


class AeomAction(Action):
    action: Literal[
        "request_customer_info",
        "query_database",
        "calculate_total",
        "execute_resolution",
    ]
    field: Optional[Literal["order_id", "email", "reason", "photo_evidence", "delivery_address"]] = None
    collection: Optional[Literal["orders", "customers", "products"]] = None
    query: Optional[dict[str, Any]] = None
    base_price: Optional[float] = None
    extra_fees: Optional[float] = None
    resolution: Optional[Literal["refund", "reship", "deny"]] = None
    amount: Optional[float] = None
    wallet: Optional[Literal["source", "store_credit"]] = None
    reason: Optional[str] = None


class AeomObservation(Observation):
    ticket_status: Literal["open", "pending_customer", "pending_db", "resolved", "denied", "failed"] = "open"
    customer_reply: Optional[str] = None
    db_result: Optional[dict[str, Any]] = None
    error_log: Optional[str] = None
    steps_taken: int = 0
    final_score: Optional[float] = None
    policy_snapshot: dict = Field(default_factory=lambda: {
        "return_window_days": 7,
        "photo_evidence_required_for": ["damaged", "tampered"],
        "refund_wallet_options": ["source", "store_credit"],
        "delivery_fee_refundable": True,
        "platform_fee_refundable": False,
    })


class AeomState(State):
    task_name: str = ""
    order_id: Optional[str] = None
    customer_email: Optional[str] = None
    customer_name: Optional[str] = None
    item_name: Optional[str] = None
    base_price: float = 0.0
    delivery_fee: float = 0.0
    order_date: Optional[str] = None
    delivery_status: str = ""
    complaint_reason: str = ""
    collected_fields: list[str] = Field(default_factory=list)
    action_history: list[dict] = Field(default_factory=list)
    photo_evidence_provided: bool = False
    resolution_issued: bool = False
    cumulative_reward: float = 0.0
