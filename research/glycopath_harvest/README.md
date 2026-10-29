# GlycoPath literature harvesting (independent implementation)

This directory contains an independently implemented, provenance-preserving harvest of at least 1,134 openly licensed glycoscience full texts. **It does not claim to reproduce the original GlycoPath manuscript corpus or trained model.**

The repository is public. Article bodies must NOT be committed to the repository. The GitHub Actions workflow archives bibliography, corpus coverage and execution logs only. Licensed JATS plain text can be stored locally by running the script with `--save-licensed-text` in an authorized private environment.

Outputs: records.csv, checkpoint.json, summary.json. Each article has a PMCID and source link; unknown licenses or short XML bodies do not count. A PASS means 1,134 licensed XML bodies were actually retrieved, not 1,134 paper titles. Scientific metrics from the original manuscript remain UNVERIFIED until human gold labels and original evaluation code are supplied.

To run in a private network-enabled environment: `python research/glycopath_harvest/collect_open_fulltext.py --target 1134 --save-licensed-text`.
