"""Lossless, portable transport for the complete committed reference trajectory."""
from __future__ import annotations
import base64
import gzip
from io import BytesIO
import json
from pathlib import Path

REFERENCE_PATH = Path(__file__).resolve().parent.parent / "examples/reference_compare.json.gz.b64"


def write_reference(value: dict, path: Path = REFERENCE_PATH) -> None:
    """No timestamps or source paths in gzip header; all numeric values retained."""
    raw = (json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")
    buffer = BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0, compresslevel=9) as archive:
        archive.write(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(base64.b64encode(buffer.getvalue()).decode("ascii") + "\n", encoding="ascii")


def read_reference(path: Path = REFERENCE_PATH) -> dict:
    encoded = path.read_text(encoding="ascii").strip()
    compressed = base64.b64decode(encoded, validate=True)
    return json.loads(gzip.decompress(compressed).decode("utf-8"))
