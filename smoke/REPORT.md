# Prompt-to-Solidity smoke report

## Setup

- Generator: Claude Haiku, three independent tool-disabled calls
- Cases: Counter, owner-only Ether piggy bank, fixed-supply token
- Compiler: solc 0.8.30 via Forge 1.7.1
- EVM target: Shanghai
- Harness: dependency-free Solidity tests; no npm, Ganache, or `forge-std`

## Raw-output observations

| Case | Raw source compiles as returned | Normalized source compiles | Behavior tests |
| --- | --- | --- | --- |
| Counter | No | Yes | Pass |
| PiggyBank | Yes | Yes | Pass |
| SimpleToken | Yes | Yes | Pass |

The Counter response included Markdown fences despite the explicit “Solidity source only” instruction. That makes the raw response uncompilable and is the clearest first failure mode. The compile candidate removes those fences and normalizes whitespace. All three raw responses also omitted SPDX headers.

The contracts otherwise implemented the requested narrow behaviors: Counter state transitions/events, PiggyBank ownership/deposit/full withdrawal/revert paths, and SimpleToken metadata/supply/transfers/custom-error paths.

## Verification

Exact command:

```sh
/Users/openclaw/.foundry/bin/forge test
```

Result:

```text
Ran 3 test suites: 12 tests passed, 0 failed, 0 skipped (12 total tests).
```

## Interpretation

This sample is too small to justify training, retrieval, deployment, or broader infrastructure. Compilation and smoke-test success are useful baseline signals, not security review. These generated contracts are not audited or production-ready.
