"""Batch quote behavior requested by sales operations."""


def build_batch_quotes(requests, catalog, coupons, quote_date):
    """Return ordered quote or rejection outcomes for a batch."""

    if not isinstance(requests, list) or not 1 <= len(requests) <= 50:
        raise ValueError("requests must contain between 1 and 50 items")

    counts = {}
    for item in requests:
        if isinstance(item, dict):
            request_id = item.get("request_id")
            if isinstance(request_id, str) and request_id:
                counts[request_id] = counts.get(request_id, 0) + 1

    outcomes = []
    for item in requests:
        if not isinstance(item, dict):
            outcomes.append({"request_id": None, "status": "rejected", "code": "invalid_item"})
            continue
        request_id = item.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            outcomes.append({"request_id": request_id, "status": "rejected", "code": "invalid_request_id"})
            continue
        if counts.get(request_id, 0) > 1:
            outcomes.append({"request_id": request_id, "status": "rejected", "code": "duplicate_request_id"})
            continue
        plan_name = item.get("plan")
        if plan_name not in catalog:
            outcomes.append({"request_id": request_id, "status": "rejected", "code": "unknown_plan"})
            continue
        plan = catalog[plan_name]
        seats = item.get("seats")
        if not isinstance(seats, int) or isinstance(seats, bool) or not plan["min_seats"] <= seats <= plan["max_seats"]:
            outcomes.append({"request_id": request_id, "status": "rejected", "code": "invalid_seats"})
            continue
        term = item.get("term_months")
        if not isinstance(term, int) or isinstance(term, bool) or term not in (1, 12):
            outcomes.append({"request_id": request_id, "status": "rejected", "code": "invalid_term"})
            continue
        coupon_code = item.get("coupon")
        coupon = None
        if coupon_code is not None:
            if coupon_code not in coupons:
                outcomes.append({"request_id": request_id, "status": "rejected", "code": "unknown_coupon"})
                continue
            coupon = coupons[coupon_code]
            if coupon["plan"] != plan_name:
                outcomes.append({"request_id": request_id, "status": "rejected", "code": "coupon_wrong_plan"})
                continue
            if quote_date > coupon["expires_on"]:
                outcomes.append({"request_id": request_id, "status": "rejected", "code": "coupon_expired"})
                continue
        subtotal = plan["monthly_cents"] * seats * term
        term_discount = subtotal * plan["annual_discount_bps"] // 10000 if term == 12 else 0
        after_term = subtotal - term_discount
        coupon_discount = after_term * coupon["discount_bps"] // 10000 if coupon is not None else 0
        outcomes.append({
            "request_id": request_id,
            "status": "quoted",
            "subtotal_cents": subtotal,
            "term_discount_cents": term_discount,
            "coupon_discount_cents": coupon_discount,
            "total_cents": after_term - coupon_discount,
        })
    return outcomes
