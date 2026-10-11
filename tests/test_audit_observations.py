import copy
import unittest
from security_lab.audit import event_record,make_chain,verify
from security_lab.common import Rejected, canonical
from security_lab.observations import usable,residual_authority_area

class AuditTests(unittest.TestCase):
    def setUp(self):
        self.records=[event_record(event='accepted', request_hash='a'*64,epoch=1,
            reason='ok',sequence=i,observed_at=100+i) for i in range(1,4)]
        self.chain,self.anchor=make_chain(self.records)
    def test_verified(self): self.assertTrue(verify(self.chain,self.anchor))
    def test_mutation_detected(self):
        self.chain[0]['record']['reason']='changed'
        with self.assertRaises(Rejected): verify(self.chain,self.anchor)
    def test_truncation_detected(self):
        with self.assertRaises(Rejected): verify(self.chain[:-1],self.anchor)
    def test_reorder_detected(self):
        with self.assertRaises(Rejected): verify(list(reversed(self.chain)),self.anchor)
    def test_rebuilt_chain_does_not_match_old_anchor(self):
        self.records[0]['reason']='changed'
        rebuilt,_=make_chain(self.records)
        with self.assertRaises(Rejected): verify(rebuilt,self.anchor)
    def test_replaced_anchor_is_out_of_threat_model(self):
        self.records[0]['reason']='changed'
        rebuilt,new_anchor=make_chain(self.records)
        self.assertTrue(verify(rebuilt,new_anchor))
    def test_no_payload_field(self):
        self.records[0]['payload']='not for log'
        with self.assertRaises(Rejected): make_chain(self.records)
    def test_free_text_reason_not_allowed(self):
        self.records[0]['reason']='multi line\nvalue'
        with self.assertRaises(Rejected): make_chain(self.records)
    def test_sequence_gap(self):
        self.records[1]['sequence']=9
        with self.assertRaises(Rejected): make_chain(self.records)
    def test_hash_is_not_anonymization(self):
        # Demonstrates a limitation rather than claiming privacy from hashing.
        from security_lab.common import digest
        known={digest({'choice':v}):v for v in ['yes','no']}
        self.assertEqual(known[digest({'choice':'yes'})],'yes')

class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.o=dict(source='trusted-local-adapter',kind='measured',clock='local-monotonic-ms',
                    observed_at=1000,sequence=2,session='session-a',quality='usable')
    def check(self): return usable(self.o,now=1100,session='session-a',current_seq=1)
    def test_fresh(self): self.assertTrue(self.check())
    def test_prediction_not_measurement(self):
        self.o['kind']='prediction'
        with self.assertRaises(Rejected): self.check()
    def test_unknown_source(self):
        self.o['source']='untrusted'
        with self.assertRaises(Rejected): self.check()
    def test_wrong_session(self):
        self.o['session']='session-b'
        with self.assertRaises(Rejected): self.check()
    def test_wrong_clock(self):
        self.o['clock']='wall-clock'
        with self.assertRaises(Rejected): self.check()
    def test_old_sequence(self):
        self.o['sequence']=1
        with self.assertRaises(Rejected): self.check()
    def test_future(self):
        self.o['observed_at']=1101
        with self.assertRaises(Rejected): self.check()
    def test_stale(self):
        self.o['observed_at']=100
        with self.assertRaises(Rejected): self.check()
    def test_unknown_quality(self):
        self.o['quality']='unknown'
        with self.assertRaises(Rejected): self.check()
    def test_labels_do_not_prove_physical_truth(self):
        # Same metadata could describe an inaccurate sensor. This check cannot tell.
        self.assertTrue(self.check())
    def test_authority_area(self):
        self.assertEqual(residual_authority_area([
            {'second':0,'operations':3},{'second':10,'operations':1},{'second':30,'operations':0}]),50)
    def test_nonmonotonic_area(self):
        with self.assertRaises(Rejected): residual_authority_area([
            {'second':10,'operations':3},{'second':10,'operations':0}])
    def test_canonical_key_order(self): self.assertEqual(canonical({'a':1,'b':2}),canonical({'b':2,'a':1}))
    def test_canonical_rejects_float(self):
        with self.assertRaises(Rejected): canonical({'x':1.0})
