import base64
import json
from typing import Tuple, Any, List, Dict
import streamlit as st
from openai import OpenAI
from .vision_model import get_provider_config, init_client, fetch_models, filter_vision_models

def get_vision_provider_config(provider_name: str) -> Tuple[str, str]:
    """Gets the API base and key for a given provider."""
    with open("config.json") as f:
        config = json.load(f)["providers"]
    return get_provider_config(config, provider_name)

def get_vision_models(api_base: str, api_key: str) -> List[str]:
    """Gets a list of available vision models."""
    all_models = fetch_models(api_base, api_key)
    return filter_vision_models(all_models)

def run_vision_inference(client: OpenAI, model: str, prompt: str, image_path: str) -> str:
    """Runs vision inference on a single image."""
    with open(image_path, "rb") as f:
        b64_image = base64.b64encode(f.read()).decode("utf-8")
    
    image_type = "image/png" if image_path.endswith(".png") else "image/jpeg"
    
    image_contents = [{
        "type": "image_url",
        "image_url": {
            "url": f"data:{image_type};base64,{b64_image}"
        }
    }]

    messages = [
        {
            "role": "user",
            "content": [{"type": "text", "text": prompt}] + image_contents
        }
    ]

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"Inference error: {e}")
        return ""
