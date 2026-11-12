"""Recompute the recorded public-reference results; engineering PASS is not paper acceptance."""
import json,csv,hashlib,math,statistics,sys
from pathlib import Path
P=Path('verification');O=Path('final_output');O.mkdir(exist_ok=True)
def get(p):return json.loads(p.read_text())
def equal(a,b):assert math.isclose(float(a),float(b),rel_tol=1e-9,abs_tol=1e-10),(a,b)
checks=[]
for name,keys in [('reference',('graph','train_pairs','validation_pairs','test_pairs')),('glycosmos',('seeds','train','validation','test'))]:
    root=P/name;m=get(root/'metrics.json')
    for r in m[keys[0]]:
        seed=r['seed'];g=get(root/f'graph_{seed}.json');tr=set(map(tuple,g[keys[1]]));va=set(map(tuple,g[keys[2]]));te=set(map(tuple,g[keys[3]]));assert not(tr&va or va&te or tr&te)
        if name=='reference':
            assert all((a,b) not in te and (b,a) not in te for a,b,*_ in g['edges'])
        else:
            ns=g['nodes'];assert all((ns[a][2:],ns[b][2:]) not in te for a,b,t in g['edges'] if t=='train_glycan_pathway')
        for method,metric in r['results'].items():
            preds=get(root/f'pred_{method}_{seed}.json');ranks=[p['rank'] for p in preds];assert len(ranks)==len(te)
            equal(statistics.mean(1/x for x in ranks),metric['mrr'])
            for k in (1,3,10):equal(statistics.mean(x<=k for x in ranks),metric['hits'+str(k)])
        checks.append({'task':name,'seed':seed,'status':'PASS','scope':'ranking and split recomputation'})
reg=get(P/'registry/metrics.json');pairs=get(P/'registry/registry_pairs.json');assert len(pairs)==reg['evaluated_pairs'];assert sum(x['same_graph'] for x in pairs)==reg['supported_graph_registry_collisions'];checks.append({'task':'registry','status':'PASS','scope':'accession collision recomputation'})
for phase in ('before','after'):
    pred=get(P/f'qwen_literature/{phase}.json');m=get(P/'qwen_literature/metrics.json')[phase]
    for task in ('glycan','chemical'):
        rows=[r for r in pred if r['task']==task];tp=fp=fn=0
        for r in rows:
            a={v.casefold().strip() for v in r['prediction']};b={v.casefold().strip() for v in r['gold']};tp+=len(a&b);fp+=len(a-b);fn+=len(b-a)
        assert [tp,fp,fn]==[m[task]['tp'],m[task]['fp'],m[task]['fn']]
checks.append({'task':'qwen_literature','status':'PASS','scope':'independent prediction count recomputation, weak vs public gold explicitly separated'})
m=get(P/'qwen_reference/metrics.json')
for phase in ('before','after'):
    a=get(P/f'qwen_reference/{phase}_predictions.json');equal(sum(x['exact'] for x in a)/len(a),m[phase+'_exact'])
checks.append({'task':'qwen_reference','status':'PASS','scope':'field-copy pilot recomputation'})
m=get(P/'measured/metrics.json')
for a in m['seeds']:
    if a['status']!='PASS':continue
    p=list(csv.DictReader((P/f'measured/predictions_{a["seed"]}.csv').open()));assert len(p)==a['common_test_records']
    for mode in a['metrics']:
        e=[float(x[mode])-float(x['rank']) for x in p];equal(statistics.mean(abs(x) for x in e),a['metrics'][mode]['mae']);equal(math.sqrt(statistics.mean(x*x for x in e)),a['metrics'][mode]['rmse'])
    split=get(P/f'measured/split_{a["seed"]}.json');assert not set(split['train_data_ids'])&set(split['test_data_ids'])
checks.append({'task':'measured_evidence','status':'PASS','scope':'same-subset DataID-held-out percentile error recomputation'})
report={'engineering_verification':'PASS','checks':checks,'paper_acceptance':'PARTIAL','unresolved':['natural glycan NER/RE expert gold','cross-database natural entity linking','independent original-study dependency and conflict gold','calibrated relation probability','complete 1134-paper literature-derived GKG','functional path independent expert/wet-lab validation','external strong baselines and full ablations','fixed-split multiple Qwen seeds']}
(O/'acceptance.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
