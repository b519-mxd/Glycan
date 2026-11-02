# GlycoPath 1134 JATS collection: strict evidence gate

This independent Europe PMC collection does **not** reproduce the manuscript's original cohort. The repository is public: do not commit harvested article text to Git history. The workflow produces a **14-day** GitHub Actions artifact with only text for articles that *automatically* present CC BY, CC BY-SA, or CC0 license URLs in the JATS `<license>` element, plus a CSV attribution and verification manifest. Manual legal/subject-matter review remains necessary before broader reuse.

Run locally (network needed):

```bash
python -m pip install 'defusedxml>=0.7.1,<1'
python research/glycopath_harvest/collect_open_fulltext.py --target 1134 --save-text --output research/glycopath_harvest/results
```

`--save-text` is the actual supported option. `summary.json` is `PASS` **only if 1,134 unique PMCID/DOI/PMID/text candidates with permissive JATS license have their readable `.txt` files saved and hash-verified**. `records.csv` contains per-item PMCID, DOI, title, authors, journal, source link, license URL, status, filename, and SHA-256; `progress.json` is finalized even when the result is blocked. The XML parser rejects unsafe entity expansion and missing/short bodies. An ambiguous, NC, or ND license will not be redistributed in the public artifact. No PDFs are downloaded.

This automated check is not an expert confirmation of glycoscience relevance or an original-method reproduction. It never computes or reports GlycoPath Precision/F1/MRR/Hits@K. Gold annotations, independent test splits, and GPU availability must be established separately before formal scientific experiments.
