"""Optional live HTTPS LLM Plan generator with untrusted-output validation."""
from __future__ import annotations
from dataclasses import dataclass
import json,os
from urllib.request import Request,urlopen
from glycopath_research.supervisor import PlanStep,validate_plan,execute,InvalidPlan

@dataclass(frozen=True)
class LLMPlanInfo:
    model:str
    base_url:str
    is_live_provider:bool
    token_usage:dict

class OpenAICompatiblePlanner:
    def __init__(self,base_url:str,model:str,api_key:str|None=None,timeout:float=60):
        if not base_url.startswith('https://') and not base_url.startswith('http://127.0.0.1:'):
            raise ValueError('HTTPS or explicit local loopback required')
        self.base_url=base_url.rstrip('/')
        self.model=model;self.api_key=api_key or os.environ.get('GLYCOPATH_LLM_API_KEY')
        self.timeout=timeout

    def propose(self,research_goal:str,registered_tools:list[str])->tuple[list[PlanStep],LLMPlanInfo]:
        if not self.api_key:raise RuntimeError('NO_AUTHORIZED_LLM_CREDENTIALS')
        system=('Return JSON object with key steps (name, dependencies, max_attempts 1..3). '
                'Use only allowlisted tools. Do not claim validation without gold labels.')
        payload={'model':self.model,'messages':[{'role':'system','content':system},
                  {'role':'user','content':json.dumps({'research_goal':research_goal,
                      'registered_tools':sorted(registered_tools)},ensure_ascii=False)}],
                  'temperature':0,'response_format':{'type':'json_object'}}
        req=Request(self.base_url+'/chat/completions',data=json.dumps(payload).encode('utf8'),
                    headers={'Content-Type':'application/json','Authorization':'Bearer '+self.api_key},method='POST')
        with urlopen(req,timeout=self.timeout) as response:response_json=json.load(response)
        data=json.loads(response_json['choices'][0]['message']['content'])
        if not isinstance(data.get('steps'),list):raise InvalidPlan('Invalid Plan shape')
        steps=[]
        for item in data['steps']:
            if set(item)!={'name','dependencies','max_attempts'}:raise InvalidPlan('Unknown Plan keys')
            steps.append(PlanStep(str(item['name']),tuple(item['dependencies']),int(item['max_attempts'])))
        return validate_plan(steps,set(registered_tools)), LLMPlanInfo(
            self.model,self.base_url,True,response_json.get('usage') or {})

def run_llm_plan(goal,tools,planner):
    steps,details=planner.propose(goal,list(tools))
    result=execute(steps,tools)
    result['planner']={'model':details.model,'base_url':details.base_url,
         'live_provider':details.is_live_provider,'usage':details.token_usage}
    return result
