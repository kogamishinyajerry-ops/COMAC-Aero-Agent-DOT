#!/usr/bin/env python3
"""Read/extract byte-identical archived evidence using only the standard library."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def records(root=HERE):
    return json.loads((root / 'evidence/storage.json').read_text(encoding='utf-8'))['artifacts']


def checked_path(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Artifact path escapes package')
    return path


def verify(data, record):
    if len(data) != record['bytes'] or hashlib.sha256(data).hexdigest() != record['sha256']:
        raise ValueError('Artifact identity mismatch: ' + record['path'])
    return data


def unpack(record, root=HERE):
    if record['codec'] != 'gzip-concatenated-parts':
        raise ValueError('Unsupported evidence encoding')
    chunks = [verify(checked_path(root, p['path']).read_bytes(), p) for p in record['parts']]
    compressed = b''.join(chunks)
    if len(compressed) != record['compressed_bytes']:
        raise ValueError('Compressed size mismatch')
    return verify(gzip.decompress(compressed), record)


def read_bytes(path, root=HERE):
    path = Path(path).resolve()
    if path.is_file():
        return path.read_bytes()
    for record in records(root):
        if checked_path(root, record['path']) == path:
            return unpack(record, root)
    raise FileNotFoundError(path)


def read_json(path):
    return json.loads(read_bytes(path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract-to', type=Path, help='New output directory; never overwrites an existing directory')
    args = parser.parse_args()
    artifacts = [(r, unpack(r)) for r in records()]
    if args.extract_to:
        args.extract_to.mkdir(parents=True, exist_ok=False)
        for record, data in artifacts:
            target = checked_path(args.extract_to, record['path'])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    print(json.dumps({'exact_original_artifacts_verified': len(artifacts), 'extracted_to': str(args.extract_to) if args.extract_to else None}, indent=2))


if __name__ == '__main__':
    main()
