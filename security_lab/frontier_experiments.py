"""Run deterministic local boundary experiments. No external actions or model calls."""
from __future__ import annotations
import argparse
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict,replace
from pathlib import Path
from tempfile import TemporaryDirectory
from .common import digest
from .release_context import VerifiedBuild,ReleaseApproval,check_release
from .tool_contracts import contract_digest,check_contract,enforce_effect
from .capability_budget import BudgetStore
from .memory_authority import head_of,check_current
from .evidence_age import DisplayState,repaint,authorize_from_evidence,display_only_freshness

def run()->dict:
    v=VerifiedBuild('a'*64,'builder','reviewed-workflow','source-1')
    a=ReleaseApproval('a'*64,'builder','reviewed-workflow','source-1','public-demo','public',1000)
    release={
      'matching':check_release(v,a,'public-demo','public',10),
      'same_digest_other_workflow':check_release(replace(v,workflow='other-workflow'),a,'public-demo','public',10),
      'same_digest_other_destination':check_release(v,a,'other-destination','public',10),
      'visibility_changed':check_release(v,a,'public-demo','private',10),
      'expired':check_release(v,a,'public-demo','public',1000),
      'scope':'Policy fixture after assumed signature verification; no signatures issued/verified.'}
    c={'tool':'preview','server':'local-demo','revision':'r1','description':'Render locally',
       'input_schema':{'type':'object'},'operations':['preview'],'egress':['local-display']}
    fingerprint=contract_digest(c)
    contracts={'package_lock_unchanged':True,'same_descriptor':check_contract(c,fingerprint),
      'description_changed':check_contract({**c,'description':'Render and copy elsewhere'},fingerprint),
      'same_metadata_unpermitted_effect':enforce_effect('publish','public-site',
          {'operations':['preview'],'destinations':['local-display']}),
      'scope':'Synthetic tool descriptors; no live scanner, MCP transport or remote enforcement.'}
    with TemporaryDirectory() as t:
        b=BudgetStore(Path(t)/'budget.sqlite')
        with ThreadPoolExecutor(max_workers=8) as ex:
            decisions=list(ex.map(lambda i:b.reserve('job-'+str(i),80),range(100)))
        budget={'requests':100,'per_call_limit':100,'request_units':80,'total_limit':300,
          'per_call_only_total':sum(80 for _ in range(100) if 80<=100),
          'shared_decisions':dict(sorted(Counter(decisions).items())),
          'shared_snapshot':b.snapshot(),'units':'synthetic units, not money'}
        q=BudgetStore(Path(t)/'queue.sqlite');q.reserve('queued',80)
        q.transition(True);q.transition(False)
        budget['queued_after_stop_resume']=q.deliver('queued')
        q.reserve('new-job',80);budget['new_job_after_resume']=q.deliver('new-job')
        u=BudgetStore(Path(t)/'unknown.sqlite');u.reserve('request',80);u.mark_unknown('request')
        budget['unknown_outcome_reserved']=u.snapshot()['reserved_or_spent']
        budget['unknown_outcome_retry']=u.deliver('request')
    grant={'sequence':1,'kind':'grant','subject':'writer','resource':'report'}
    revoke={**grant,'sequence':2,'kind':'revoke'}
    current=[grant,revoke];head=head_of(current,'incarnation-1')
    memory={'old_grant_only_reference':True,
      'summary_claims_allowed_current_ledger':check_current(current,head,'incarnation-1','writer','report','Permission is granted'),
      'old_snapshot_against_current_head':check_current([grant],head,'incarnation-1','writer','report'),
      'new_explicit_grant':check_current(current+[{**grant,'sequence':3}],
         head_of(current+[{**grant,'sequence':3}],'incarnation-1'),'incarnation-1','writer','report'),
      'scope':'Handwritten summary fixture; not LLM memory accuracy or EAL-Bench reproduction.'}
    f=DisplayState(1000,1000,1000,'capture-1','measured')
    timeline=[]
    for now in range(1000,2100,100):
        x=f if now==1000 else repaint(f,now)
        timeline.append({'now_ms':now,'measured_ms':x.measured_ms,'rendered_ms':x.rendered_ms,
          'measurement_age_ms':now-x.measured_ms,'render_age_ms':now-x.rendered_ms,
          'display_check':display_only_freshness(x,now),
          'evidence_decision':authorize_from_evidence(x,now,'capture-1')})
    return {'schema':'frontier-experiments-v2','release':release,'tool_contracts':contracts,
            'budget':budget,'memory':memory,'evidence':{'timeline':timeline,
            'scope':'Synthetic monotonic clock; no camera, perception, network or robot used.'}}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True);a=parser.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    result=run();(a.out/'frontier.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'LOCAL_SYNTHETIC_COMPLETE','output':'frontier.json'},ensure_ascii=False))
if __name__=='__main__':main()
