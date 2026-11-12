"""Real GlyCosmos database reconstruction, no causal pathway claims."""
import csv,json,hashlib,random,collections,re,sys,os
from pathlib import Path
import numpy as np,torch
from torch import nn
from glycopath_research.reference_attack import Policy
from glycopath_research.structure_graph import parse_glycan,ParseError
torch.set_num_threads(2)
O=Path('glycosmos_output');O.mkdir(exist_ok=True)
def dump(n,x):(O/n).write_text(json.dumps(x,indent=2,ensure_ascii=False))
def read(p):
    with open(p,encoding='utf-8-sig',newline='') as f:
        r=csv.reader(f);head=next(r);return head,list(r)
gid=re.compile(r'(?<![A-Z0-9])G[0-9]{5}[A-Z]{2}(?![A-Z0-9])')
pid=re.compile(r'(?<![A-Z0-9])(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})(?![A-Z0-9])')
rid=re.compile(r'R-[A-Z]{3}-[0-9]+')
def pair(p,a,b):
    h,r=read(p);out=set()
    for row in r:
        x=';'.join(row)
        for u in a.findall(x):
            for v in b.findall(x):out.add((u,v))
    print(p,h,len(r),len(out),flush=True);return out,{'headers':h,'raw_rows':len(r),'pairs':len(out),'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest()}
gp,m1=pair('cosmos/glycan_protein.csv',gid,pid);pp,m2=pair('cosmos/protein_pathway.csv',pid,rid);gt,m3=pair('cosmos/glycan_pathway.csv',gid,rid)
assert len(gp)>0 and len(pp)>0 and len(gt)>0,(m1,m2,m3)
# Restrict to database-associated glycans and connecting proteins; retain every heldout target.
# Restrict to human pathway namespace to ensure comparable candidate scope.
gt=sorted((a,b) for a,b in gt if b.startswith('R-HSA-'))
assert len(gt)>=30
G={a for a,b in gt};P={b for a,b in gp if a in G};T={b for a,b in gt}
gp={(a,b) for a,b in gp if a in G and b in P}
pp={(a,b) for a,b in pp if a in P and b in T}
# fixed bounded task: 300 unique pairs sampled before training, not based on reachability
rng=random.Random(2026);rng.shuffle(gt);gt=gt[:300];G={a for a,b in gt};T={b for a,b in gt};gp={(a,b) for a,b in gp if a in G};P={b for a,b in gp};pp={(a,b) for a,b in pp if a in P and b in T}
print('subgraph',len(G),len(P),len(T),len(gp),len(pp),len(gt),flush=True)
def run(seed):
    r=random.Random(seed);torch.manual_seed(seed);x=gt[:];r.shuffle(x);n=len(x);train=x[:int(n*.7)];val=x[int(n*.7):int(n*.85)];test=x[int(n*.85):];nodes=sorted({'g:'+a for a in G}|{'p:'+a for a in P}|{'t:'+a for a in T});ids={a:i for i,a in enumerate(nodes)};reg=[{'g':0,'p':1,'t':2}[a[0]] for a in nodes];adj=collections.defaultdict(set);edges=[]
    for typ,ps,a,b in [('glycan_protein',gp,'g:','p:'),('protein_pathway',pp,'p:','t:'),('train_glycan_pathway',train,'g:','t:')]:
        for u,v in sorted(ps):
            h,t=ids[a+u],ids[b+v];adj[h].add(t);adj[t].add(h);edges.append([h,t,typ])
    assert all(ids['t:'+t] not in adj[ids['g:'+h]] for h,t in val+test)
    known=collections.defaultdict(set)
    for h,t in gt:known[ids['g:'+h]].add(ids['t:'+t])
    cand=sorted(ids['t:'+t] for t in T)
    def options(c,path,h,t=None):return sorted(v for v in adj[c] if v not in path and not(t is not None and c==h and v==t))
    def scores(h,model,mode):
        front=[([h],1.)];score=collections.defaultdict(float)
        for _ in range(3):
            nex=[]
            for path,w in front:
                o=options(path[-1],path,h)
                if not o:continue
                if model is None:p=np.ones(len(o))/(len(o) if mode=='uniform' else 1)
                else:
                    with torch.no_grad():p=model.logits(h,path[-1],o,[reg[v] for v in o]).exp().numpy()
                for v,z in zip(o,p):
                    m=w*float(z);nex.append((path+[v],m))
                    if v in cand:score[v]+=m
            front=sorted(nex,key=lambda a:(-a[1],a[0]))[:32]
        return score
    res={};traces={}
    for mode in ('count','uniform','single','dual'):
        model=None
        if mode in ('single','dual'):
            model=Policy(len(nodes),3,mode=='dual');opt=torch.optim.Adam(model.parameters(),lr=.005);before={k:v.clone() for k,v in model.state_dict().items()};trace=[]
            for i in range(400):
                a,b=r.choice(train);h,t=ids['g:'+a],ids['t:'+b];path=[h];logs=[]
                for _ in range(3):
                    o=options(path[-1],path,h,t)
                    if not o:break
                    d=torch.distributions.Categorical(logits=model.logits(h,path[-1],o,[reg[v] for v in o]));z=d.sample();logs.append(d.log_prob(z));path.append(o[z.item()])
                    if path[-1]==t:break
                reward=(1. if path[-1]==t else -.1)-.02*(len(path)-1)
                if logs:
                    loss=-torch.stack(logs).sum()*reward;opt.zero_grad();loss.backward();opt.step()
                trace.append({'episode':i,'reward':reward,'success':path[-1]==t})
            traces[mode]={'trace':trace,'parameter_delta':{k:float((v-before[k]).norm()) for k,v in model.state_dict().items()}};torch.save(model.state_dict(),O/f'{mode}_{seed}.pt')
        pred=[]
        for a,b in test:
            h,t=ids['g:'+a],ids['t:'+b];z=scores(h,model,mode);allow=[i for i in cand if i==t or i not in known[h]];v=z.get(t,0.);rank=sum(z.get(i,0.)>=v for i in allow);pred.append({'head':a,'target':b,'rank':rank,'reachable':v>0,'candidates':len(allow)})
        arr=np.array([p['rank'] for p in pred]);res[mode]={'mrr':float(np.mean(1/arr)),'hits1':float(np.mean(arr<=1)),'hits3':float(np.mean(arr<=3)),'hits10':float(np.mean(arr<=10)),'reachable':float(np.mean([p['reachable'] for p in pred]))};dump(f'pred_{mode}_{seed}.json',pred)
    dump(f'graph_{seed}.json',{'nodes':nodes,'edges':edges,'train':train,'validation':val,'test':test});dump(f'trace_{seed}.json',traces)
    return {'seed':seed,'nodes':len(nodes),'edges':len(edges),'train':len(train),'validation':len(val),'test':len(test),'results':res,'region_delta':traces['dual']['parameter_delta']['region.weight'],'entity_delta':traces['dual']['parameter_delta']['entity.weight']}
m={'sources':[m1,m2,m3],'scope':'GlyCosmos human glycan-pathway association reconstruction; database-derived labels, not independent causal mechanisms; source overlap possible','glycans':len(G),'proteins':len(P),'pathways':len(T),'glycan_protein_edges':len(gp),'protein_pathway_edges':len(pp),'queries':len(gt),'seeds':[run(s) for s in (11,19,42)]};dump('metrics.json',m);print(json.dumps(m,indent=2))
