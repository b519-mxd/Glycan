from glycopath_research.metadata_repair import verify_pmcid_pmid
def test_reject_non_pmcid_without_network():
    assert verify_pmcid_pmid('BAD-ID')['status']=='INVALID_PMCID'
