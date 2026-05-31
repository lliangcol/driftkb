PAYMENT_PROVIDER = "stripe"


def charge(amount_cents: int) -> dict[str, int | str]:
    if amount_cents <= 0:
        raise ValueError("amount_cents must be positive")
    return {"provider": PAYMENT_PROVIDER, "amount_cents": amount_cents}
