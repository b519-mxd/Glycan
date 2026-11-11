"""Structured Plan validator and auditable stage gates, NOT yet a live LLM supervisor."""
from __future__ import annotations
from dataclasses import dataclass,field
from typing import Callable

@dataclass(frozen=True)
class PlanStep:
    name:str
    dependencies:tuple[str,...]=()
    max_attempts:int=1

@dataclass(frozen=True)
class GateResult:
    state:str
    output:dict=field(default_factory=dict)
    reason:str=""

class InvalidPlan(ValueError):pass

def validate_plan(steps:list[PlanStep],available_tools:set[str])->list[PlanStep]:
    names=[s.name for s in steps]
    if len(names)!=len(set(names)) or not all(names):raise InvalidPlan("Duplicate or empty step")
    if any(s.max_attempts<1 or s.max_attempts>5 for s in steps):raise InvalidPlan("Retries outside 1..5")
    if any(s.name not in available_tools for s in steps):raise InvalidPlan("Tool not permitted")
    pending={s.name:set(s.dependencies) for s in steps}
    for k,v in pending.items():
        if k in v or not v.issubset(set(names)):raise InvalidPlan("Invalid dependency")
    sorted_steps=[]
    while pending:
        ready=sorted(k for k,v in pending.items() if not v)
        if not ready:raise InvalidPlan("Dependency cycle")
        for name in ready:
            sorted_steps.append(next(s for s in steps if s.name==name))
            del pending[name]
        for deps in pending.values():deps.difference_update(ready)
    return sorted_steps

def execute(steps:list[PlanStep],tools:dict[str,Callable[[dict],GateResult]])->dict:
    order=validate_plan(steps,set(tools))
    outcomes={};log=[]
    for step in order:
        if any(outcomes[d].state!="PASS" for d in step.dependencies):
            outcomes[step.name]=GateResult("BLOCK",reason="UPSTREAM_GATE_NOT_PASS")
            log.append({"stage":step.name,"attempt":0,"state":"BLOCK","reason":"UPSTREAM_GATE_NOT_PASS"})
            continue
        result=GateResult("BLOCK",reason="NOT_EXECUTED")
        for attempt in range(1,step.max_attempts+1):
            try:
                result=tools[step.name]({d:outcomes[d].output for d in step.dependencies})
                if result.state not in ("PASS","BLOCK","REVIEW"):raise ValueError("Bad gate state")
            except Exception as error:
                result=GateResult("BLOCK",reason="TOOL_ERROR:"+type(error).__name__)
            log.append({"stage":step.name,"attempt":attempt,"state":result.state,"reason":result.reason})
            if result.state!="REVIEW":break
        outcomes[step.name]=result
    return {"overall_status":"PASS" if all(x.state=="PASS" for x in outcomes.values()) else "PARTIAL",
            "stage_statuses":{k:v.state for k,v in outcomes.items()},
            "outputs":{k:v.output for k,v in outcomes.items()},"audit_log":log}
