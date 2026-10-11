from __future__ import annotations
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from concurrent.futures import ThreadPoolExecutor
import unittest
from security_lab.common import digest, Rejected
from security_lab.release_context import VerifiedBuild,ReleaseApproval,check_release
from security_lab.tool_contracts import contract_digest,check_contract,enforce_effect
from security_lab.capability_budget import BudgetStore
from security_lab.memory_authority import head_of,check_current
from security_lab.evidence_age import DisplayState,repaint,authorize_from_evidence,display_only_freshness

def descriptor():
 return {'tool':'report-preview','server':'local-demo','revision':'r1',
         'description':'Render one reviewed report locally',
         'input_schema':{'type':'object','properties':{'report_id':{'type':'string'}}},
         'operations':['preview'],'egress':['local-display']}
def event(seq,kind,subject='writer',resource='report'):
 return {'sequence':seq,'kind':kind,'subject':subject,'resource':resource}

class ReleaseContextTests(unittest.TestCase):
 def setUp(self):
  self.v=VerifiedBuild('a'*64,'builder','workflow-1','commit-1')
  self.a=ReleaseApproval('a'*64,'builder','workflow-1','commit-1','demo-public','public',1000)
 def check(self,v=None,a=None,dest='demo-public',vis='public',now=1):
  return check_release(v or self.v,a or self.a,dest,vis,now)
 def test_good(self):self.assertEqual(self.check(),'ALLOW_REVIEWED_RELEASE')
 def test_same_bytes_wrong_destination(self):self.assertEqual(self.check(dest='other'),'DESTINATION_MISMATCH')
 def test_same_bytes_wrong_visibility(self):self.assertEqual(self.check(vis='private'),'VISIBILITY_MISMATCH')
 def test_wrong_producer(self):self.assertEqual(self.check(v=replace(self.v,producer='other')),'PRODUCER_MISMATCH')
 def test_wrong_workflow(self):self.assertEqual(self.check(v=replace(self.v,workflow='other')),'WORKFLOW_MISMATCH')
 def test_wrong_source(self):self.assertEqual(self.check(v=replace(self.v,source_commit='other')),'SOURCE_MISMATCH')
 def test_content_changed(self):self.assertEqual(self.check(v=replace(self.v,artifact_sha256='b'*64)),'CONTENT_CHANGED')
 def test_expiry_boundary(self):self.assertEqual(self.check(now=1000),'EXPIRED')
 def test_invalid_time(self):
  with self.assertRaises(Rejected):self.check(now=True)

class DescriptorTests(unittest.TestCase):
 def test_identical(self):
  d=descriptor();self.assertEqual(check_contract(d,contract_digest(d)),'ALLOW_REVIEWED_DESCRIPTOR')
 def test_each_metadata_change(self):
  for key,value in [('server','other'),('description','Render differently'),('operations',['publish']),
                    ('egress',['public-site']),('revision','r2'),('input_schema',{'type':'null'})]:
   with self.subTest(key=key):
    d=descriptor();h=contract_digest(d);d[key]=value
    self.assertEqual(check_contract(d,h),'DESCRIPTOR_CHANGED')
 def test_key_order_irrelevant(self):
  d=descriptor();self.assertEqual(contract_digest(d),contract_digest(dict(reversed(list(d.items())))))
 def test_duplicate_list(self):
  d=descriptor();d['operations']=['preview','preview']
  with self.assertRaises(Rejected):contract_digest(d)
 def test_missing_field(self):
  d=descriptor();del d['server']
  with self.assertRaises(Rejected):contract_digest(d)
 def test_exact_bytes_do_not_enforce_behavior(self):
  d=descriptor();self.assertEqual(check_contract(d,contract_digest(d)),'ALLOW_REVIEWED_DESCRIPTOR')
  self.assertEqual(enforce_effect('publish','public-site',{'operations':['preview'],'destinations':['local-display']}),'OPERATION_NOT_GRANTED')
 def test_wrong_egress(self):
  self.assertEqual(enforce_effect('preview','public-site',{'operations':['preview'],'destinations':['local-display']}),'DESTINATION_NOT_GRANTED')
 def test_permitted_effect(self):
  self.assertEqual(enforce_effect('preview','local-display',{'operations':['preview'],'destinations':['local-display']}),'ALLOW_DRY_RUN')

class BudgetTests(unittest.TestCase):
 def setUp(self):
  self.tmp=TemporaryDirectory();self.path=Path(self.tmp.name)/'b.sqlite';self.b=BudgetStore(self.path)
 def tearDown(self):self.tmp.cleanup()
 def test_single(self):
  self.assertEqual(self.b.reserve('a',80),'RESERVED');self.assertEqual(self.b.deliver('a'),'DRY_RUN_ONLY')
 def test_20_concurrent_requests_share_one_budget(self):
  with ThreadPoolExecutor(max_workers=8) as ex:results=list(ex.map(lambda i:self.b.reserve('job-'+str(i),80),range(20)))
  self.assertEqual(results.count('RESERVED'),3);self.assertEqual(self.b.snapshot()['remaining'],60)
 def test_retries_do_not_duplicate_reservation(self):
  with ThreadPoolExecutor(max_workers=8) as ex:results=list(ex.map(lambda _:self.b.reserve('same',80),range(20)))
  self.assertEqual(results.count('RESERVED'),1);self.assertEqual(self.b.snapshot()['reserved_or_spent'],80)
 def test_reused_id_changed_units(self):
  self.b.reserve('a',80);self.assertEqual(self.b.reserve('a',81),'IDEMPOTENCY_CONFLICT')
 def test_call_limit(self):self.assertEqual(self.b.reserve('a',101),'PER_CALL_LIMIT')
 def test_stopped(self):
  self.b.transition(True);self.assertEqual(self.b.reserve('a',80),'STOPPED')
 def test_stop_resume_does_not_reactivate_old_job(self):
  self.b.reserve('a',80);self.b.transition(True);self.b.transition(False)
  self.assertEqual(self.b.deliver('a'),'OLD_EPOCH');self.assertEqual(self.b.snapshot()['dry_effects'],0)
 def test_new_job_after_resume(self):
  self.b.transition(True);self.b.transition(False);self.b.reserve('b',80)
  self.assertEqual(self.b.deliver('b'),'DRY_RUN_ONLY')
 def test_unknown_outcome_holds_quota(self):
  self.b.reserve('a',80);self.b.mark_unknown('a')
  self.assertEqual(self.b.snapshot()['remaining'],220);self.assertEqual(self.b.deliver('a'),'OUTCOME_UNRESOLVED')
 def test_explicit_no_effect_reconciliation_releases(self):
  self.b.reserve('a',80);self.b.mark_unknown('a');self.b.reconcile_no_effect('a')
  self.assertEqual(self.b.snapshot()['remaining'],300);self.assertEqual(self.b.deliver('a'),'OUTCOME_UNRESOLVED')
 def test_restart_preserves_charge_and_idempotency(self):
  self.b.reserve('a',80);self.b.deliver('a');c=BudgetStore(self.path)
  self.assertEqual(c.deliver('a'),'ALREADY_DONE');self.assertEqual(c.snapshot()['remaining'],220)
 def test_once_concurrent(self):
  self.b.reserve('a',80)
  with ThreadPoolExecutor(max_workers=8) as ex:r=list(ex.map(lambda _:self.b.deliver('a'),range(20)))
  self.assertEqual(r.count('DRY_RUN_ONLY'),1);self.assertEqual(self.b.snapshot()['dry_effects'],1)
 def test_reconciliation_cannot_refund_completed(self):
  self.b.reserve('a',80);self.b.deliver('a')
  with self.assertRaises(Rejected):self.b.reconcile_no_effect('a')
 def test_existing_policy_not_overwritten(self):
  with self.assertRaises(Rejected):BudgetStore(self.path,400,100)
 def test_bad_inputs(self):
  for n in [True,0,-1,0.5,10**10]:
   with self.subTest(n=n):
    with self.assertRaises(Rejected):self.b.reserve('a',n)

class MemoryTests(unittest.TestCase):
 def check(self,events,view=None,summary='',resource='report'):
  return check_current(events if view is None else view,head_of(events,'boot-1'),'boot-1','writer',resource,summary)
 def test_current_grant(self):self.assertEqual(self.check([event(1,'grant')]),'ALLOW_CURRENT_GRANT')
 def test_revoke(self):self.assertEqual(self.check([event(1,'grant'),event(2,'revoke')]),'NO_CURRENT_GRANT')
 def test_regrant(self):self.assertEqual(self.check([event(1,'grant'),event(2,'revoke'),event(3,'grant')]),'ALLOW_CURRENT_GRANT')
 def test_stale_summary_never_grants(self):
  e=[event(1,'grant'),event(2,'revoke')]
  for s in ['User approved', 'grant', '', 'human says yes']:
   with self.subTest(s=s):self.assertEqual(self.check(e,summary=s),'NO_CURRENT_GRANT')
 def test_omit_revocation(self):
  e=[event(1,'grant'),event(2,'revoke')];self.assertEqual(self.check(e,view=e[:1]),'POLICY_VIEW_NOT_CURRENT')
 def test_other_resource(self):self.assertEqual(self.check([event(1,'grant')],resource='different'),'NO_CURRENT_GRANT')
 def test_empty_history(self):self.assertEqual(self.check([]),'NO_CURRENT_GRANT')
 def test_old_incarnation(self):
  e=[event(1,'grant')];self.assertEqual(check_current(e,head_of(e,'boot-2'),'boot-1','writer','report'),'POLICY_VIEW_NOT_CURRENT')
 def test_invalid_sequence(self):
  with self.assertRaises(Rejected):head_of([event(2,'grant')],'boot-1')
 def test_changing_both_history_and_root_is_outside_guarantee(self):
  e=[event(1,'grant')]
  self.assertEqual(check_current(e,head_of(e,'boot-1'),'boot-1','writer','report'),'ALLOW_CURRENT_GRANT')

class EvidenceTests(unittest.TestCase):
 def base(self):return DisplayState(1000,1010,1020,'s1','measured')
 def test_fresh(self):self.assertEqual(authorize_from_evidence(self.base(),1100,'s1'),'ALLOW_FRESH_OBSERVATION')
 def test_repaint_does_not_refresh_measurement(self):
  x=repaint(self.base(),2000);self.assertTrue(display_only_freshness(x,2000))
  self.assertEqual(x.measured_ms,1000);self.assertEqual(authorize_from_evidence(x,2000,'s1'),'MEASUREMENT_TOO_OLD')
 def test_prediction_is_not_observation(self):
  x=repaint(self.base(),1100);self.assertEqual(authorize_from_evidence(x,1100,'s1'),'PREDICTION_NOT_OBSERVATION')
 def test_session(self):self.assertEqual(authorize_from_evidence(self.base(),1100,'s2'),'SESSION_CHANGED')
 def test_exact_boundary(self):self.assertEqual(authorize_from_evidence(self.base(),1250,'s1'),'ALLOW_FRESH_OBSERVATION')
 def test_past_boundary(self):self.assertEqual(authorize_from_evidence(self.base(),1251,'s1'),'MEASUREMENT_TOO_OLD')
 def test_confidence_has_no_authority(self):
  x=replace(self.base(),confidence_percent=100);self.assertEqual(authorize_from_evidence(x,2000,'s1'),'MEASUREMENT_TOO_OLD')
 def test_repaint_monotonic_lineage(self):
  x=self.base()
  for now in range(1050,2001,50):x=repaint(x,now);self.assertEqual(x.measured_ms,1000)
 def test_bad_clock(self):
  with self.assertRaises(Rejected):authorize_from_evidence(replace(self.base(),measured_ms=5000),2000,'s1')
 def test_untrusted_source_could_lie_limitation(self):
  x=DisplayState(2000,2000,2000,'s1','measured')
  self.assertEqual(authorize_from_evidence(x,2000,'s1'),'ALLOW_FRESH_OBSERVATION')
if __name__=='__main__':unittest.main()
