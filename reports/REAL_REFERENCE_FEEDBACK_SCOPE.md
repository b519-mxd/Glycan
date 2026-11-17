# Real reference integration + controlled incremental update benchmark
Date: 2026-11-17.

**Scope: real frozen glycan registry and curated bibliographic records, controlled
input changes. This is NOT a natural language retrieval, biological hypothesis,
or multi-agent superiority experiment.**

## Pinned sources
- `registry_records.json`: 2,500 *sampled* GlyCosmos accession/IUPAC records in
  the restricted supported-parser subset. SHA256:
  `90a301cff0475eef414e7a83188bc48dbd22cde5477b75d25c4b5e1725fb48cb`.
- `reference_records.json`: 200 curated lectin specificity records (primary,
  secondary and negative), preserved from the earlier public benchmark artifact.
  SHA256:
  `c038f2e21ad20c220d2ee9495242c9b0bd0287899e538c7449cc37bfeab7b874`.
- These large files are distributed in the previous research artifacts, not
  committed to this branch. Small real-origin smoke fixtures are committed
  separately in `tests/test_real_reference_feedback_smoke.py`.

## Method
1. Freeze the reference index, re-parse every accepted IUPAC entry, check its
   structural signature, and link only a unique matching accession.
2. Build 80 registry identity objects with registry assertion metadata and
   **technical dependency traces**. No biological relation is added.
3. Replace 30 query structures with a *different genuinely registered* IUPAC
   structure of the **same composition**. This is a **controlled update**,
   not a claim about real-world mutation rates.
4. Compare no reprocessing, automatic dependency-aware selective refresh,
   and fixed full rerun with identical lookup/refresh handlers.
5. Independently check DOI source and sign of 200 curated lectin specificity
   records without linking motif descriptions to unrelated full glycans.

## Actual results from the full offline frozen-input run
| Condition | Current accession links correct | Registry assertions current | Traces pass | Handler calls |
|---|---:|---:|---:|---:|
| No reprocessing | 50/80 | 50/80 | 50/80 | 0 |
| Quality-event-driven selective refresh | 80/80 | 80/80 | 80/80 | 90 |
| Fixed pipeline with dependency cache | 80/80 | 80/80 | 80/80 | 90 |
| Fixed full rerun | 80/80 | 80/80 | 80/80 | 240 |

Relative to a *non-cached full rerun*, both selective refresh and a cached
fixed pipeline use 62.5% fewer handler calls, with identical registry results.
Therefore, this experiment isolates the benefit of incremental computation,
NOT a multi-agent coordination gain.

Curated records: 198/200 recover a DOI citation and signed label, 2/200 have
`source=unknown` and remain REVIEW, 20/20 negative records remain negative.
A controlled species mismatch is BLOCK.

Local full package: 25 software tests passed (14 coordinator + 11 reference).
GitHub smoke CI: 14 coordinator + 6 pinned-record tests passed at
https://github.com/b519-mxd/Glycan/actions/runs/44042799845 .

## Scientific boundary
- Source DOI identifies a **bibliographic report**; not an independent original
  experiment or a verified biological claim.
- Registry match is limited to a restricted IUPAC parser and unique accession
  in the frozen reference subset, not a general chemical identity proof.
- Control PASS verifies declared state consistency; it is not expert review.
- Technical trace is a dependency chain, **not** an IRRL biological path.
- No LLM participated in this benchmark. Its result demonstrates incremental
  invalidation/refresh, not MAS advantage over an equally capable cached
  single-Agent / incrementally updated fixed pipeline.
- A fair scientific comparison still needs single LLM-Agent, fixed pipeline
  with caching, no-feedback MAS and feedback MAS under the same tool access,
  budget and independently validated natural glycan tasks.

## Reproduction
With the two input JSON files downloaded from earlier public-benchmark
artifacts, run:

```bash
python benchmark_real_reference_feedback.py \
  --registry registry_records.json \
  --lectin reference_records.json \
  --out real_reference_feedback_metrics.json
```

This branch does not change the previous Qwen training, evidence
measurement results, or IRRL model and ranking metrics.
