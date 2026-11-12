"""DataID-isolated measured affinity rank reconstruction; not calibrated relation probability."""
import pandas as pd,numpy as np,json,hashlib,re,random,collections
from pathlib import Path
O=Path('evidence_output');O.mkdir(exist_ok=True)
def dump(n,x):(O/n).write_text(json.dumps(x,indent=2,ensure_ascii=False))
p=Path('cosmos/carbogrove.csv');d=pd.read_csv(p,low_memory=False);headers=list(d.columns)
print('headers',headers,'raw rows',len(d),flush=True)
def col(*names):
    for n in names:
        for c in headers:
            if re.sub('[^a-z0-9]','',c.lower())==n:return c
    raise ValueError((names,headers))
cols={k:col(*v) for k,v in {'lectin':['glycosmoslectinnumber','lectinnumber','lectinid'],'data':['dataid'],'result':['resultid'],'source':['datasource'],'provider':['provider','sampleprovider'],'conc':['concentration','concentrationugml'],'glycan':['glytoucanid'],'intensity':['bindingintensity'],'sd':['stdev','sd','standarddeviation']}.items()}
d=d.rename(columns={v:k for k,v in cols.items()})[list(cols)].copy()
d=d.dropna(subset=['lectin','data','glycan','intensity','source','provider','conc']);d['intensity']=pd.to_numeric(d.intensity,errors='coerce');d=d[np.isfinite(d.intensity)]
for k in ('lectin','data','result','source','provider','conc','glycan'):d[k]=d[k].astype(str).str.strip()
# DataID/condition/glycan groups prevent reuse of the same assay record across result reports.
assay=['data','lectin','source','provider','conc'];g=assay+['glycan']
u=d.drop_duplicates(subset=g+['intensity']).groupby(g,dropna=False)['intensity'].mean().reset_index()
# No absolute cross-assay comparison: rank percentile within observed (selected) assay list.
u['rank']=u.groupby(assay).intensity.rank(pct=True,method='average')
counts=u.groupby(assay).glycan.transform('size');u=u[counts>=3].copy()
d=d.merge(u[g+['rank']],on=g,how='inner');assert len(u)>100
ids=sorted(u.data.unique());assert len(ids)>10
results=[]
for seed in (11,19,42):
    rng=random.Random(seed);x=ids[:];rng.shuffle(x);cut=int(.8*len(x));train=set(x[:cut]);test=set(x[cut:]);assert not train&test
    tr=u[u.data.isin(train)];te=u[u.data.isin(test)];raw=d[d.data.isin(train)]
    broad=['lectin','glycan'];context=['lectin','glycan','source','provider','conc']
    a=raw.groupby(broad)['rank'].mean().rename('mention_mean').reset_index();b=tr.groupby(broad)['rank'].mean().rename('dedup_mean').reset_index();c=tr.groupby(context)['rank'].mean().rename('condition_mean').reset_index()
    z=te.merge(a,on=broad,how='left').merge(b,on=broad,how='left').merge(c,on=context,how='left');common=z.dropna(subset=['mention_mean','dedup_mean','condition_mean']).copy()
    if len(common)<10:
        results.append({'seed':seed,'status':'BLOCKED','reason':'too few common comparable test measurements','test_records':len(z),'common':len(common),'broad_coverage':float(z.dedup_mean.notna().mean())});continue
    vals={}
    for mode in ('mention_mean','dedup_mean','condition_mean'):
        e=common[mode]-common['rank'];vals[mode]={'mae':float(abs(e).mean()),'rmse':float(np.sqrt(np.mean(e*e)))}
    # Duplicate a deterministic sample of existing rows. Reference grouping invariant by construction.
    extra=raw.sample(frac=.2,random_state=seed);dup=pd.concat([raw,extra,extra,extra]);a2=dup.groupby(broad)['rank'].mean();a1=raw.groupby(broad)['rank'].mean();shift=float((a2-a1).abs().mean());dedup_shift=float((dup.drop_duplicates(subset=g).groupby(broad)['rank'].mean()-raw.drop_duplicates(subset=g).groupby(broad)['rank'].mean()).abs().max())
    common.to_csv(O/f'predictions_{seed}.csv',index=False);dump(f'split_{seed}.json',{'train_data_ids':sorted(train),'test_data_ids':sorted(test)})
    results.append({'seed':seed,'status':'PASS','train_dataids':len(train),'test_dataids':len(test),'train_records':len(tr),'test_records':len(te),'common_test_records':len(common),'common_coverage':len(common)/len(te),'metrics':vals,'controlled_duplicate_mention_mean_shift':shift,'dedup_exact_copy_max_shift':dedup_shift})
m={'source':'https://download.glycosmos.org/glycosmos_lectins_carbogrove_list.csv','sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'headers':headers,'raw_eligible_rows':len(d),'unique_measurement_contexts':len(u),'data_ids':len(ids),'scope':'held-out DataID, percentile within observed high-affinity assay records, same-source/condition matching; not biochemical truth probability, distinct DataIDs not necessarily independent experiments','seeds':results};dump('metrics.json',m);print(json.dumps(m,indent=2))
