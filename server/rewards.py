def reward_request_info(field: str, task: str, already_collected: list[str]) -> float:
    if field in already_collected:
        return -0.05

    if task == "standard_refund":
        if field == "photo_evidence":
            return -0.10
        return 0.0

    if task == "damaged_item_refund":
        if field == "order_id":
            return +0.10
        if field == "photo_evidence":
            return +0.15
        return 0.0

    if task == "policy_violation_denial":
        if field == "email":
            return +0.10
        if field == "photo_evidence":
            return -0.10
        return 0.0

    return 0.0


def reward_query_db(collection: str, query: dict, found: bool,
                    task: str, order: dict, already_queried: list[str]) -> float:
    cache_key = f"{collection}:{list(query.keys())[0]}"
    if cache_key in already_queried:
        return -0.05

    if not found:
        return 0.0

    if task == "standard_refund":
        if collection == "orders":
            return +0.20

    if task == "damaged_item_refund":
        if collection == "orders":
            return +0.15
        if collection == "products":
            return +0.05

    if task == "policy_violation_denial":
        if collection == "customers":
            return +0.10
        if collection == "orders":
            return +0.15

    return 0.0


def reward_calculate(base_price: float, extra_fees: float, order: dict, task: str) -> float:
    correct = (
        abs(base_price - order["base_price"]) <= 1.0 and
        abs(extra_fees - order["delivery_fee"]) <= 1.0
    )

    if task == "damaged_item_refund":
        return +0.15 if correct else -0.10

    if task == "standard_refund":
        return +0.10 if correct else -0.10

    return 0.0


def reward_resolution(resolution: str, amount: float | None, wallet: str | None,
                      reason: str | None, task: str, order: dict,
                      photo_evidence_provided: bool) -> float:
    score = 0.0

    if task == "standard_refund":
        if resolution == "refund":
            score += 0.30
            full_refund = order["base_price"] + order["delivery_fee"]
            if amount is not None and (
                abs(amount - order["base_price"]) <= 1.0 or
                abs(amount - full_refund) <= 1.0
            ):
                score += 0.30
            if wallet == "source":
                score += 0.10
        else:
            score -= 0.20

    elif task == "damaged_item_refund":
        total = order["base_price"] + order["delivery_fee"]
        if not photo_evidence_provided:
            score -= 0.15
        if resolution == "refund":
            score += 0.20
            if amount is not None and abs(amount - total) <= 1.0:
                score += 0.15
            if wallet == "source":
                score += 0.05
        else:
            score -= 0.20

    elif task == "policy_violation_denial":
        if resolution == "deny":
            score += 0.30
            if reason:
                if any(kw in reason.lower() for kw in ["7", "policy", "window", "days", "return"]):
                    score += 0.20
        elif resolution == "refund":
            score -= 0.30

    return score
