from typing import List, Dict, Tuple
from pathlib import Path
import json
import streamlit as st
from .models import ImageEntry

def save_to_jsonl_content(data: List[ImageEntry], dataset_dir: Path) -> str:
    # Save a small manifest header with base_dir for portability
    lines = []
    manifest = {"__manifest__": {"base_dir": str(dataset_dir.resolve())}}
    lines.append(json.dumps(manifest, ensure_ascii=False))
    for item in data:
        lines.append(json.dumps(item.to_jsonl(), ensure_ascii=False))
    return "\n".join(lines)

def load_jsonl_data(jsonl_content: str) -> Tuple[List[ImageEntry], str]:
    """
    Returns: (entries, base_dir)
    """
    lines = [ln for ln in jsonl_content.split("\n") if ln.strip()]
    base_dir = ""
    entries: List[ImageEntry] = []

    for idx, line in enumerate(lines):
        try:
            data = json.loads(line)
        except Exception:
            continue
        if "__manifest__" in data and "base_dir" in data["__manifest__"]:
            base_dir = data["__manifest__"]["base_dir"]
            continue
        # Back-compat: if no manifest, base_dir stays empty
        id_ = data.get("id")
        original_name = data.get("original_name", "")
        dataset_filename = data.get("dataset_filename", original_name)
        full_path = data.get("full_path", "")
        prompt = data.get("prompt", "")
        modified = data.get("modified", False)
        source = data.get("source", "jsonl")

        entries.append(
            ImageEntry(
                id=id_,
                original_name=original_name,
                dataset_filename=dataset_filename,
                full_path=full_path,
                prompt=prompt,
                modified=modified,
                source=source,
                image_data="",
                debug_info=None,
            )
        )

    return entries, base_dir
