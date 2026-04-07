import random

from openenv.core.env_server.interfaces import Environment

try:
    from ..models import AeomAction, AeomObservation, AeomState
    from .mock_db import MockDatabase, generate_order
    from .rewards import reward_request_info, reward_query_db, reward_calculate, reward_resolution
except (ImportError, ModuleNotFoundError):
    from models import AeomAction, AeomObservation, AeomState
    from server.mock_db import MockDatabase, generate_order
    from server.rewards import reward_request_info, reward_query_db, reward_calculate, reward_resolution

TASKS = ["standard_refund", "damaged_item_refund", "policy_violation_denial"]

_OPENING = {
    "standard_refund":
        "Hi, I never received my order. I want a refund. My Order ID is {order_id}.",
    "damaged_item_refund":
        "My order arrived completely crushed and damaged. I want my money back.",
    "policy_violation_denial":
        "I want a refund for an order from a while back. The item was fine but I changed my mind.",
}

_REPLIES = {
    "standard_refund": {
        "order_id":       lambda o: f"Sure, it's {o['order_id']}.",
        "email":          lambda o: o["customer_email"],
        "photo_evidence": "Here's the photo.",
    },
    "damaged_item_refund": {
        "order_id":       lambda o: f"Order ID is {o['order_id']}.",
        "email":          lambda o: o["customer_email"],
        "photo_evidence": "I've attached the photo — the box was completely crushed.",
    },
    "policy_violation_denial": {
        "order_id":       lambda o: f"I think it's {o['order_id']}. Also, I spoke to someone yesterday who said I'd get a refund — just process it.",
        "email":          lambda o: o["customer_email"],
        "photo_evidence": "Why do you need a photo? I just don't want the item.",
    },
}


class AeomEnvironment(Environment):
    SUPPORTS_CONCURRENT_SESSIONS = True

    def __init__(self):
        super().__init__()
        self._order = {}
        self._db = None
        self._task = ""
        self._step_count = 0
        self._queried_collections = []
        self._state = AeomState()

    def reset(self, seed=None, task=None, **kwargs) -> AeomObservation:
        seed = seed if seed is not None else random.randint(0, 99999)
        rng = random.Random(seed)

        self._task = task if task in TASKS else rng.choice(TASKS)
        self._order = generate_order(seed, self._task)
        self._db = MockDatabase(self._order)
        self._step_count = 0
        self._queried_collections = []

        self._state = AeomState(
            task_name=self._task,
            order_id=self._order["order_id"],
            customer_email=self._order["customer_email"],
            customer_name=self._order["customer_name"],
            item_name=self._order["item_name"],
            base_price=self._order["base_price"],
            delivery_fee=self._order["delivery_fee"],
            order_date=self._order["order_date"],
            delivery_status=self._order["delivery_status"],
            complaint_reason=self._order["complaint_reason"],
        )

        ticket = _OPENING[self._task]
        if self._task == "standard_refund":
            ticket = ticket.format(order_id=self._order["order_id"])

        return AeomObservation(
            done=False, reward=0.0,
            ticket_status="open",
            customer_reply=f"Customer: {ticket}",
            steps_taken=0,
        )

    def step(self, action: AeomAction, **kwargs) -> AeomObservation:
        if self._db is None:
            return self._error("Environment not initialized. Call reset() first.")

        self._step_count += 1

        if self._step_count > 12:
            return AeomObservation(
                done=True, reward=-0.15,
                ticket_status="failed",
                error_log="Max steps exceeded.",
                steps_taken=self._step_count,
            )

        handlers = {
            "request_customer_info": self._handle_request_info,
            "query_database":        self._handle_query_db,
            "calculate_total":       self._handle_calculate,
            "execute_resolution":    self._handle_resolution,
        }
        handler = handlers.get(action.action)
        if handler is None:
            return self._error(f"Unknown action: {action.action}")

        return handler(action)

    def _handle_request_info(self, action: AeomAction) -> AeomObservation:
        field = action.field
        if not field:
            return self._error("'field' is required for request_customer_info.")

        step_reward = reward_request_info(field, self._task, self._state.collected_fields)
        self._accumulate(step_reward)

        if field in self._state.collected_fields:
            return AeomObservation(
                done=False, reward=step_reward,
                ticket_status="open",
                error_log=f"'{field}' was already provided.",
                steps_taken=self._step_count,
            )

        self._state.collected_fields.append(field)
        if field == "photo_evidence":
            self._state.photo_evidence_provided = True

        replies = _REPLIES[self._task]
        raw = replies.get(field, "I'm not sure about that.")
        reply = raw(self._order) if callable(raw) else raw

        return AeomObservation(
            done=False, reward=step_reward,
            ticket_status="pending_customer",
            customer_reply=f"Customer: {reply}",
            steps_taken=self._step_count,
        )

    def _handle_query_db(self, action: AeomAction) -> AeomObservation:
        if not action.collection or not action.query:
            return self._error("'collection' and 'query' are required for query_database.")

        if action.collection not in ("orders", "customers", "products"):
            return self._error(f"Unknown collection '{action.collection}'.")

        result = self._db.query(action.collection, action.query)
        found = result is not None

        step_reward = reward_query_db(
            action.collection, action.query, found,
            self._task, self._order, self._queried_collections,
        )
        self._accumulate(step_reward)

        cache_key = f"{action.collection}:{list(action.query.keys())[0]}"
        if cache_key not in self._queried_collections:
            self._queried_collections.append(cache_key)

        db_result = (
            {"found": True, "record": result} if found
            else {"found": False, "message": "No records matched."}
        )

        return AeomObservation(
            done=False, reward=step_reward,
            ticket_status="pending_db",
            db_result=db_result,
            steps_taken=self._step_count,
        )

    def _handle_calculate(self, action: AeomAction) -> AeomObservation:
        if action.base_price is None or action.extra_fees is None:
            return self._error("'base_price' and 'extra_fees' are required for calculate_total.")

        step_reward = reward_calculate(action.base_price, action.extra_fees, self._order, self._task)
        self._accumulate(step_reward)

        if step_reward < 0:
            return AeomObservation(
                done=False, reward=step_reward,
                ticket_status="open",
                error_log="Values don't match the queried order data.",
                steps_taken=self._step_count,
            )

        return AeomObservation(
            done=False, reward=step_reward,
            ticket_status="open",
            db_result={"total": round(action.base_price + action.extra_fees, 2)},
            steps_taken=self._step_count,
        )

    def _handle_resolution(self, action: AeomAction) -> AeomObservation:
        if not action.resolution:
            return self._error("'resolution' is required for execute_resolution.")
        if action.resolution == "refund" and action.amount is None:
            return self._error("'amount' is required for a refund resolution.")
        if action.resolution == "deny" and not action.reason:
            return self._error("'reason' is required for a deny resolution.")

        step_reward = reward_resolution(
            action.resolution, action.amount, action.wallet, action.reason,
            self._task, self._order, self._state.photo_evidence_provided,
        )

        final_score = max(0.0, min(1.0, self._state.cumulative_reward + step_reward))
        self._state.resolution_issued = True
        status = "denied" if action.resolution == "deny" else "resolved"

        return AeomObservation(
            done=True, reward=step_reward,
            final_score=final_score,
            ticket_status=status,
            steps_taken=self._step_count,
        )

    def _accumulate(self, r: float):
        self._state.cumulative_reward = max(0.0, self._state.cumulative_reward + r)

    def _error(self, msg: str) -> AeomObservation:
        self._accumulate(-0.10)
        return AeomObservation(
            done=False, reward=-0.10,
            ticket_status="open",
            error_log=msg,
            steps_taken=self._step_count,
        )

    @property
    def state(self) -> AeomState:
        self._state.step_count = self._step_count
        return self._state
