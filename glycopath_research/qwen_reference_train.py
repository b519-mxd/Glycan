"""Bounded real Qwen CPU LoRA; curated record field extraction only."""
import json,csv,random,hashlib
from pathlib import Path
import torch
from transformers import AutoModelForCausalLM,AutoTokenizer
from peft import LoraConfig,get_peft_model,PeftModel
from huggingface_hub import model_info
torch.set_num_threads(2);torch.manual_seed(11);random.seed(11)
out=Path('qwen_output');out.mkdir(exist_ok=True);mid='Qwen/Qwen2.5-0.5B-Instruct';rev=model_info(mid).sha
rows=list(csv.DictReader(open('external/motifs.csv')));groups=sorted({r['motif'] for r in rows});random.shuffle(groups);held=set(groups[:20]);train=[r for r in rows if r['motif'] not in held];test=[r for r in rows if r['motif'] in held]
tok=AutoTokenizer.from_pretrained(mid,revision=rev);base=AutoModelForCausalLM.from_pretrained(mid,revision=rev,torch_dtype=torch.float32);base.config.use_cache=False
def example(r):return 'Extract the glycan motif name from the curated record. Record: '+r['motif_name']+' | structure: '+r['motif']+'\nAnswer:',r['motif_name']
def infer(model,rs):
    model.eval();ret=[]
    for r in rs:
        p,a=example(r);x=tok(p,return_tensors='pt',truncation=True,max_length=160)
        with torch.no_grad():g=model.generate(**x,max_new_tokens=16,do_sample=False,pad_token_id=tok.eos_token_id)
        y=tok.decode(g[0,x['input_ids'].shape[1]:],skip_special_tokens=True).strip().split('\n')[0];ret.append(dict(prompt=p,gold=a,prediction=y,exact=y==a))
    return ret
before=infer(base,test[:8]);model=get_peft_model(base,LoraConfig(r=4,lora_alpha=8,target_modules=['q_proj','v_proj'],lora_dropout=0.,task_type='CAUSAL_LM'));opt=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=2e-4);trace=[];model.train()
for step,r in enumerate(train[:16]):
    p,a=example(r);x=tok(p,add_special_tokens=False).input_ids;y=tok(' '+a+tok.eos_token,add_special_tokens=False).input_ids
    loss=model(input_ids=torch.tensor([x+y]),labels=torch.tensor([[-100]*len(x)+y])).loss;opt.zero_grad();loss.backward();opt.step();trace.append(dict(step=step+1,loss=float(loss.detach())));print(trace[-1],flush=True)
model.save_pretrained(out/'adapter');tok.save_pretrained(out/'adapter');after=infer(model,test[:8]);fresh=AutoModelForCausalLM.from_pretrained(mid,revision=rev,torch_dtype=torch.float32);replay=infer(PeftModel.from_pretrained(fresh,out/'adapter'),test[:8]);assert [x['prediction'] for x in replay]==[x['prediction'] for x in after]
for n,x in [('train_loss',trace),('before_predictions',before),('after_predictions',after),('reloaded_predictions',replay),('split',dict(train=train,test=test))]:(out/(n+'.json')).write_text(json.dumps(x,indent=2))
m=dict(model=mid,revision=rev,steps=len(trace),heldout_records_evaluated=len(after),before_exact=sum(x['exact'] for x in before)/len(before),after_exact=sum(x['exact'] for x in after)/len(after),reload_verified=True,scope='CPU LoRA curated record extraction only; answer present in input, not literature NER/RE gold',torch=torch.__version__,data_sha256=hashlib.sha256(Path('external/motifs.csv').read_bytes()).hexdigest());(out/'metrics.json').write_text(json.dumps(m,indent=2));print(m)
