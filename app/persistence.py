from typing import List, Tuple
from pathlib import Path
import json
from .models import ImageEntry

def save_to_jsonl_content(data: List[ImageEntry], dataset_dir: Path, resize_policy: dict | None = None) -> str:
    """
    Save JSONL with portable relative paths:
    - __manifest__.base_dir: exactly as user typed (prefer relative like ./dataset1)
    - Each entry rel_path: base_dir + dataset_filename (including subfolders if dataset_filename has any)
      Example: base_dir="./dataset1", dataset_filename="sub/pippo.jpg" -> rel_path="./dataset1/sub/pippo.jpg"
    - Do not persist full_path
    """
    lines = []
    base_dir_str = str(dataset_dir) if str(dataset_dir) else "."
    if not Path(base_dir_str).is_absolute() and not base_dir_str.startswith("./"):
        base_dir_str = f"./{base_dir_str}"

    manifest = {"__manifest__": {"base_dir": base_dir_str}}
    if resize_policy:
        manifest["__manifest__"]["resize"] = resize_policy  # save policy here

    lines.append(json.dumps(manifest, ensure_ascii=False))

    for item in data:
        rel_path = f"{base_dir_str.rstrip('/')}/{item.dataset_filename.lstrip('/')}"
        item.rel_path = rel_path
        lines.append(json.dumps(item.to_jsonl(), ensure_ascii=False))

    return "\n".join(lines)

def load_jsonl_data(jsonl_content: str) -> Tuple[List[ImageEntry], str, dict | None]:
    """
    Load JSONL:
    - full_path = Path(rel_path).resolve()
    - base_dir is informative (can be used to validate), but rel_path is authoritative
    """
    lines = [ln for ln in jsonl_content.split("\n") if ln.strip()]
    base_dir = ""
    resize_policy = None
    entries: List[ImageEntry] = []

    for line in lines:
        data = json.loads(line)
        if "__manifest__" in data:
            base_dir = data["__manifest__"].get("base_dir", "")
            resize_policy = data["__manifest__"].get("resize")
            continue

        id_ = data.get("id")
        original_name = data.get("original_name", "")
        dataset_filename = data.get("dataset_filename", original_name)
        rel_path = data.get("rel_path")

        prompt = data.get("prompt", "")
        modified = data.get("modified", False)
        source = data.get("source", "jsonl")

        # Build absolute full path from rel_path relative to current working dir
        full_path = str(Path(rel_path).resolve()) if rel_path else ""

        entries.append(
            ImageEntry(
                id=id_,
                original_name=original_name,
                dataset_filename=dataset_filename,
                full_path=full_path,
                rel_path=rel_path,
                prompt=prompt,
                modified=modified,
                source=source,
                image_data="",
                debug_info=None,
            )
        )

    return entries, base_dir, resize_policy

