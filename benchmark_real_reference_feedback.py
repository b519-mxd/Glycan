"""Controlled real-reference benchmark; requires pinned input JSON artifacts.

Run:
  python benchmark_real_reference_feedback.py --registry registry_records.json \
      --lectin reference_records.json --out benchmark.json
Requires GlyCosmos registry-alignment and glycopath reference-attack records.
This evaluates deterministic dependency refresh, not LLM or biological discovery.
"""
import argparse,collections,hashlib,json,time
from copy import deepcopy
from pathlib import Path
from glycopath_research.real_reference_adapter import (
    RegistryReference,CuratedLectinReference,
    build_registry_state,build_curated_state,run_feedback,routes_and_agents)


def pairs_from_registry(rows):
    g=collections.defaultdict(list)
    for r in rows:g[tuple(r['composition'])].append(r)
    pairs=[]
    for key in sorted(g):
        arr=sorted(g[key],key=lambda x:x['accession'])
        for second in arr[1:]:
            if arr[0]['signature']!=second['signature']:
                pairs.append((arr[0],second))
                break
    return pairs


def correct(state,gold):
    out={'correct_registry_links':0,'current_registry_assertions':0,
         'technical_traces_pass':0}
    for i,acc in enumerate(gold):
        e=f'entity:{i:04d}';r=f'assertion:{i:04d}';p=f'trace:{i:04d}'
        out['correct_registry_links']+=int(state.gate(e).state=='PASS' and
            state.artifacts[e].payload.get('registry_id')==acc)
        out['current_registry_assertions']+=int(state.gate(r).state=='PASS' and
            state.artifacts[r].payload.get('subject_accession')==acc)
        out['technical_traces_pass']+=int(state.gate(p).state=='PASS')
    return out


def cached_fixed_pipeline(state, registry, lectins):
    """A fixed entity/relation/path workflow with the same dependency cache.
    This non-LLM baseline uses exactly the same registered tools.
    """
    routes, agents = routes_and_agents(registry, lectins)
    calls = 0
    for kind, agent_name in [('entity','registry_resolve'),
                             ('relation','relation_refresh'),
                             ('path','trace_refresh')]:
        for aid in sorted(state.artifacts):
            obj = state.artifacts[aid]
            if obj.kind != kind or state.gate(aid).state == 'PASS':
                continue
            result = agents[agent_name](obj, state.snapshot(), state.gate(aid))
            calls += 1
            if result is not None:
                state.put(aid, obj.kind, result.payload, obj.parents)
    return calls


def evaluate(registry_rows,lectin_rows,n=80,changed=30):
    pairs=pairs_from_registry(registry_rows)
    if not 0<changed<=n<=len(pairs):
        raise ValueError('Not enough same-composition distinct supported graphs')
    chosen=pairs[:n]
    before=[a for a,b in chosen]
    after=[b if i<changed else a for i,(a,b) in enumerate(chosen)]
    acc=[r['accession'] for r in after]
    registry=RegistryReference(registry_rows)
    lectins=CuratedLectinReference(lectin_rows)
    live=build_registry_state(before)
    initial=run_feedback(live,registry,lectins,3*n)
    assert correct(live,[r['accession'] for r in before])['correct_registry_links']==n
    for i in range(changed):
        key=f'entity:{i:04d}'
        x=deepcopy(live.artifacts[key].payload)
        x.update(raw_iupac=after[i]['iupac'],registry_id=None,
                 structure_status='UNKNOWN')
        x.pop('supported_signature',None)
        live.put(key,'entity',x)
    skipped=correct(live,acc)
    cached=deepcopy(live)
    t=time.perf_counter()
    dynamic=run_feedback(live,registry,lectins,3*n)
    dynamic_secs=time.perf_counter()-t
    full=build_registry_state(after)
    t=time.perf_counter()
    static=run_feedback(full,registry,lectins,3*n)
    static_secs=time.perf_counter()-t
    t=time.perf_counter()
    cached_calls=cached_fixed_pipeline(cached,registry,lectins)
    cached_secs=time.perf_counter()-t
    final_cached=correct(cached,acc)
    final1=correct(live,acc);final2=correct(full,acc)
    assert final1==final2==final_cached
    assert cached_calls==3*changed
    assert final1['correct_registry_links']==n
    assert dynamic['used_budget']==3*changed and static['used_budget']==3*n

    citations=build_curated_state(lectin_rows,list(range(len(lectin_rows))))
    cite=run_feedback(citations,registry,lectins,len(lectin_rows))
    passes=sum(citations.gate(k).state=='PASS' for k in citations.artifacts)
    unknown=[k for k in citations.artifacts if citations.gate(k).state!='PASS']
    negative=sum(citations.gate(f'curated:{i:04d}').state=='PASS' and
        citations.artifacts[f'curated:{i:04d}'].payload.get('polarity')==-1
        for i,row in enumerate(lectin_rows) if row['kind']=='negative')
    return {'scope':'real source records; controlled structure replacements; no LLM multi-agent superiority or biological hypothesis validation',
      'input':{'registry_rows':len(registry_rows),'curated_records':len(lectin_rows),
               'registry_queries':n,'controlled_updates':changed},
      'registry_results':{
        'no_reprocessing':skipped,
        'selective_feedback':dict(final1,calls=len(dynamic['audit_log']),
                              seconds=round(dynamic_secs,5)),
        'fixed_cached_rerun':dict(final_cached,calls=cached_calls,
                              seconds=round(cached_secs,5)),
        'fixed_full_rerun':dict(final2,calls=len(static['audit_log']),
                              seconds=round(static_secs,5)),
        'call_reduction_vs_full_rerun':1-len(dynamic['audit_log'])/len(static['audit_log'])},
      'curated_bibliographic_evidence':{
          'source_and_polarity_pass':passes,'unresolved_record_ids':unknown,
          'negative_records_retained':negative,'calls':len(cite['audit_log'])},
      'disclaimer':'An actual dependency-cached fixed pipeline matched selective feedback: same identity results and same call count. No evidence of autonomous LLM coordination or scientific discovery quality gain.'}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--registry',required=True)
    p.add_argument('--lectin',required=True)
    p.add_argument('--out',default='real_reference_feedback_metrics.json')
    p.add_argument('--n',type=int,default=80)
    p.add_argument('--changed',type=int,default=30)
    args=p.parse_args()
    inputs=[Path(args.registry),Path(args.lectin)]
    records=[json.loads(x.read_text(encoding='utf8')) for x in inputs]
    out=evaluate(records[0],records[1],args.n,args.changed)
    out['source_sha256']={x.name:hashlib.sha256(x.read_bytes()).hexdigest()
                          for x in inputs}
    Path(args.out).write_text(json.dumps(out,indent=2,ensure_ascii=False),
                              encoding='utf8')
    print(json.dumps(out,indent=2,ensure_ascii=False))
