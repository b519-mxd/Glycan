"""Curated lectin reference graph completion, not biological mechanism validation."""
import json,csv,hashlib,random,collections,sys
from pathlib import Path
import numpy as np
import torch
from torch import nn
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score,precision_score,recall_score
from glycopath_research.structure_graph import parse_glycan,ParseError
def dump(p,x): Path(p).write_text(json.dumps(x,indent=2,ensure_ascii=False))
def load(p):
    out=[]
    for i,row in enumerate(json.load(open(p))['data']):
        a=[v['value'] for v in row]
        for k,kind in [(4,'primary'),(5,'secondary'),(6,'negative')]:
            for motif,termini in (a[k] or {}).items():
                out.append(dict(head='lectin:'+a[0],tail='motif:'+motif,kind=kind,source=a[3] or 'unknown',species=a[2],termini=termini,row=i))
    return out
def feats(e):
    m=e['tail'][6:]; d={'head:'+e['head']:1,'species:'+str(e['species']):1}
    for k in (2,3,4):
        for i in range(len(m)-k+1):d['m:'+m[i:i+k]]=1
    return d
def relation(records,out):
    held=collections.Counter(e['source'] for e in records).most_common(1)[0][0]
    train=[e for e in records if e['source']!=held];test=[e for e in records if e['source']==held]
    y=lambda a:[int(e['kind']!='negative') for e in a]
    if len(set(y(train)))<2 or len(set(y(test)))<2:return {'status':'BLOCKED','reason':'source split lacks both classes','train':len(train),'test':len(test)}
    v=DictVectorizer(); X=v.fit_transform([feats(e) for e in train]); T=v.transform([feats(e) for e in test])
    model=LogisticRegression(max_iter=1000,class_weight='balanced',random_state=11).fit(X,y(train));pred=model.predict(T)
    import joblib;joblib.dump((v,model),out/'relation_model.joblib')
    dump(out/'relation_predictions.json',[dict(e,y=int(t),prediction=int(p)) for e,t,p in zip(test,y(test),pred)])
    return {'status':'PASS','task':'curated specificity polarity, not text RE or fusion validation','heldout_reference':held,'train':len(train),'test':len(test),'train_positive':sum(y(train)),'test_positive':sum(y(test)),'metrics':{n:{'precision':float(precision_score(y(test),p,zero_division=0)),'recall':float(recall_score(y(test),p,zero_division=0)),'f1':float(f1_score(y(test),p,zero_division=0)),'macro_f1':float(f1_score(y(test),p,average='macro',zero_division=0))} for n,p in [('all_positive',np.ones(len(test),dtype=int)),('logistic',pred)]}}
class Policy(nn.Module):
    def __init__(self,n,r,dual):
        super().__init__();self.e=nn.Embedding(n,16);self.region=nn.Linear(32,r);self.entity=nn.Linear(32,16);self.dual=dual
    def logits(self,h,c,opts,reg):
        x=torch.cat([self.e(torch.tensor(h)),self.e(torch.tensor(c))]); fine=self.e(torch.tensor(opts))@self.entity(x)
        if not self.dual:return torch.log_softmax(fine,0)
        rr=sorted(set(reg));rl=torch.log_softmax(self.region(x)[rr],0);z=torch.empty_like(fine)
        for j,r in enumerate(rr):
            ix=[i for i,a in enumerate(reg) if a==r];z[ix]=rl[j]+torch.log_softmax(fine[ix],0)
        return z
def graph_run(records,out,seed):
    rng=random.Random(seed);torch.manual_seed(seed)
    pairs=sorted({(e['head'],e['tail']) for e in records if e['kind']!='negative'});rng.shuffle(pairs);n=len(pairs)
    train=pairs[:int(.7*n)];val=pairs[int(.7*n):int(.85*n)];test=pairs[int(.85*n):]
    assert not(set(train)&set(test) or set(val)&set(test))
    pos=[e for e in records if e['kind']!='negative' and (e['head'],e['tail']) in set(train)]
    nodes=sorted({x for p in pairs for x in p}|{'species:'+str(e['species']) for e in pos}|{'source:'+e['source'] for e in pos});ids={x:i for i,x in enumerate(nodes)}
    regions={x:i for i,x in enumerate(sorted({z.split(':',1)[0] for z in nodes}))};reg=[regions[x.split(':',1)[0]] for x in nodes]
    adj=collections.defaultdict(set);edges={}
    for e in pos:
        for a,b in [(e['head'],e['tail']),(e['head'],'species:'+str(e['species'])),(e['head'],'source:'+e['source'])]:
            adj[ids[a]].add(ids[b]);adj[ids[b]].add(ids[a]);edges[(a,b)]=e['source']
    assert all(ids[b] not in adj[ids[a]] for a,b in val+test)
    cand=sorted({ids[b] for _,b in pairs});known=collections.defaultdict(set)
    for a,b in pairs:known[ids[a]].add(ids[b])
    def opts(c,path,h,t=None):return sorted(v for v in adj[c] if v not in path and not(t is not None and ((c==h and v==t) or(c==t and v==h))))
    def scores(h,model,mode):
        front=[([h],1.)];sc=collections.defaultdict(float)
        for _ in range(3):
            nxt=[]
            for path,m in front:
                o=opts(path[-1],path,h)
                if not o:continue
                if model is None:p=np.ones(len(o))/(len(o) if mode=='uniform' else 1)
                else:
                    with torch.no_grad():p=model.logits(h,path[-1],o,[reg[v] for v in o]).exp().numpy()
                for v,z in zip(o,p):
                    mass=m*float(z);nxt.append((path+[v],mass))
                    if v in cand:sc[v]+=mass
            front=sorted(nxt,key=lambda x:(-x[1],x[0]))[:32]
        return sc
    def evaluate(model,mode):
        pred=[]
        for a,b in test:
            h,t=ids[a],ids[b];s=scores(h,model,mode);allowed=[v for v in cand if v==t or v not in known[h]];z=s.get(t,0)
            rank=sum(s.get(v,0)>=z for v in allowed);pred.append(dict(head=a,target=b,rank=rank,reachable_beam=z>0,score=z,candidate_count=len(allowed)))
        return {'mrr':float(np.mean([1/p['rank'] for p in pred])),'hits1':float(np.mean([p['rank']<=1 for p in pred])),'hits3':float(np.mean([p['rank']<=3 for p in pred])),'hits10':float(np.mean([p['rank']<=10 for p in pred])),'reachable':float(np.mean([p['reachable_beam'] for p in pred]))},pred
    results={};traces={}
    for mode in ('bfs_count','uniform','single','dual'):
        model=None
        if mode in ('single','dual'):
            model=Policy(len(nodes),len(regions),mode=='dual');opt=torch.optim.Adam(model.parameters(),lr=.005);trace=[];before={k:v.detach().clone() for k,v in model.state_dict().items()}
            for ep in range(300):
                a,b=rng.choice(train);h,t=ids[a],ids[b];path=[h];logs=[]
                for _ in range(3):
                    o=opts(path[-1],path,h,t)
                    if not o:break
                    d=torch.distributions.Categorical(logits=model.logits(h,path[-1],o,[reg[v] for v in o]));j=d.sample();logs.append(d.log_prob(j));path.append(o[int(j)])
                    if path[-1]==t:break
                reward=(1. if path[-1]==t else -.1)-.02*(len(path)-1)
                if logs:
                    loss=-torch.stack(logs).sum()*reward;opt.zero_grad();loss.backward();opt.step()
                trace.append(dict(episode=ep,reward=reward,success=path[-1]==t))
            delta={k:float((v-before[k]).norm()) for k,v in model.state_dict().items()};traces[mode]={'trace':trace,'parameter_delta':delta};torch.save(model.state_dict(),out/f'{mode}_{seed}.pt')
        metric,pred=evaluate(model,mode);results[mode]=metric;dump(out/f'pred_{mode}_{seed}.json',pred)
    dump(out/f'graph_{seed}.json',{'train_pairs':train,'validation_pairs':val,'test_pairs':test,'edges':[[a,b,s] for (a,b),s in edges.items()],'nodes':nodes});dump(out/f'trace_{seed}.json',traces)
    return dict(seed=seed,nodes=len(nodes),train_pairs=len(train),validation_pairs=len(val),test_pairs=len(test),candidates=len(cand),results=results,region_parameter_delta=traces['dual']['parameter_delta']['region.weight'],entity_parameter_delta=traces['dual']['parameter_delta']['entity.weight'])
if __name__=='__main__':
    torch.set_num_threads(2);p=Path(sys.argv[1]);m=Path(sys.argv[2]);out=Path(sys.argv[3]);out.mkdir(parents=True,exist_ok=True)
    r=load(p);dump(out/'reference_records.json',r)
    x=dict(data_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),records=len(r),references=len({e['source'] for e in r}),relation=relation(r,out),graph=[graph_run(r,out,s) for s in (11,19,42)],scope='curated lectin reference graph completion only; not immune mechanism gold')
    dump(out/'metrics.json',x);print(json.dumps(x,indent=2))
