# VeriHarness Agent Notes

This repository is an experimental harness, not a product agent framework.

Rules for changes:

- Keep leaf outputs structured.
- Never let a leaf decide final acceptance for gated variants.
- Preserve traces for every leaf call.
- Treat failed runs as data.
- Keep benchmark generation deterministic by seed.
- Do not require hosted LLM credentials for tests or smoke runs.

The intended causal ablation is:

```text
H0: full trace + self accept
H1: summary + self accept
H2: state context + self accept
H3: state context + external gates
H4: state context + external gates + VeriHarness
```
