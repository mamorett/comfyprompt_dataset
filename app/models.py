from dataclasses import dataclass, asdict
from typing import Optional

@dataclass
class ImageEntry:
    id: str
    original_name: str
    dataset_filename: str
    full_path: str  # absolute path
    prompt: str = ""
    image_data: str = ""  # optional base64 thumbnail (avoid storing for all)
    modified: bool = False
    source: str = ""       # uploaded_to_dataset | rescanned_dataset | jsonl
    debug_info: Optional[dict] = None

    def to_jsonl(self) -> dict:
        # What we persist; keep stable fields only
        return {
            "id": self.id,
            "original_name": self.original_name,
            "dataset_filename": self.dataset_filename,
            "full_path": self.full_path,
            "prompt": self.prompt,
            "modified": self.modified,
            "source": self.source,
        }
