def grade_standard_refund(history: list[dict], order: dict) -> float:
    score = 0.0

    if any(
        a["action"] == "query_database"
        and a.get("collection") == "orders"
        and a.get("query", {}).get("order_id") == order["order_id"]
        for a in history
    ):
        score += 0.15

    res = next((a for a in history if a["action"] == "execute_resolution"), None)
    if res:
        if res.get("resolution") == "refund":
            score += 0.35
        if res.get("amount") is not None and abs(res["amount"] - order["base_price"]) <= 1.0:
            score += 0.30
        if res.get("wallet") == "source":
            score += 0.10

    # asked for photo on a missing-item ticket — not needed
    if any(
        a["action"] == "request_customer_info" and a.get("field") == "photo_evidence"
        for a in history
    ):
        score -= 0.10

    return max(0.0, min(1.0, score))


def grade_damaged_item(history: list[dict], order: dict) -> float:
    score = 0.0
    expected_total = order["base_price"] + order["delivery_fee"]

    if any(a["action"] == "request_customer_info" and a.get("field") == "order_id" for a in history):
        score += 0.10

    if any(a["action"] == "query_database" and a.get("collection") == "orders" for a in history):
        score += 0.15

    photo_idx = next(
        (i for i, a in enumerate(history)
         if a["action"] == "request_customer_info" and a.get("field") == "photo_evidence"),
        None,
    )
    if photo_idx is not None:
        score += 0.10

    if any(
        a["action"] == "calculate_total"
        and a.get("base_price") is not None
        and abs(a.get("base_price", 0) - order["base_price"]) <= 1.0
        and abs(a.get("extra_fees", 0) - order["delivery_fee"]) <= 1.0
        for a in history
    ):
        score += 0.10

    res = next((a for a in history if a["action"] == "execute_resolution"), None)
    if res:
        res_idx = history.index(res)
        if photo_idx is not None and res_idx < photo_idx:
            score -= 0.15
        if res.get("resolution") == "refund":
            score += 0.25
        if res.get("amount") is not None and abs(res["amount"] - expected_total) <= 1.0:
            score += 0.20
        if res.get("wallet") == "source":
            score += 0.10

    return max(0.0, min(1.0, score))


def grade_policy_violation(history: list[dict], order: dict) -> float:
    score = 0.0

    if any(a["action"] == "request_customer_info" and a.get("field") == "email" for a in history):
        score += 0.10

    if any(a["action"] == "query_database" and a.get("collection") == "customers" for a in history):
        score += 0.10

    if any(a["action"] == "query_database" and a.get("collection") == "orders" for a in history):
        score += 0.10

    res = next((a for a in history if a["action"] == "execute_resolution"), None)
    if res:
        if res.get("resolution") == "deny":
            score += 0.35
            reason = (res.get("reason") or "").lower()
            if any(kw in reason for kw in ["7", "policy", "window", "days", "return"]):
                score += 0.20
        elif res.get("resolution") == "refund":
            score -= 0.20

    if not any(
        a["action"] == "request_customer_info" and a.get("field") == "photo_evidence"
        for a in history
    ):
        score += 0.05

    return max(0.0, min(1.0, score))


GRADERS = {
    "standard_refund":         grade_standard_refund,
    "damaged_item_refund":     grade_damaged_item,
    "policy_violation_denial": grade_policy_violation,
}
