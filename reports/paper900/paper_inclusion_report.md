# VeriHarness Modal Paper900 Analysis

## Validated dataset

- 880 rows across 13 runs; 2652 leaf calls.
- Zero infrastructure/client-error rows after one quarantined request was rerun identically.
- Oracle-blind acceptance; TextWorld terminal success and full hidden HumanEval tests are post-hoc outcomes.

## Primary TextWorld result (50 paired games, budget 4)

### Qwen2.5-Coder-14B-AWQ/L4

- Raw diagnostics: 14/50 (28.0%).
- Same-information natural language: 35/50 (70.0%).
- Location+observed, no alternatives: 18/50 (36.0%).
- Typed fields: 36/50 (72.0%).
- Typed vs raw: 44.0% [95% CI 28.0%, 60.0%], exact p=1.04904e-05, Holm p=3.14713e-05.
- Typed vs same-information NL: 2.0% [95% CI -8.0%, 12.0%], exact p=1, Holm p=1.
- Typed vs location-only: 36.0% [95% CI 20.0%, 52.0%], exact p=0.000121117, Holm p=0.000242233.

### Llama-3.1-8B-AWQ/T4

- Raw diagnostics: 8/50 (16.0%).
- Same-information natural language: 29/50 (58.0%).
- Location+observed, no alternatives: 9/50 (18.0%).
- Typed fields: 29/50 (58.0%).
- Typed vs raw: 42.0% [95% CI 28.0%, 56.0%], exact p=9.53674e-07, Holm p=3.8147e-06.
- Typed vs same-information NL: 0.0% [95% CI -12.0%, 12.0%], exact p=1, Holm p=1.
- Typed vs location-only: 40.0% [95% CI 26.0%, 54.0%], exact p=1.09673e-05, Holm p=2.19345e-05.

## Robustness lanes

### Budget sensitivity (same 15 games)

- Qwen raw/typed wins at budgets 2, 4, 6, 8: 5/8, 4/11, 4/11, 4/12.
- Llama raw/typed wins at budgets 2, 4, 6, 8: 1/5, 2/9, 2/11, 2/11.
- The gain increases between budgets 2 and 4, then plateaus for Qwen and grows through budget 6 for Llama; this is not a universal step exactly at budget 4.

### Sampled Qwen decoding (20 games x 3 seeds)

- Per-seed wins: raw 6/6/5, same-information NL 14/13/14, typed 14/16/14.
- Typed vs raw clustered delta: 45.0% [95% CI 23.3%, 66.7%], Holm p=0.0053.
- Typed vs same-information NL: 5.0% [95% CI -3.3%, 15.0%], Holm p=0.499.

### Public-test HumanEval scope check (15 tasks)

- Qwen hidden-test success is 14/15 under every policy; all 15 candidates pass the public gate on call one.
- Llama hidden-test success is 10/15 for raw, same-information NL, and location-only, versus 9/15 for typed fields.
- This lane supplies a negative boundary result, not evidence of code-repair improvement.

## Efficiency and prompt overhead

- Typed vs same-information NL uses 130 vs 147 calls for Qwen and 149 vs 161 for Llama.
- Paired call differences are -0.34 calls/game [95% CI -0.60, -0.06] for Qwen and -0.24 [-0.44, -0.04] for Llama.
- Average retry transcripts are similar (typed/prose: 701/716 Qwen; 706/722 Llama). Total prompt-word proxies are 14% and 10% lower for typed feedback because it realizes fewer calls.

## Statistical definitions

- Primary intervals: 10,000 paired bootstrap resamples over 50 games, seed 1.
- Primary tests: two-sided exact McNemar with Holm correction over four planned contrasts within each model.
- Sampling intervals: 10,000 bootstrap resamples over 20 game clusters, retaining three repeats per game.
- Sampling tests: 100,000 seeded game-cluster sign flips with Holm correction.

## Interpretation for the paper

1. Include: structured verifier feedback with expected alternatives substantially outperforms raw diagnostics across both model families.
2. Include as a boundary: typed JSON structure itself does not outperform an information-matched natural-language message.
3. Include: removing expected alternatives largely removes the gain, identifying explicit repair content as the active ingredient within structured feedback.
4. Include as robustness: the ordering persists across budgets and sampled decoding.
5. Include as a negative scope result: public-test HumanEval shows no repair-policy gain; most Qwen tasks pass on the first call, and Llama differences are small.
6. Exclude: claims that typed structure alone is causal, that preserve/retention is beneficial, or that the study demonstrates deployment impact.

See the CSV files in this directory for exact paper tables.
