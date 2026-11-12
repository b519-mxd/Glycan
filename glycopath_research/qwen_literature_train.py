"""Real Qwen mixed glycan-literature weak supervision + BC5CDR independent human-label transfer pilot."""
import json,random,re,os,hashlib,glob
from pathlib import Path
import torch
from transformers import AutoTokenizer,AutoModelForCausalLM
from peft import LoraConfig,get_peft_model,PeftModel
from huggingface_hub import model_info
torch.set_num_threads(2);torch.manual_seed(11);random.seed(11)
out=Path('text_output');out.mkdir(exist_ok=True)
def write(name,x):(out/name).write_text(json.dumps(x,ensure_ascii=False,indent=2))
def read_json(p):
    x=Path(p).read_text()
    try:
        y=json.loads(x)
        return y if isinstance(y,list) else y.get('data',y.get('rows',[]))
    except json.JSONDecodeError:return [json.loads(z) for z in x.splitlines() if z.strip()]
def chemical(row):
    tok=row['tokens'];tag=row['tags'];ent=[];i=0
    while i<len(tag):
        if tag[i]==1:
            j=i+1
            while j<len(tag) and tag[j]==4:j+=1
            ent.append(' '.join(tok[i:j]));i=j
        else:i+=1
    return {'text':' '.join(tok),'gold':list(dict.fromkeys(ent)),'task':'chemical','label':'PUBLIC_HUMAN_BC5CDR'}
def sample_public(path,n,seed):
    data=[chemical(r) for r in read_json(path)];data=[r for r in data if 5<=len(r['text'].split())<=55]
    p=[r for r in data if r['gold']];q=[r for r in data if not r['gold']]
    rng=random.Random(seed);rng.shuffle(p);rng.shuffle(q);ret=p[:int(n*.75)]+q[:n-int(n*.75)];rng.shuffle(ret);return ret
pat=re.compile(r'(?<![A-Za-z0-9])(?:N-acetylglucosamine|N-acetylgalactosamine|sialic acid|fucose|mannose|galactose|glucose|GlcNAc|GalNAc|Neu5Ac|Neu5Gc)(?![A-Za-z0-9])',re.I)
files=sorted(Path('original_artifact').rglob('PMC*.txt'));random.shuffle(files);gly=[]
for p in files:
    text=p.read_text(errors='replace')
    for sent in re.split(r'(?<=[.!?])\s+',text):
        if 12<=len(sent.split())<=55 and pat.search(sent):
            gly.append({'text':sent,'gold':list(dict.fromkeys(m.group(0) for m in pat.finditer(sent))),'task':'glycan','label':'WEAK_LABEL','doc':p.stem,'source_hash':hashlib.sha256(p.read_bytes()).hexdigest()});break
    if len(gly)>=56:break
assert len(gly)==56 and len({x['doc'] for x in gly})==56
trg,vg,teg=gly[:32],gly[32:40],gly[40:56]
trc=sample_public('external/train.json',32,11);vc=sample_public('external/valid.json',8,19);tec=sample_public('external/test.json',16,42)
train=trg+trc;random.shuffle(train);test=teg+tec;val=vg+vc
# exact normalized entity sets, not span-level NER.
def prompt(r):return 'Extract exact '+('named carbohydrate molecules' if r['task']=='glycan' else 'chemical entities')+' from the sentence. Output only entity strings separated by | or NONE.\nSentence: '+r['text']+'\nAnswer:'
def target(r):return ' | '.join(r['gold']) if r['gold'] else 'NONE'
mid='Qwen/Qwen2.5-0.5B-Instruct';rev='7ae557604adf67be50417f59c2c2f167def9a775'
tok=AutoTokenizer.from_pretrained(mid,revision=rev);base=AutoModelForCausalLM.from_pretrained(mid,revision=rev,torch_dtype=torch.float32,attn_implementation='eager');base.config.use_cache=False
def infer(m,rs):
    m.eval();ret=[]
    for r in rs:
        x=tok(prompt(r),return_tensors='pt',truncation=True,max_length=224)
        with torch.no_grad():g=m.generate(**x,max_new_tokens=24,do_sample=False,pad_token_id=tok.eos_token_id)
        z=tok.decode(g[0,x['input_ids'].shape[1]:],skip_special_tokens=True).strip().split('\n')[0];p=[v.strip() for v in z.split('|') if v.strip() and v.strip().upper()!='NONE']
        ret.append(dict(r,prediction=p,raw=z))
    return ret
def score(rs):
    res={}
    for task in ('glycan','chemical'):
        a=[r for r in rs if r['task']==task];tp=fp=fn=exact=0
        for r in a:
            f=lambda xs:{x.casefold().strip() for x in xs};p=f(r['prediction']);g=f(r['gold']);tp+=len(p&g);fp+=len(p-g);fn+=len(g-p);exact+=int(p==g)
        pr=tp/max(tp+fp,1);rc=tp/max(tp+fn,1)
        res[task]=dict(n=len(a),precision=pr,recall=rc,f1=2*pr*rc/max(pr+rc,1e-12),exact=exact/len(a),tp=tp,fp=fp,fn=fn)
    return res
write('split.json',dict(train=train,validation=val,test=test))
before=infer(base,test);write('before.json',before)
model=get_peft_model(base,LoraConfig(r=4,lora_alpha=8,target_modules=['q_proj','v_proj'],lora_dropout=0.,task_type='CAUSAL_LM'));opt=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=2e-4);trace=[];model.train()
for step,r in enumerate(train):
    x=tok(prompt(r),add_special_tokens=False,truncation=True,max_length=224).input_ids;y=tok(' '+target(r)+tok.eos_token,add_special_tokens=False).input_ids
    loss=model(input_ids=torch.tensor([x+y]),labels=torch.tensor([[-100]*len(x)+y])).loss;opt.zero_grad();loss.backward();opt.step();trace.append(dict(step=step+1,loss=float(loss.detach()),task=r['task']));print(trace[-1],flush=True)
    if (step+1)%16==0:write('train_loss.json',trace)
model.save_pretrained(out/'adapter');tok.save_pretrained(out/'adapter');write('train_loss.json',trace)
after=infer(model,test);write('after.json',after);v=infer(model,val);write('validation_predictions.json',v)
fresh=AutoModelForCausalLM.from_pretrained(mid,revision=rev,torch_dtype=torch.float32,attn_implementation='eager');reload=PeftModel.from_pretrained(fresh,out/'adapter');check=infer(reload,test[:4]);assert [x['prediction'] for x in check]==[x['prediction'] for x in after[:4]]
m=dict(model=mid,revision=rev,seed=11,steps=len(trace),train_counts={'glycan_weak':len(trg),'public_chemical_human':len(trc)},before=score(before),after=score(after),validation=score(v),reload_verified_first_four=True,scope='weak glycan entity surface extraction; independent human BC5CDR subset general chemical entity surface-set evaluation; not span NER or glycan gold',corpus_docs=56,torch=torch.__version__);write('metrics.json',m);print(json.dumps(m,indent=2))
