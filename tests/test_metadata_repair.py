import pytest
from unittest.mock import patch,MagicMock
from io import BytesIO
import json
from glycopath_research.metadata_repair import fetch_verified_pmid_map

def test_invalid_id_offline():
    with pytest.raises(ValueError):fetch_verified_pmid_map(['BAD-ID'])

def test_authoritative_mapping_exact_match():
    response={'status':'ok','records':[{'pmcid':'PMC123','pmid':432},{'pmcid':'PMC999','pmid':111}]}
    mock=MagicMock();mock.__enter__.return_value=BytesIO(json.dumps(response).encode())
    with patch('glycopath_research.metadata_repair.urlopen',return_value=mock):
        values,log=fetch_verified_pmid_map(['PMC123'])
    assert values=={'PMC123':'432'} and log['verified_count']==1
