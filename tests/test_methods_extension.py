from glycopath_research.methods_extension import *
from copy import deepcopy
import json
def run():
    ctx={'species':'human','assay':'A'}
    def r(k,g,p,q=1,c=ctx):return dict(key=k,cluster=g,polarity=p,quality=q,context=c)
    a=[r('e1','study1',1),r('e2','study1',-1),r('e3','study2',1)]
    x=fuse(a,ctx,ctx);y=fuse(a+[deepcopy(a[0])]*9,ctx,ctx);assert x==y
    assert x['support']==1.5 and x['refute']==.5
    assert fuse([r('e1','study1',1),r('e2','study2',1)],ctx,ctx)['strength']>fuse([r('e1','study1',1)],ctx,ctx)['strength']
    assert fuse([r('e1','study1',1,c={'species':'mouse','assay':'A'})],ctx,ctx)['direction'] is None
    assert fuse([r('e1',None,1,c={'species':'human'})],ctx,ctx)['direction'] is None
    assert solve_global({'a':{'X':.9},'b':{'X':.8,'Y':.79}},[('a','b')])['mapping']=={'a':'X','b':'Y'}
    assert solve_global({'a':{'X':.9},'b':{'X':.8}},corefs=[('a','b')])['mapping']=={'a':'X','b':'X'}
    assert solve_global({'a':{'X':.9,'Y':.9}})['mapping']=={'a':None}
    assert solve_global({'a':{'X':.9}},budget=1)['status']=='BUDGET_EXHAUSTED'
    try:fuse(a+[r('e1','study1',-1)],ctx,ctx);raise AssertionError('not rejected')
    except ValueError:pass
    e=dict(id='a',head='g',tail='R',relation='binds',structure='VERIFIED',context=ctx,provenance=['e1'],status='OBSERVED')
    e2=dict(e,id='b',relation='associated')
    assert len(legal_edges([e,e2],'g',{'g'},ctx,ctx,{'binds','associated'}))==2
    assert legal_edges([dict(e,structure='CONFLICT')],'g',{'g'},ctx,ctx,{'binds'})==[]
    assert audit_typed_path([e],ctx,ctx,{'binds'})['status']=='LOCALLY_SUPPORTED_NOT_CAUSAL'
    assert audit_typed_path([dict(e,context={'species':'human'})],ctx,ctx,{'binds'})['status']=='REVIEW'
    assert context_match({'species':None},ctx,ctx)=='UNKNOWN'
    return {'scope':'controlled unit checks only','checks':14,'base':x,'duplicate_9':y,'status':'PASS'}
def test_controlled_methods():assert run()['status']=='PASS'
if __name__=='__main__':print(json.dumps(run(),indent=2))
