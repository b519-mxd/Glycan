import pytest
from glycopath_research.llm_orchestrator import OpenAICompatiblePlanner
def test_remote_plaintext_denied():
    with pytest.raises(ValueError):
        OpenAICompatiblePlanner('http://external.example/v1','model','key')
def test_missing_llm_credentials():
    with pytest.raises(RuntimeError,match='NO_AUTHORIZED_LLM_CREDENTIALS'):
        OpenAICompatiblePlanner('https://example.org/v1','test','').propose('goal',['tool'])
