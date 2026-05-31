# Profiles

Profiles let DriftKB support repository-specific layouts without changing the default behavior for other projects. The default profile remains language-neutral and uses `docs/kb/**` plus `.driftkb/**` paths.

Select a profile from the CLI:

```text
driftkb validate --profile enterprise-java
driftkb gaps detect --profile enterprise-java
driftkb promote .agents/kb/zh/generated/payment-service-stub.md --profile enterprise-java
```

You can also persist the profile in `.driftkb/config.yml`:

```yaml
profile: enterprise-java
version: 1
```

An explicit CLI `--profile` overrides the configured profile for that command.

## `default`

The default profile keeps DriftKB portable:

- curated KB: `docs/kb/curated`
- generated KB: `docs/kb/generated`
- validation output: `.driftkb/validation`
- adapters: `generic`
- generated stubs use `anchor_symbols` and `validation_status: pending_human_review`
- promotion requires `validation_status: human_reviewed` and `reviewed_by`

## `enterprise-java`

The `enterprise-java` profile is opt-in. It does not hard-code a local checkout path; it only changes config defaults and frontmatter aliases:

- curated KB: `.agents/kb/zh/curated`
- generated KB: `.agents/kb/zh/generated`
- validation output: `.agents/kb/zh/_validation`
- call graph cache: `.agents/kb/zh/_validation/call_graph_cache.json`
- section map: `.agents/kb/zh/_validation/kb_section_map.json`
- fingerprint snapshots: `.agents/kb/zh/_validation/fingerprints`
- adapters: `generic`, `enterprise-java`
- gap risk annotations: `@DS`, `@Transactional`, `@RocketMQMessageListener`, `@XxlJob`

Profile frontmatter aliases:

- `anchor_classes` is treated as `anchor_symbols`
- generated stubs use `anchor_classes`
- generated stubs use `review_status: pending_review`
- promotion accepts `review_status: reviewed` or `review_status: human_reviewed`
- promotion accepts `reviewer` or `reviewed_by`

Initialize an example config and directories:

```text
driftkb init --profile enterprise-java
```

`init` creates missing directories and writes `.driftkb/config.yml` only when it does not already exist. It does not overwrite an existing config file.

Run validation with the profile:

```text
driftkb validate --profile enterprise-java
```

Detect gaps with Enterprise Java-compatible stub frontmatter:

```text
driftkb gaps detect --profile enterprise-java --write
```

Promote a reviewed generated stub:

```text
driftkb promote .agents/kb/zh/generated/payment-service-stub.md --profile enterprise-java
```

Before promotion, the stub must still be under the generated KB directory, have `kind: generated`, and identify a human reviewer. Promotion moves it into the curated KB directory, updates `kind`, `last_verified_commit`, and `stale_policy`, and removes generated review fields.
