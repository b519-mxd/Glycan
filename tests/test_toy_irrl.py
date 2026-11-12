import pytest
def test_two_policy_reinforce_updates_on_toy():
    pytest.importorskip("torch")
    from glycopath_research.irrl import train_toy_graph
    result=train_toy_graph(30,19)
    assert result["task_type"]=="TOY_SMOKE_NOT_SCIENTIFIC"
    assert len(result["trace"])==30
