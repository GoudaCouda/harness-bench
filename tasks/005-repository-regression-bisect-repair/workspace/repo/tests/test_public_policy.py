from ledger_router.eligibility import collection_decision


def test_active_positive_balance_is_eligible() -> None:
    assert collection_decision(
        {"region": "US", "trial": False, "status": "active", "amount_due": 10}
    ) == (True, "eligible_balance")


def test_closed_account_is_not_eligible() -> None:
    assert collection_decision(
        {"region": "CA", "trial": False, "status": "closed", "amount_due": 10}
    ) == (False, "account_status")


def test_trial_and_zero_balance_guards() -> None:
    assert collection_decision(
        {"region": "US", "trial": True, "status": "active", "amount_due": 10}
    ) == (False, "trial_account")
    assert collection_decision(
        {"region": "US", "trial": False, "status": "active", "amount_due": 0}
    ) == (False, "no_balance")
