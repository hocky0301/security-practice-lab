import concurrent.futures
from pathlib import Path
import tempfile
import unittest
from security_lab.common import Rejected
from security_lab.authority import Authority

def request():
    return {'operation':'preview_motion','resource':'paper-stage','position_mdeg':1000,
            'duration_ms':300,'observation_id':'frame-1'}

class AuthorityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'state.sqlite'
        self.a=Authority(self.path);self.r=request()
        self.a.observe(observation_id='frame-1', measured_at=100,target='paper-stage')
        self.g=self.a.approve(self.r,actor='author',audience='local-preview',now=100)
    def tearDown(self): self.tmp.cleanup()
    def execute(self, **kw):
        args={'actor':'author','audience':'local-preview','now':101};args.update(kw)
        return self.a.execute(self.g,self.r,**args)
    def test_exact_approved_request(self): self.assertEqual(self.execute()['effect'],'DRY_RUN_ONLY')
    def test_changed_request(self):
        self.r['position_mdeg']=2000
        with self.assertRaisesRegex(Rejected,'CONTENT_CHANGED'): self.execute()
        self.assertEqual(self.a.receipts(),0)
    def test_changed_duration(self):
        self.r['duration_ms']=301
        with self.assertRaises(Rejected): self.execute()
    def test_wrong_actor(self):
        with self.assertRaisesRegex(Rejected,'IDENTITY'): self.execute(actor='someone')
    def test_wrong_audience(self):
        with self.assertRaises(Rejected): self.execute(audience='remote-preview')
    def test_replay(self):
        self.execute()
        with self.assertRaisesRegex(Rejected,'ALREADY_USED'): self.execute()
    def test_restart_preserves_used(self):
        self.execute();self.a=Authority(self.path)
        with self.assertRaises(Rejected): self.execute()
    def test_expired(self):
        with self.assertRaisesRegex(Rejected,'EXPIRED'): self.execute(now=130)
    def test_clock_before_issue(self):
        with self.assertRaises(Rejected): self.execute(now=99)
    def test_stop(self):
        self.a.stop()
        with self.assertRaisesRegex(Rejected,'STOPPED'): self.execute()
    def test_resume_does_not_resurrect(self):
        self.a.stop();self.a.resume(reviewer_role='human')
        with self.assertRaisesRegex(Rejected,'REVOKED'): self.execute()
    def test_policy_change_revokes(self):
        self.a.set_policy('motion-policy-v2')
        with self.assertRaises(Rejected): self.execute()
    def test_model_cannot_approve(self):
        with self.assertRaises(Rejected):
            self.a.approve(self.r,actor='author',audience='local-preview',now=100,reviewer_role='model')
    def test_model_cannot_resume(self):
        with self.assertRaises(Rejected): self.a.resume(reviewer_role='model')
    def test_stale_observation(self):
        with self.assertRaisesRegex(Rejected,'OBSERVATION_STALE'): self.execute(now=106)
    def test_predicted_input_refused(self):
        self.a.observe(observation_id='forecast-1', measured_at=100,target='paper-stage',trusted=False)
        r=request();r['observation_id']='forecast-1'
        g=self.a.approve(r,actor='author',audience='local-preview',now=100)
        with self.assertRaises(Rejected): self.a.execute(g,r,actor='author',audience='local-preview',now=101)
    def test_observation_id_not_overwritable(self):
        with self.assertRaises(Rejected): self.a.observe(observation_id='frame-1',measured_at=102,target='paper-stage')
    def test_unknown_operation(self):
        self.r['operation']='write-anywhere'
        with self.assertRaises(Rejected): self.execute()
    def test_out_of_range(self):
        self.r['position_mdeg']=30001
        with self.assertRaises(Rejected): self.execute()
    def test_float_rejected(self):
        self.r['position_mdeg']=float('nan')
        with self.assertRaises(Rejected): self.execute()
    def test_boolean_not_integer(self):
        self.r['duration_ms']=True
        with self.assertRaises(Rejected): self.execute()
    def test_unknown_fields_rejected(self):
        self.r['extra']='not supported'
        with self.assertRaises(Rejected): self.execute()
    def test_concurrent_single_consumption(self):
        def attempt(_):
            try:
                self.execute();return 'accepted'
            except Rejected: return 'denied'
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            outcomes=list(pool.map(attempt, range(8)))
        self.assertEqual(outcomes.count('accepted'),1)
        self.assertEqual(self.a.receipts(),1)
    def test_stop_survives_restart(self):
        self.a.stop();self.a=Authority(self.path)
        with self.assertRaises(Rejected): self.execute()
    def test_new_grant_after_resume(self):
        self.a.stop();self.a.resume(reviewer_role='human')
        self.g=self.a.approve(self.r,actor='author',audience='local-preview',now=101)
        self.assertTrue(self.execute()['accepted'])
