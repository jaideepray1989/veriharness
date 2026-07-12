# Focused TextWorld Repair Ablation Protocol

Date: 2026-07-10

## Status

This is a fixed pre-run protocol for the focused ablation, written after the
broader 200-game sweep was stopped. It is not an external preregistration. The
earlier broad run completed raw-diagnostic rows for the full seed manifest, so
the focused subset must not be described as unseen with respect to that
baseline.

## Question

On an external verifier-rich environment, which parts of VeriHarness improve
success under an equal four-call budget: structured failure fields,
preserve-set instructions, or the combined policy with candidate retention?

## Fixed Design

| Item | Value |
|---|---|
| Environment | TextWorld 1.7.0, fresh state per candidate |
| Games | 50 |
| Seed rule | Final 50 seeds in `textworld-preregistered-v1` |
| Game seeds | 20261051 through 20261100 |
| Primary model | `qwen2.5-coder:14b` through local Ollama |
| Decoding | Temperature 0, top-p unset |
| Policies | `generic+diagnostics`, `typed-fields`, `typed-preserve`, `typed-repair+retain` |
| Budget | At most four leaf calls per task |
| Acceptance | Fresh-state execution reaches a terminal win within four commands |

The first model is reviewed before running the identical Qwen 7B replication.

## Analysis

Report paired success differences with bootstrap confidence intervals and
exact McNemar tests. Also report realized leaf calls, wall time, prompt-token
overhead, and failure labels. The primary comparison is full
`typed-repair+retain` versus `generic+diagnostics`. Component comparisons are
`typed-fields` versus diagnostics, `typed-preserve` versus `typed-fields`, and
full policy versus `typed-preserve`.

Do not attribute a full-policy gain to typed fields alone unless the
`typed-fields` comparison supports it. Count every timeout, parse failure, and
environment failure as an unsuccessful task.
