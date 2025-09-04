from typing import List, Tuple
from pathlib import Path
import json
from .models import ImageEntry

def save_to_jsonl_content(data: List[ImageEntry], dataset_dir: Path) -> str:
    """
    Save JSONL with portable relative paths:
    - __manifest__.base_dir: exactly as user typed (prefer relative like ./dataset1)
    - Each entry rel_path: base_dir + dataset_filename (including subfolders if dataset_filename has any)
      Example: base_dir="./dataset1", dataset_filename="sub/pippo.jpg" -> rel_path="./dataset1/sub/pippo.jpg"
    - Do not persist full_path
    """
    lines = []
    base_dir_str = str(dataset_dir) if str(dataset_dir) else "."
    # Normalize base_dir to ensure it starts with "./" if relative and not already
    if not Path(base_dir_str).is_absolute() and not base_dir_str.startswith("./"):
        base_dir_str = f"./{base_dir_str}"

    # manifest
    lines.append(json.dumps({"__manifest__": {"base_dir": base_dir_str}}, ensure_ascii=False))

    for item in data:
        # dataset_filename may or may not include subfolders; we honor it
        rel_path = f"{base_dir_str.rstrip('/')}/{item.dataset_filename.lstrip('/')}"
        item.rel_path = rel_path
        lines.append(json.dumps(item.to_jsonl(), ensure_ascii=False))

    return "\n".join(lines)

def load_jsonl_data(jsonl_content: str) -> Tuple[List[ImageEntry], str]:
    """
    Load JSONL:
    - full_path = Path(rel_path).resolve()
    - base_dir is informative (can be used to validate), but rel_path is authoritative
    """
    lines = [ln for ln in jsonl_content.split("\n") if ln.strip()]
    base_dir = ""
    entries: List[ImageEntry] = []

    for line in lines:
        data = json.loads(line)
        if "__manifest__" in data and "base_dir" in data["__manifest__"]:
            base_dir = data["__manifest__"]["base_dir"]
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

    return entries, base_dir
