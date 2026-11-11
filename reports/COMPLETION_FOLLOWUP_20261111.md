# GlycoPath completion work — scientific scope and limits

This follow-up adds (1) restricted branched IUPAC-like structure parsing and 
contradiction/ambiguity tests, (2) authoritative Europe PMC PMCID-to-PMID 
verification for the original 33 errors, (3) optional authenticated HTTPS 
LLM Plan generation behind typed allowlist gates, and (4) pinned open-data 
CPU benchmarks from BojarLab/glycowork v1.11.0 (MIT license).

The public benchmarks are **not** the missing original independent expert
NER, entity alignment, provenance or biological path gold sets. Structure
parser coverage is a deterministic supported-grammar check. Binding baselines 
predict measured Z-scores for completely held-out glycan sequences; a high-Z
operational retrieval metric is a proxy, not a verified functional mechanism.

Run:```bash
PYTHONPATH=. pytest -q tests/test_structure_graph.py tests/test_metadata_repair.py tests/test_public_benchmarks.py tests/test_llm_orchestrator.py
```
The new GitHub workflow `glycopath-public-benchmark.yml` downloads the 
pinned original CSVs and publishes SHA-256 digests, scores and metadata audit 
artifacts. GPU Qwen training and domain-validated IRRL still require independent
task-specific gold and explicitly authorized accelerator capacity. Do not 
report placeholder metrics for absent experiments.

Reference corpus workflow: https://github.com/b519-mxd/Glycan/actions/runs/41441017494
Public data: https://github.com/BojarLab/glycowork/releases/tag/v1.11.0
