import random
from datetime import datetime, timedelta

PRODUCTS = [
    {"item_name": "Amul Butter 500g",    "base_price": 289.0, "category": "dairy"},
    {"item_name": "Parle-G Biscuits",    "base_price":  30.0, "category": "snacks"},
    {"item_name": "Surf Excel 1kg",      "base_price": 215.0, "category": "household"},
    {"item_name": "Maggi Noodles 12pk",  "base_price": 192.0, "category": "food"},
    {"item_name": "Colgate Toothpaste",  "base_price":  99.0, "category": "personal_care"},
]

DELIVERY_FEE = 29.0
NAMES = ["Rahul Mehta", "Priya Singh", "Arjun Sharma", "Neha Gupta", "Vikram Rao"]

_STATUS = {
    "standard_refund":         "lost",
    "damaged_item_refund":     "delivered",
    "policy_violation_denial": "delivered",
}

_REASON = {
    "standard_refund":         "missing",
    "damaged_item_refund":     "damaged",
    "policy_violation_denial": "change_of_mind",
}

_DAYS_AGO = {
    "standard_refund":         (2, 6),
    "damaged_item_refund":     (3, 6),
    "policy_violation_denial": (8, 10),   # violates 7-day policy
}


def generate_order(seed: int, task: str) -> dict:
    rng = random.Random(seed)
    product = rng.choice(PRODUCTS)
    name = rng.choice(NAMES)
    email = name.lower().replace(" ", ".") + "@email.com"

    lo, hi = _DAYS_AGO[task]
    days_ago = rng.randint(lo, hi)
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    order_date = (today - timedelta(days=days_ago)).strftime("%Y-%m-%d")

    suffix = "".join(rng.choices("ABCDEFGHJKLMNPQRSTUVWXYZ0123456789", k=6))
    order_id = f"ZPT-{suffix}"

    return {
        "order_id":          order_id,
        "customer_name":     name,
        "customer_email":    email,
        "item_name":         product["item_name"],
        "base_price":        product["base_price"],
        "delivery_fee":      DELIVERY_FEE,
        "delivery_status":   _STATUS[task],
        "order_date":        order_date,
        "complaint_reason":  _REASON[task],
        "days_ago":          days_ago,
    }


class MockDatabase:
    def __init__(self, order: dict):
        self._order = order

    def query(self, collection: str, query: dict) -> dict | None:
        if collection == "orders":
            key, value = next(iter(query.items()))
            if key in ("order_id", "customer_email") and self._order.get(key) == value:
                return {k: v for k, v in self._order.items() if k != "days_ago"}
            return None

        if collection == "customers":
            key, value = next(iter(query.items()))
            if key == "email" and value == self._order["customer_email"]:
                return {
                    "customer_id":   f"CUST-{abs(hash(value)) % 90000 + 10000}",
                    "name":          self._order["customer_name"],
                    "email":         self._order["customer_email"],
                    "order_history": [self._order["order_id"]],
                }
            return None

        if collection == "products":
            key, value = next(iter(query.items()))
            if key == "item_name" and value == self._order["item_name"]:
                return {
                    "item_name":    self._order["item_name"],
                    "base_price":   self._order["base_price"],
                    "delivery_fee": self._order["delivery_fee"],
                }
            return None

        return None
