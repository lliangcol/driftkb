---
title: Payment processing
last_verified_commit: HEAD
source_globs:
  - src/payment.py
stale_policy: warn
anchor_symbols:
  - charge
adapters:
  - generic
---

# Payment processing

The minimal example charges a card through the configured payment provider.
The KB is considered stale when `src/payment.py` changes after the current
checkout commit.

```bash verify
rg -n "PAYMENT_PROVIDER = \"stripe\"" src/payment.py
# expected: match_count >= 1
```
