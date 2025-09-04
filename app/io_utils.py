from io import BytesIO
import base64
from PIL import Image, PngImagePlugin
from pathlib import Path
from typing import Tuple, Dict, Any, Optional
import os
import streamlit as st

def check_file_access(file_path: Path) -> Dict[str, Any]:
    info = {
        "exists": False,
        "readable": False,
        "size": 0,
        "error": None,
        "absolute_path": str(file_path.resolve()),
    }
    try:
        info["exists"] = file_path.exists()
        if info["exists"]:
            info["readable"] = os.access(str(file_path), os.R_OK)
            info["size"] = file_path.stat().st_size
    except Exception as e:
        info["error"] = str(e)
    return info

@st.cache_data(show_spinner=False)
def cached_thumbnail(image_path: str, size=(150, 150)) -> str:
    try:
        path = Path(image_path)
        with Image.open(path) as img:
            img.thumbnail(size, Image.Resampling.LANCZOS)
            buf = BytesIO()
            img.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""

def base64_to_image(base64_str: str) -> Optional[Image.Image]:
    try:
        data = base64.b64decode(base64_str)
        img = Image.open(BytesIO(data))
        img.load()
        return img
    except Exception:
        return None

def load_image_from_path(file_path: Path) -> Tuple[str, Dict[str, Any]]:
    debug_info = check_file_access(file_path)
    try:
        if debug_info["exists"] and debug_info["readable"]:
            return cached_thumbnail(str(file_path)), debug_info
        return "", debug_info
    except Exception as e:
        debug_info["load_error"] = str(e)
        return "", debug_info
