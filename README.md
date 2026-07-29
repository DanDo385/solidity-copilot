# Solidity Copilot

An evaluation-first research project for generating Solidity contracts from constrained specifications and reference-contract context.

## Status

Experimental. The project begins by defining the task, legal data sources, and a reproducible evaluation harness before committing to fine-tuning.

## V1 objective

Given a structured contract request and optional reference-contract context, generate a self-contained Solidity implementation that:

1. compiles with a pinned `solc` version;
2. passes generated or curated Foundry tests;
3. respects explicit interface and invariant requirements; and
4. is clearly labeled as experimental and not production-audited.

## Why baseline before LoRA

LoRA or QLoRA is a candidate adaptation method, not a starting assumption. We first benchmark a capable base model with retrieval and few-shot prompting. Fine-tuning is justified only if it closes measured failures such as repeated Solidity/Foundry syntax errors, inconsistent project conventions, or weak performance on the held-out task distribution.

## Initial workstreams

- Define the task boundary and JSONL data contract.
- Curate licensed, attributable contract examples.
- Build a baseline generation benchmark.
- Build compile, test, and security-oriented evaluation gates.
- Run a LoRA/QLoRA experiment only after the baseline report.

## Safety boundary

Generated contracts are educational and experimental artifacts. They are not audited, deployment-ready financial software. No private keys, live deployment automation, or mainnet transaction paths belong in this repository.

## Repository map

- `docs/v1.md` — v1 scope, data schema, and evaluation plan.
- `data/` — local-only datasets and manifests; raw source corpora are ignored by Git.
- `evals/` — evaluation harnesses and fixtures.
- `training/` — reproducible training configurations after the baseline gate.

## License

MIT. Source examples retain their own upstream licenses and attribution requirements.
