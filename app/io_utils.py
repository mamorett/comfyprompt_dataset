from io import BytesIO
import base64
from PIL import Image, PngImagePlugin
from pathlib import Path
from typing import Tuple, Dict, Any, Optional
import os
import streamlit as st
from PIL import Image, ImageOps
from typing import Tuple, Literal, Optional

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


ResizeMode = Literal["fit", "crop", "pad_square"]

def resize_image(
    img: Image.Image,
    target_size: Tuple[int, int],
    mode: ResizeMode = "fit",
    pad_color=(0, 0, 0, 0)  # transparent by default for PNG
) -> Image.Image:
    """
    Resize an image according to mode:
    - fit: maintain aspect ratio, fit within target_size, no crop/pad (may leave margins if you later paste)
    - crop: maintain aspect ratio, center-crop to fill target_size
    - pad_square: make a square canvas of max(target_size), fit inside and pad
    """
    w, h = img.size
    tw, th = target_size

    if mode == "fit":
        # thumbnail modifies in-place, keeps aspect
        img = img.copy()
        img.thumbnail((tw, th), Image.Resampling.LANCZOS)
        return img

    if mode == "crop":
        # scale to cover then center-crop
        src_ratio = w / h
        dst_ratio = tw / th
        if src_ratio > dst_ratio:
            # source is wider: scale by height
            scale = th / h
        else:
            # source is taller/narrower: scale by width
            scale = tw / w
        new_w, new_h = int(w * scale), int(h * scale)
        resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        left = (new_w - tw) // 2
        top = (new_h - th) // 2
        return resized.crop((left, top, left + tw, top + th))

    if mode == "pad_square":
        # square canvas with max dimension of tw,th (use max to pick intended square)
        size = max(tw, th)
        # fit inside square
        img = img.copy()
        img.thumbnail((size, size), Image.Resampling.LANCZOS)
        # create canvas
        if img.mode in ("RGBA", "LA"):
            bg = Image.new("RGBA", (size, size), pad_color)
        else:
            bg = Image.new("RGB", (size, size), pad_color[:3] if isinstance(pad_color, tuple) else (0, 0, 0))
        # center paste
        x = (size - img.width) // 2
        y = (size - img.height) // 2
        bg.paste(img, (x, y))
        return bg

    # fallback
    return img

def load_pil_image(path: str) -> Optional[Image.Image]:
    try:
        im = Image.open(path)
        im.load()
        return im
    except Exception:
        return None

def save_image_with_format(
    img: Image.Image,
    out_path: Path,
    fmt: Literal["PNG", "JPEG"] = "PNG",
    quality: int = 90
) -> bool:
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        params = {}
        if fmt.upper() == "JPEG":
            # ensure RGB
            if img.mode in ("RGBA", "LA"):
                img = img.convert("RGB")
            params.update(dict(quality=int(quality), optimize=True))
            img.save(str(out_path), format="JPEG", **params)
        else:
            img.save(str(out_path), format="PNG")
        return True
    except Exception:
        return False
