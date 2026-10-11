from pathlib import Path
import tempfile
import unittest
from security_lab.authority import Authority
from security_lab.common import Rejected,digest
from security_lab.recovery import recover_preview
from test_authority import request

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.snapshot={'schema':'motion-data-v1','motions':[request()]}
        self.h=digest(self.snapshot)
    def tearDown(self):self.tmp.cleanup()
    def recover(self):return recover_preview(self.snapshot,expected_hash=self.h,trusted_epoch=8,destination=self.root/'new')
    def test_new_stopped_state(self):
        r=self.recover();self.assertTrue(r['stopped']);self.assertEqual(r['epoch'],9)
    def test_no_old_authority(self):
        self.recover();a=Authority(self.root/'new/authority.sqlite')
        with a._db() as c:self.assertEqual(c.execute('SELECT count(*) FROM grants').fetchone()[0],0)
    def test_refuses_old_grants_in_snapshot(self):
        self.snapshot['grants']=[];self.h=digest(self.snapshot)
        with self.assertRaises(Rejected):self.recover()
        self.assertFalse((self.root/'new').exists())
    def test_corrupt_data(self):
        self.snapshot['motions'][0]['duration_ms']=999
        with self.assertRaises(Rejected):self.recover()
    def test_no_overwrite(self):
        (self.root/'new').mkdir()
        with self.assertRaises(FileExistsError):self.recover()
    def test_approve_blocked_after_recovery(self):
        self.recover();a=Authority(self.root/'new/authority.sqlite')
        with self.assertRaisesRegex(Rejected,'STOPPED'):
            a.approve(request(),actor='author',audience='local-preview',now=100)
    def test_old_grant_not_known_after_manual_resume(self):
        self.recover();a=Authority(self.root/'new/authority.sqlite');a.resume(reviewer_role='human')
        with self.assertRaisesRegex(Rejected,'UNKNOWN_GRANT'):
            a.execute('old-id',request(),actor='author',audience='local-preview',now=101)
    def test_invalid_motion_rejected_before_writing(self):
        self.snapshot['motions'][0]['duration_ms']=99999;self.h=digest(self.snapshot)
        with self.assertRaises(Rejected):self.recover()
        self.assertFalse((self.root/'new').exists())
