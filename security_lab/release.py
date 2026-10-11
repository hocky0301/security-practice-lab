"""Export only reviewed byte strings, not a working tree or its Git history.

The reviewer, source root, process, and output parent must be trusted. POSIX
openat/O_NOFOLLOW rejects symlinks in every *relative* component. The source
root's ancestry is an operator responsibility. No secret detector is claimed.
"""
from __future__ import annotations
import hashlib
import io
import os
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile
from .common import Rejected, label, sha256_text

MAX_FILE = 4 * 1024 * 1024
MAX_TOTAL = 32 * 1024 * 1024

def components(name: str) -> tuple[str, ...]:
    if type(name) is not str or not name or len(name) > 240:
        raise Rejected('INVALID_PATH')
    if not re.fullmatch(r'[A-Za-z0-9_./@-]+', name):
        raise Rejected('INVALID_PATH')
    bits = tuple(name.split('/'))
    if name.startswith('/') or any(x in ('', '.', '..', '.git') for x in bits):
        raise Rejected('INVALID_PATH')
    if PurePosixPath(name).is_absolute():
        raise Rejected('INVALID_PATH')
    return bits

def read_beneath(root: Path, name: str) -> bytes:
    bits = components(name)
    if not hasattr(os, 'O_NOFOLLOW') or not hasattr(os, 'O_DIRECTORY'):
        raise Rejected('PLATFORM_UNSUPPORTED')
    handles: list[int] = []
    try:
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        handles.append(fd)
        for part in bits[:-1]:
            fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            handles.append(fd)
        fd = os.open(bits[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        handles.append(fd)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE:
            raise Rejected('NOT_SMALL_REGULAR_FILE')
        data = bytearray()
        while True:
            piece = os.read(fd, min(65536, MAX_FILE + 1 - len(data)))
            if not piece:
                break
            data.extend(piece)
            if len(data) > MAX_FILE:
                raise Rejected('FILE_TOO_LARGE')
        return bytes(data)
    except OSError as exc:
        raise Rejected('SOURCE_UNREADABLE') from exc
    finally:
        for fd in reversed(handles):
            os.close(fd)

def build_archive(root: Path, manifest: dict) -> tuple[bytes, dict]:
    if type(manifest) is not dict or set(manifest) != {'schema', 'reviewed_by', 'files'}:
        raise Rejected('MANIFEST_SCHEMA')
    if manifest['schema'] != 'release-v1':
        raise Rejected('MANIFEST_SCHEMA')
    label(manifest['reviewed_by'])
    entries = manifest['files']
    if type(entries) is not list or not 1 <= len(entries) <= 1000:
        raise Rejected('MANIFEST_FILES')
    accepted: list[tuple[str, bytes]] = []
    seen: set[str] = set()
    total = 0
    for entry in entries:
        if type(entry) is not dict or set(entry) != {'path', 'sha256', 'approved'}:
            raise Rejected('ENTRY_SCHEMA')
        if entry['approved'] is not True:
            raise Rejected('NOT_APPROVED')
        name = entry['path']
        components(name)
        if name.casefold() in seen:
            raise Rejected('DUPLICATE_PATH')
        seen.add(name.casefold())
        expected = sha256_text(entry['sha256'])
        data = read_beneath(root, name)
        if hashlib.sha256(data).hexdigest() != expected:
            raise Rejected('CONTENT_CHANGED')
        total += len(data)
        if total > MAX_TOTAL:
            raise Rejected('TOTAL_TOO_LARGE')
        # Keep the very bytes checked. Never read the mutable path a second time.
        accepted.append((name, data))
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
        for name, data in sorted(accepted):
            info = zipfile.ZipInfo(name, (2000, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zf.writestr(info, data)
    blob = out.getvalue()
    return blob, {'files': len(accepted), 'input_bytes': total,
                  'archive_sha256': hashlib.sha256(blob).hexdigest()}
