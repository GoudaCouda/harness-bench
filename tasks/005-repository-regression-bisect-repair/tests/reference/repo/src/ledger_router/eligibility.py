"""Collection eligibility policy."""

ALLOWED_REGIONS = {"US", "CA", "GB"}


def collection_decision(invoice):
    """Return (eligible, reason) without causing an external action."""
    if invoice.get("region") not in ALLOWED_REGIONS:
        return False, "region_blocked"
    if invoice.get("trial") is True:
        return False, "trial_account"
    if invoice.get("status") not in {"active", "delinquent"}:
        return False, "account_status"
    if invoice.get("amount_due", 0) <= 0:
        return False, "no_balance"
    return True, "eligible_balance"
