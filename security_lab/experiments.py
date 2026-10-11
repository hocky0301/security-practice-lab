"""Generate the local-only synthetic results saved in results/experiments.json.

No live scanning, real incident, cloud identity, LLM or physical actuator.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import zipfile
from .authority import Authority
from .common import Rejected, digest
from .audit import make_chain, event_record, verify
from .dependencies import evaluate
from .observations import usable, residual_authority_area
from .release import build_archive
from .recovery import recover_preview

NOW='2026-10-09T12:00:00Z'
INVENTORY='a'*64

def attempt(fn):
    try:
        result=fn()
        return {'decision':'ACCEPT', 'result': result}
    except Rejected as e:
        return {'decision':'DENY', 'reason':str(e)}

def request():
    return dict(operation='preview_motion',resource='paper-stage',position_mdeg=1000,
                duration_ms=300,observation_id='frame-1')

def authority_cases(root):
    cases=[]
    for name in ['approved', 'content_changed', 'actor_changed', 'audience_changed',
                 'expired', 'stopped', 'stopped_then_resumed', 'policy_changed',
                 'replayed_after_restart', 'observation_stale', 'new_grant_after_resume']:
        a=Authority(root/(name+'.sqlite'))
        a.observe(observation_id='frame-1',measured_at=100,target='paper-stage')
        r=request();g=a.approve(r,actor='author',audience='local-preview',now=100)
        kw=dict(actor='author',audience='local-preview',now=101)
        if name=='content_changed':r['duration_ms']=301
        if name=='actor_changed':kw['actor']='other'
        if name=='audience_changed':kw['audience']='other-preview'
        if name=='expired':kw['now']=130
        if name=='stopped':a.stop()
        if name=='stopped_then_resumed':a.stop();a.resume(reviewer_role='human')
        if name=='policy_changed':a.set_policy('policy-v2')
        if name=='replayed_after_restart':
            a.execute(g,r,**kw);a=Authority(root/(name+'.sqlite'))
        if name=='observation_stale':kw['now']=106
        if name=='new_grant_after_resume':
            a.stop();a.resume(reviewer_role='human')
            g=a.approve(r,actor='author',audience='local-preview',now=101)
        result=attempt(lambda:a.execute(g,r,**kw))
        result['case']=name;result['receipt_count']=a.receipts()
        cases.append(result)
    return cases

def release_cases(root):
    src=root/'release-source';src.mkdir();(src/'code').mkdir();(src/'private').mkdir()
    data=b'print("public demo")\n';(src/'code/demo.py').write_bytes(data)
    (src/'private/notes.txt').write_text('non-public synthetic fixture')
    m=dict(schema='release-v1',reviewed_by='human-fixture',files=[
        dict(path='code/demo.py',sha256=hashlib.sha256(data).hexdigest(),approved=True)])
    def build():
        raw,report=build_archive(src,m)
        with zipfile.ZipFile(io.BytesIO(raw)) as z:report['names']=z.namelist()
        return report
    ok=attempt(build)
    (src/'code/demo.py').write_bytes(data+b'# new revision\n')
    changed=attempt(build)
    return {'approved_export':ok,'changed_after_review':changed}

def dependency_cases():
    base={'schema':'scan-normalized-v1','complete':True,'skipped':[],'checked':2,
          'inventory_sha256':INVENTORY,'generated_at':'2026-10-09T11:00:00Z',
          'scanner':'synthetic-fixture','findings':[dict(package='demo-package',version='1.0',
          advisory='DEMO-001',severity='high')]}
    ex=dict(package='demo-package',version='1.0',advisory='DEMO-001',owner='maintainer',
            reason='Local fixture temporary decision',approved_at='2026-10-09T10:00:00Z',
            expires_at='2026-10-10T10:00:00Z',inventory_sha256=INVENTORY)
    results=[]
    for name in ['complete_clean','high_no_exception','temporary_exception','expired_exception',
                 'scanner_incomplete','inventory_changed','stale_report']:
        r=copy.deepcopy(base);exceptions=[]
        if name=='complete_clean':r['findings']=[]
        if name in ('temporary_exception','expired_exception'):exceptions=[copy.deepcopy(ex)]
        if name=='expired_exception':exceptions[0]['expires_at']=NOW
        if name=='scanner_incomplete':r['complete']=False
        if name=='inventory_changed':r['inventory_sha256']='b'*64
        if name=='stale_report':r['generated_at']='2026-10-01T00:00:00Z'
        outcome = attempt(lambda:evaluate(r,exceptions,now=NOW,expected_inventory=INVENTORY))
        if outcome['decision'] == 'ACCEPT':
            outcome['decision'] = outcome['result']['verdict']
        results.append(dict(case=name, **outcome))
    return results

def audit_cases():
    records=[event_record(event='accepted',request_hash='a'*64,epoch=1,reason='ok',sequence=i,
                          observed_at=100+i) for i in range(1,4)]
    chain,anchor=make_chain(records)
    changed=copy.deepcopy(records);changed[0]['reason']='changed'
    rebuilt,replaced_anchor=make_chain(changed)
    return dict(original=attempt(lambda:verify(chain,anchor)),
                truncated=attempt(lambda:verify(chain[:-1],anchor)),
                rebuilt_old_anchor=attempt(lambda:verify(rebuilt,anchor)),
                rebuilt_replaced_anchor=attempt(lambda:verify(rebuilt,replaced_anchor)))

def observation_cases():
    base=dict(source='trusted-local-adapter',kind='measured',clock='local-monotonic-ms',
              observed_at=1000,sequence=2,session='session-a',quality='usable')
    results=[]
    for name,change in [('fresh',{}),('prediction',{'kind':'prediction'}),('old',{'observed_at':100}),
                        ('other_session',{'session':'session-b'}),('not_new',{'sequence':1}),
                        ('future',{'observed_at':1200}),('unknown_quality',{'quality':'unknown'})]:
        obs={**base,**change}
        results.append(dict(case=name,**attempt(lambda:usable(obs,now=1100,session='session-a',current_seq=1))))
    return results

def run(out: Path) -> dict:
    out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)
        snapshot={'schema':'motion-data-v1','motions':[request()]}
        recovery=recover_preview(snapshot,expected_hash=digest(snapshot),trusted_epoch=8,destination=root/'restored')
        result={'scope':'synthetic-local-only', 'authority':authority_cases(root),
                'release':release_cases(root), 'dependencies':dependency_cases(),
                'audit':audit_cases(), 'observations':observation_cases(), 'recovery':recovery,
                'residual_authority':{
                    'coarse_lease_area':residual_authority_area([{'second':0,'operations':3},{'second':60,'operations':0}]),
                    'revocation_area':residual_authority_area([{'second':0,'operations':3},{'second':2,'operations':0},{'second':60,'operations':0}]),
                    'unit':'operation-seconds; diagnostic, not probability'}}
    (out/'experiments.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=Path('results'))
    args=p.parse_args();report=run(args.out)
    print(json.dumps({'scope':report['scope'],'authority_cases':len(report['authority']),
        'authority_decisions':[x['decision'] for x in report['authority']],
        'dependencies':len(report['dependencies']),'observations':len(report['observations'])}))
if __name__=='__main__':main()
