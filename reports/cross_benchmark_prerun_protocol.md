# Cross-Benchmark Typed Repair Protocol

Date: 2026-07-09

This version-controlled pre-run protocol defines the paper evidence run before
model execution. It is not an externally registered preregistration.

## Primary Question

Does the full `typed-repair+retain` policy outperform `generic+diagnostics` on
local verifier-rich tasks under the same maximum leaf-call budget?

## Fixed Design

| Item | Value |
|---|---|
| Models | qwen2.5-coder:14b, qwen2.5:7b, Apple CoreAI Freeform |
| Strategies | `generic+diagnostics`, `typed-fields`, `typed-repair+retain` |
| Call budget | 4 leaf calls per task |
| Decoding | Local models temperature 0; CoreAI bridge default greedy behavior |
| HumanEval | 164 tasks, fixed dataset order, seed 1 |
| TextWorld | 200 fixed game seeds: 20260901 through 20261100 |
| MiniWorkflow | 200 held-out template instances, seed 1 |
| DS-1000 | 100 fixed dataset records, seed 1 |

## Acceptance And Scoring

TextWorld candidates are executed from a fresh game state. MiniWorkflow uses
artifact, evidence, and deterministic gates. HumanEval and DS-1000 use only
non-oracle syntax/output-contract gates online; their official tests remain
post-hoc scores.

## Analysis

Report per-benchmark paired success differences, paired bootstrap confidence
intervals, exact McNemar tests, realized calls, prompt-token overhead, and the
contribution of each benchmark to pooled gains. Do not claim a cross-benchmark
typed-repair effect if it is carried by one benchmark or if code benchmarks
remain flat.
