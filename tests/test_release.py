import copy
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
import zipfile
from security_lab.common import Rejected
from security_lab.release import build_archive, components

class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'code').mkdir()
        (self.root / 'code/main.py').write_bytes(b'print("demo")\n')
        (self.root / 'private').mkdir()
        (self.root / 'private/note.txt').write_text('LOCAL FIXTURE ONLY')
        self.manifest = {'schema': 'release-v1', 'reviewed_by': 'human-reviewer', 'files': [
            {'path': 'code/main.py', 'sha256': hashlib.sha256(b'print("demo")\n').hexdigest(), 'approved': True}]}
    def tearDown(self): self.temp.cleanup()
    def test_only_reviewed_files(self):
        blob, report = build_archive(self.root, self.manifest)
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            self.assertEqual(z.namelist(), ['code/main.py'])
        self.assertEqual(report['files'], 1)
    def test_changed_bytes_rejected(self):
        (self.root / 'code/main.py').write_bytes(b'changed')
        with self.assertRaisesRegex(Rejected, 'CONTENT_CHANGED'): build_archive(self.root, self.manifest)
    def test_unapproved_rejected(self):
        self.manifest['files'][0]['approved'] = False
        with self.assertRaisesRegex(Rejected, 'NOT_APPROVED'): build_archive(self.root, self.manifest)
    def test_truthy_approval_rejected(self):
        self.manifest['files'][0]['approved'] = 'yes'
        with self.assertRaises(Rejected): build_archive(self.root, self.manifest)
    def test_empty_rejected(self):
        self.manifest['files'] = []
        with self.assertRaises(Rejected): build_archive(self.root, self.manifest)
    def test_duplicate_rejected(self):
        self.manifest['files'] *= 2
        with self.assertRaisesRegex(Rejected, 'DUPLICATE'): build_archive(self.root, self.manifest)
    def test_missing_file_rejected(self):
        (self.root / 'code/main.py').unlink()
        with self.assertRaises(Rejected): build_archive(self.root, self.manifest)
    def test_file_symlink_rejected(self):
        p = self.root / 'code/main.py'; p.unlink(); p.symlink_to('../private/note.txt')
        with self.assertRaises(Rejected): build_archive(self.root, self.manifest)
    def test_directory_symlink_rejected(self):
        p=self.root / 'code/main.py'; p.unlink(); (self.root/'code').rmdir()
        (self.root/'code').symlink_to(self.root/'private', target_is_directory=True)
        with self.assertRaises(Rejected): build_archive(self.root, self.manifest)
    def test_root_symlink_rejected(self):
        (self.root/'alias').symlink_to(self.root/'code',target_is_directory=True)
        with self.assertRaises(Rejected): build_archive(self.root/'alias', self.manifest)
    def test_path_constraints(self):
        for bad in ['../x','/x','x//y','x/./y','x/../y','x\\y','x\ny','.git/config']:
            with self.subTest(path=repr(bad)), self.assertRaises(Rejected): components(bad)
    def test_deterministic_zip(self):
        a, _ = build_archive(self.root, self.manifest)
        b, _ = build_archive(self.root, self.manifest)
        self.assertEqual(a,b)
    def test_additional_fields_rejected(self):
        self.manifest['recursive'] = True
        with self.assertRaises(Rejected): build_archive(self.root, self.manifest)
    def test_new_unlisted_file_not_exported(self):
        (self.root/'code/new.py').write_text('new file')
        a, _=build_archive(self.root,self.manifest)
        with zipfile.ZipFile(io.BytesIO(a)) as z: self.assertNotIn('code/new.py',z.namelist())
