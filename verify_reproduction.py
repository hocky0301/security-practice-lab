"""Run the local tests and compare regenerated synthetic evidence."""
from __future__ import annotations
import contextlib
import hashlib
import io
import json
from pathlib import Path
import platform
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent

def main() -> int:
    sys.path.insert(0, str(ROOT))
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'))
    capture = io.StringIO()
    with contextlib.redirect_stdout(capture):
        test_result = unittest.TextTestRunner(stream=capture, verbosity=2).run(suite)
    print(capture.getvalue(), end='')
    from security_lab.experiments import run
    with tempfile.TemporaryDirectory() as work:
        actual = run(Path(work))
    saved = json.loads((ROOT / 'results/experiments.json').read_text())
    same = actual == saved
    from security_lab.frontier_experiments import run as run_frontier
    frontier_actual = run_frontier()
    frontier_saved = json.loads((ROOT / 'results/frontier.json').read_text())
    frontier_same = frontier_actual == frontier_saved
    report = {
        'python': platform.python_version(), 'platform': sys.platform,
        'tests_run': test_result.testsRun, 'failures': len(test_result.failures),
        'errors': len(test_result.errors), 'skipped': len(test_result.skipped),
        'stored_result_matches': same,
        'frontier_result_matches': frontier_same,
        'scope': 'local-synthetic; no real identity, network, LLM or actuator',
        'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted((ROOT / 'security_lab').glob('*.py'))},
    }
    (ROOT / 'verification_report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 0 if test_result.wasSuccessful() and not test_result.skipped and same and frontier_same else 1

if __name__ == '__main__':
    raise SystemExit(main())
