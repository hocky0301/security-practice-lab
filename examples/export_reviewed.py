"""Export a trusted, human-reviewed manifest. Never pushes to a remote.

The operator must control the manifest, source-root ancestry and output parent.
The output must be outside the source tree and must not already exist.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from security_lab.common import Rejected
from security_lab.release import build_archive

def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    try:
        source=a.root.resolve(strict=True)
        target=a.output.parent.resolve(strict=True)/a.output.name
        if target==source or source in target.parents:
            raise Rejected('OUTPUT_MUST_BE_OUTSIDE_SOURCE')
        manifest=json.loads(a.manifest.read_text(encoding='utf-8'))
        blob,report=build_archive(a.root,manifest)
        with target.open('xb') as f:
            f.write(blob)
        print(json.dumps({'status':'EXPORTED_NOT_PUBLISHED',**report}))
        return 0
    except Rejected as e:
        print(json.dumps({'status':'BLOCKED','reason':str(e)}));return 1
    except (OSError,ValueError,TypeError) as e:
        print(json.dumps({'status':'BLOCKED','reason':type(e).__name__}));return 1
if __name__=='__main__':raise SystemExit(main())
