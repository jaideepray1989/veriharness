# AgenticDev 2026 Paper

The manuscript follows the workshop's short-paper requirements:

- ACM proceedings format
- `\documentclass[sigconf,review,anonymous]{acmart}`
- at most five content pages
- up to two additional reference-only pages
- anonymous review copy

Build from this directory:

```bash
tectonic main.tex --outdir ../../output/pdf
```

Recompute the statistics from the row-level data:

```bash
python3 analyze.py
```

The stable review PDF is copied to:

```text
output/pdf/veriharness-agenticdev2026.pdf
```

Before submission, verify the PDF page count, anonymity, embedded fonts, and
that the anonymous artifact is accessible to reviewers. Replace the anonymous
author block only for the camera-ready version.
