# Minimal DriftKB Example

This example is a tiny repo-shaped project with the default DriftKB layout:

```text
.driftkb/config.yml
docs/kb/curated/payment.md
src/payment.py
```

Run validation from this directory inside a normal git checkout with a valid
`HEAD` commit:

```text
driftkb validate
```

The first run should pass. The KB uses `last_verified_commit: HEAD`, so the
example works inside a cloned checkout without baking in a private commit hash.

Now edit `src/payment.py` and change:

```python
PAYMENT_PROVIDER = "stripe"
```

to another value, then run:

```text
driftkb validate
```

You should see `FAIL` because the verify block no longer finds the expected
provider string.
