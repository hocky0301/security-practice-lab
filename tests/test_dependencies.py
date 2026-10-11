import copy
import unittest
from security_lab.common import Rejected
from security_lab.dependencies import evaluate

NOW='2026-10-09T12:00:00Z'
INV='a'*64

def scan():
    return {'schema':'scan-normalized-v1', 'complete':True, 'skipped':[], 'checked':2,
        'inventory_sha256':INV, 'generated_at':'2026-10-09T11:00:00Z', 'scanner':'fixture-v1',
        'findings':[{'package':'demo-package','version':'1.0','advisory':'DEMO-001','severity':'high'}]}

def exception():
    return {'package':'demo-package','version':'1.0','advisory':'DEMO-001','owner':'maintainer',
        'reason':'Temporary local fixture exception', 'approved_at':'2026-10-09T10:00:00Z',
        'expires_at':'2026-10-10T10:00:00Z','inventory_sha256':INV}

class DependencyTests(unittest.TestCase):
    def run_case(self, r=None, e=None):
        return evaluate(scan() if r is None else r, [] if e is None else e, now=NOW, expected_inventory=INV)
    def test_high_blocks(self): self.assertEqual(self.run_case()['verdict'],'BLOCK')
    def test_reviewed_exception_passes(self): self.assertEqual(self.run_case(e=[exception()])['verdict'],'PASS')
    def test_expired_blocks(self):
        e=exception();e['expires_at']=NOW
        with self.assertRaises(Rejected): self.run_case(e=[e])
    def test_no_owner_blocks(self):
        e=exception();e['owner']=''
        with self.assertRaises(Rejected): self.run_case(e=[e])
    def test_short_reason_blocks(self):
        e=exception();e['reason']='ok'
        with self.assertRaises(Rejected): self.run_case(e=[e])
    def test_incomplete_blocks(self):
        r=scan();r['complete']=False
        with self.assertRaisesRegex(Rejected,'SCAN_INCOMPLETE'): self.run_case(r)
    def test_skip_blocks(self):
        r=scan();r['skipped']=['demo-two']
        with self.assertRaises(Rejected): self.run_case(r)
    def test_zero_count_blocks(self):
        r=scan();r['checked']=0
        with self.assertRaises(Rejected): self.run_case(r)
    def test_boolean_count_blocks(self):
        r=scan();r['checked']=True
        with self.assertRaises(Rejected): self.run_case(r)
    def test_stale_report_blocks(self):
        r=scan();r['generated_at']='2026-10-01T12:00:00Z'
        with self.assertRaises(Rejected): self.run_case(r)
    def test_future_report_blocks(self):
        r=scan();r['generated_at']='2026-10-10T12:00:00Z'
        with self.assertRaises(Rejected): self.run_case(r)
    def test_wrong_inventory_blocks(self):
        r=scan();r['inventory_sha256']='b'*64
        with self.assertRaises(Rejected): self.run_case(r)
    def test_unknown_severity_blocks(self):
        r=scan();r['findings'][0]['severity']='unknown'
        with self.assertRaises(Rejected): self.run_case(r)
    def test_orphan_exception_blocks(self):
        e=exception();e['version']='2.0'
        with self.assertRaises(Rejected): self.run_case(e=[e])
    def test_clean_complete_passes(self):
        r=scan();r['findings']=[]
        self.assertEqual(self.run_case(r)['verdict'],'PASS')
    def test_expiration_window_bounded(self):
        e=exception();e['expires_at']='2027-01-01T00:00:00Z'
        with self.assertRaises(Rejected): self.run_case(e=[e])
