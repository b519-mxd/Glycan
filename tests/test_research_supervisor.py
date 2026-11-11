import pytest
from glycopath_research.supervisor import PlanStep,GateResult,InvalidPlan,execute,validate_plan

def test_cycle_is_rejected():
    with pytest.raises(InvalidPlan):
        validate_plan([PlanStep("a",("b",)),PlanStep("b",("a",))],{"a","b"})
def test_review_blocks_unvalidated_downstream():
    called=[]
    z=execute([PlanStep("infer",("collect",)),PlanStep("collect",max_attempts=2)],
              {"collect":lambda _:GateResult("REVIEW",reason="REVIEW_REQUIRED"),
               "infer":lambda _:called.append(True) or GateResult("PASS")})
    assert z["stage_statuses"]["infer"]=="BLOCK" and len(called)==0
def test_pass_passes_state():
    z=execute([PlanStep("a"),PlanStep("b",("a",))],
              {"a":lambda _:GateResult("PASS",{"value":42}),
               "b":lambda x:GateResult("PASS",{"answer":x["a"]["value"]})})
    assert z["outputs"]["b"]["answer"]==42
