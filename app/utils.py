import hashlib
import json
import re
from pathlib import Path
from typing import Optional

def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def normalize_prompt(p: str) -> str:
    p = p.strip()
    p = re.sub(r"\s+", " ", p)
    return p

def safe_json_load(s: str) -> Optional[dict]:
    try:
        return json.loads(s)
    except Exception:
        return None

def is_image_file(name: str) -> bool:
    return name.lower().endswith((".png", ".jpg", ".jpeg"))

def relative_to_base(path: Path, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except Exception:
        return path.name
