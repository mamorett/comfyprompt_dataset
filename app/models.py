from dataclasses import dataclass
from typing import Optional

@dataclass
class ImageEntry:
    id: str
    original_name: str
    dataset_filename: str
    full_path: str  # absolute path at runtime
    prompt: str = ""
    image_data: str = ""
    modified: bool = False
    source: str = ""
    debug_info: Optional[dict] = None
    rel_path: Optional[str] = None  # relative to project root (includes dataset_dir and subfolders)

    def to_jsonl(self) -> dict:
        return {
            "id": self.id,
            "original_name": self.original_name,
            "dataset_filename": self.dataset_filename,
            "rel_path": self.rel_path,  # e.g. "./dataset1/sub/pippo.jpg"
            "prompt": self.prompt,
            "modified": self.modified,
            "source": self.source,
        }
