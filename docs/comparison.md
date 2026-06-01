# Comparison

DriftKB is not a documentation generator, a prose linter, or a hosted knowledge
base. It is a local validation CLI for curated Markdown KB pages.

## DriftKB vs README Linters

README linters usually check formatting, links, spelling, or style. DriftKB
checks whether a curated KB page still matches the source areas and mechanical
assertions declared by that page.

Use both when useful: linters improve document quality, while DriftKB catches
repo-specific drift signals.

## DriftKB vs AI-Generated Docs

AI-generated docs can help draft missing context, but generated text is not
trusted by default in DriftKB. Gap detection is advisory, and promotion from
generated stubs into curated KB requires human review.

DriftKB focuses on validation after humans curate the knowledge.

## DriftKB vs Full Static Analysis

Full static analyzers understand a programming language deeply. DriftKB uses
lightweight fingerprints, constrained verify blocks, git diff context, and an
optional static call graph cache. This keeps the core portable and avoids
locking the project to one language or graph provider.

Language-specific adapters can improve signal without becoming mandatory core
dependencies.

## DriftKB vs Hosted Knowledge-Base Services

DriftKB is local-first. It does not require a SaaS account, a database, a
background worker, or a remote service. CI and hooks can consume the same CLI
and JSON reports that developers run locally.
