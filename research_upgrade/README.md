# GlycoPath research upgrade: verified incremental algorithms

This PR adds conservative chemical identity checks, provenance-aware signed evidence fusion, and standalone path evidence auditing. These are research-engineering prototypes, not validated biomedical findings.

Local corpus file audit (1134 saved JATS text) on 2026-11-11 found: 1134 unique PMCID and SHA256; 1100 unique non-empty DOI; 34 DOI missing; 33 invalid PMIDs containing PMCID values. The original PR #2 remains draft and separate.

The original repository contains lexicon/regex NER and simplified path search. Qwen was **not** finetuned, no curated independent gold exists, and paper-grade hierarchical IRRL remains **NOT_RUN**. See the separately delivered research package for CPU weak-label training (2400 sentences, three seeds), toy REINFORCE smoke, complete metadata audit and recorded outputs. Weak proxy metrics MUST NOT be used as manuscript NER/RE/IRRL results.

Run: \`PYTHONPATH=. pytest -q tests/test_research_methods.py\`.

The glycan parser deliberately covers only a small linear motif syntax: it is not a full SNFG or IUPAC-Condensed parser. Context equality is conservative, and a signed evidence index is not a calibrated probability.
