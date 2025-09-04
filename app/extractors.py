import json
from typing import Dict, Any, Optional, List
from PIL import Image, PngImagePlugin
from pathlib import Path
import streamlit as st
from .utils import normalize_prompt, safe_json_load

# Core cached extraction entry
@st.cache_data(show_spinner=False)
def cached_extract_prompts(file_path: str) -> str:
    return extract_all_prompts(Path(file_path))

def extract_all_prompts(file_path: Path) -> str:
    prompts: List[str] = []
    seen = set()

    def add(p: Optional[str]):
        if not p:
            return
        np = normalize_prompt(p)
        if np and np not in seen:
            seen.add(np)
            prompts.append(np)

    add(extract_positive_prompt(file_path))
    for p in extract_positive_prompts_comfyui(file_path):
        add(p)

    if not prompts:
        return ""
    return max(prompts, key=len)

def extract_positive_prompt(file_path: Path) -> Optional[str]:
    try:
        with Image.open(file_path) as img:
            if img.format != "PNG":
                return None

            meta = img.info or {}
            # Try JSON first
            params = meta.get("parameters")
            if isinstance(params, str):
                parsed = safe_json_load(params)
                if isinstance(parsed, dict):
                    for key in ["Positive prompt", "positive prompt", "Positive Prompt",
                                "positive_prompt", "prompt", "Prompt"]:
                        if key in parsed:
                            return str(parsed[key])

            # Otherwise parse text format with Positive prompt and Negative prompt lines
            if isinstance(params, str):
                return parse_text_parameters(params)

            # Also inspect iTXt/tEXt chunks (PIL keeps most in info, but be safe)
            # Workaround: if "parameters" not present above
            for k, v in meta.items():
                if isinstance(v, str) and ("Positive prompt" in v or "Negative prompt" in v):
                    result = parse_text_parameters(v)
                    if result:
                        return result
    except Exception:
        return None
    return None

def parse_text_parameters(parameters_data: str) -> Optional[str]:
    # A1111-like text: Positive prompt: ... \n Negative prompt: ... \n other
    lines = [ln.strip() for ln in parameters_data.split("\n")]
    pos_started = False
    buf: List[str] = []
    for line in lines:
        lc = line.lower()
        if lc.startswith("positive prompt:"):
            pos_started = True
            buf = [line.split(":", 1)[1].strip()]
            continue
        if pos_started:
            # Stop at another header line
            if ":" in line:
                # Often "Negative prompt:" or others
                break
            if line:
                buf.append(line)
    if buf:
        return " ".join(buf).strip()
    return None

def extract_positive_prompts_comfyui(file_path: Path) -> List[str]:
    try:
        with Image.open(file_path) as img:
            if img.format != "PNG":
                return []

            meta = img.info or {}
            positive_prompts: List[str] = []
            processed_nodes = set()

            # Try workflow (ComfyUI)
            workflow = meta.get("workflow")
            if isinstance(workflow, str):
                wf = safe_json_load(workflow)
                if isinstance(wf, dict):
                    for p in extract_positive_from_workflow(wf, processed_nodes):
                        positive_prompts.append(p["text"])

            # Fallback prompt JSON
            if not positive_prompts:
                prompt_json = meta.get("prompt")
                if isinstance(prompt_json, str):
                    pd = safe_json_load(prompt_json)
                    if isinstance(pd, dict):
                        for p in extract_positive_from_prompt_data(pd, processed_nodes):
                            positive_prompts.append(p["text"])

            return positive_prompts
    except Exception:
        return []

def extract_positive_from_workflow(workflow_data: Dict, processed_nodes: set) -> List[Dict]:
    positive_prompts: List[Dict] = []
    nodes = workflow_data.get("nodes", [])
    for node in nodes:
        node_id = node.get("id")
        if node_id in processed_nodes:
            continue

        node_type = str(node.get("type", ""))
        title = str(node.get("title", "")).lower()
        props = node.get("properties", {}) or {}
        widgets_values = node.get("widgets_values", []) or []

        is_clip = (
            node_type == "CLIPTextEncode"
            or "cliptext" in node_type.lower()
            or props.get("Node name for S&R") == "CLIPTextEncode"
        )

        if is_clip and widgets_values:
            # widgets_values[0] may be str or dict; we only care about text
            raw = widgets_values[0]
            text = raw if isinstance(raw, str) else ""

            is_positive = (
                "positive" in title
                or "pos" in title
                or (title in ("", "untitled") and text.strip() != "" and not text.lower().startswith("negative"))
            )
            is_negative = (
                "negative" in title or "neg" in title or text.strip() == "" or text.lower().startswith("negative")
            )

            if is_positive and not is_negative and text.strip():
                positive_prompts.append(
                    {"text": text, "node_id": node_id, "node_type": node_type, "title": node.get("title", "Untitled")}
                )
                processed_nodes.add(node_id)
    return positive_prompts

def extract_positive_from_prompt_data(prompt_data: Dict, processed_nodes: set) -> List[Dict]:
    positive_prompts: List[Dict] = []
    for key, value in prompt_data.items():
        if not isinstance(value, dict):
            continue
        if key in processed_nodes:
            continue
        class_type = value.get("class_type", "")
        if class_type == "CLIPTextEncode":
            inputs = value.get("inputs", {}) or {}
            text_content = inputs.get("text") or inputs.get("prompt") or ""
            if text_content and text_content.strip():
                if not text_content.lower().strip().startswith("negative"):
                    positive_prompts.append(
                        {"text": text_content, "node_id": key, "class_type": class_type, "title": f"Node {key}"}
                    )
                    processed_nodes.add(key)
    return positive_prompts
