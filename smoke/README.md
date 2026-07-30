# Contract-to-Solidity smoke harness

This directory preserves three small prompt-to-Solidity examples and exercises their intended behavior with Foundry.

## Layout

- `prompts/`: exact model inputs
- `raw/`: exact model responses, including output-format failures
- `contracts/`: normalized compile candidates; Counter's Markdown fences were removed
- `test/Smoke.t.sol`: dependency-free Solidity tests using Forge's built-in cheatcode address
- `REPORT.md`: observed results and limitations

## Run

Forge 1.7.1 is expected. No npm packages, Foundry libraries, or `forge-std` install is required.

```sh
/Users/openclaw/.foundry/bin/forge test
```

The harness covers Counter state/events, PiggyBank deposits/access control/withdrawal failure, and SimpleToken metadata/accounting/events/reverts.

## Boundary

These are experimental model outputs. Passing this narrow smoke harness is not an audit and does not make the contracts production-ready or safe to deploy.
