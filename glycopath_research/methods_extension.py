"""Methods extension prototype: bounded assignment, contextual evidence and typed action checks.
Controlled verification only; not a trained literature model."""
from itertools import product
from collections import defaultdict
from math import prod

def solve_global(candidates, conflicts=(), corefs=(), tau=.5, lam=.2, budget=100000):
    """Candidate IDs MUST be externally verified exact matches; abstain on ties or budget."""
    names=sorted(candidates); opts=[[None]+sorted(candidates[i]) for i in names]
    n=prod(map(len,opts)); best=float('-inf'); optimal=[]
    if n>budget:return {'status':'BUDGET_EXHAUSTED','mapping':{i:None for i in names},'states':n}
    for a in product(*opts):
        m=dict(zip(names,a))
        if any(m[i] is not None and m[i]==m[j] for i,j in conflicts):continue
        v=sum(candidates[i][m[i]]-tau for i in names if m[i] is not None)
        v+=lam*sum(1 if m[i] is not None and m[i]==m[j] else -1 if m[i] is not None and m[j] is not None else 0 for i,j in corefs)
        if v>best+1e-10:best=v;optimal=[m]
        elif abs(v-best)<=1e-10:optimal.append(m)
    return {'status':'OPTIMAL_ENUMERATED','objective':best,'mapping':{i:optimal[0][i] if all(m[i]==optimal[0][i] for m in optimal) else None for i in names},'states':n}

def context_match(a,b,required):
    if any(a.get(k) not in (None,'') and b.get(k) not in (None,'') and a[k]!=b[k] for k in required):return 'CONFLICT'
    if any(k not in a or k not in b or a[k] in (None,'') or b[k] in (None,'') for k in required):return 'UNKNOWN'
    return 'MATCH'

def fuse(records, query, required):
    """Records: key, cluster (known or None), context, polarity, quality."""
    unique={}
    for r in records:
        if not 0<=r['quality']<=1 or r['polarity'] not in (-1,0,1):raise ValueError('bad evidence')
        if r['key'] in unique and unique[r['key']]!=r:raise ValueError('conflicting duplicate key')
        unique[r['key']]=r
    groups=defaultdict(list); excluded=[]
    for r in unique.values():
        if context_match(r['context'],query,required)!='MATCH':excluded.append(r['key']);continue
        groups[r['cluster'] or '__unknown__'].append(r)
    plus=minus=0.; unknown=0
    for key,g in groups.items():
        w=max(r['quality'] for r in g);d=sum(r['quality'] for r in g)
        if d:plus+=w*sum(r['quality'] for r in g if r['polarity']==1)/d;minus+=w*sum(r['quality'] for r in g if r['polarity']==-1)/d
        unknown+=int(key=='__unknown__')
    mass=plus+minus
    return {'support':plus,'refute':minus,'direction':(plus-minus)/mass if mass else None,'strength':1-1/(1+mass),'conflict':2*min(plus,minus)/mass if mass else None,'known_groups':len(groups)-unknown,'unknown_pool':bool(unknown),'excluded':sorted(excluded),'keys':sorted(unique)}

def legal_edges(edges, current, visited, query, required, allowed_relations):
    """Typed edge IDs remain distinct; direction is explicit. Unknown context is reviewable."""
    seen=set();out=[]
    for e in edges:
        if e['id'] in seen:raise ValueError('duplicate edge id')
        seen.add(e['id'])
        if e['head']!=current or e['tail'] in visited or e['relation'] not in allowed_relations:continue
        if e['structure']=='CONFLICT' or context_match(e['context'],query,required)=='CONFLICT':continue
        out.append(e)
    return out

def audit_typed_path(path, query, required, allowed_relations):
    """Independent rule checks, not an expert causal validation."""
    issues=[];prior=None;visited=set()
    for i,e in enumerate(path):
        if prior is not None and prior!=e['head']:issues.append((i,'DISCONNECTED'))
        if i==0:visited.add(e['head'])
        if e['tail'] in visited:issues.append((i,'CYCLE'))
        if e['structure']!='VERIFIED':issues.append((i,'STRUCTURE_UNRESOLVED'))
        if e['relation'] not in allowed_relations:issues.append((i,'RELATION_NOT_ALLOWED'))
        if context_match(e['context'],query,required)!='MATCH':issues.append((i,'CONTEXT_NOT_VERIFIED'))
        if not e.get('provenance') or e.get('status')!='OBSERVED':issues.append((i,'EVIDENCE_GAP'))
        if i and context_match(path[i-1]['context'],e['context'],required)!='MATCH':issues.append((i,'CROSS_EDGE_CONTEXT_GAP'))
        prior=e['tail'];visited.add(prior)
    return {'status':'REVIEW' if issues or not path else 'LOCALLY_SUPPORTED_NOT_CAUSAL','issues':issues}
