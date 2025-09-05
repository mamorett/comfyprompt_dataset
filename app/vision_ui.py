import streamlit as st
import base64
import json
from .vision_model import get_provider_config, init_client, fetch_models, filter_vision_models


def get_vision_provider_config(provider_name: str):
    """Gets the API base and key for a given provider."""
    with open("config.json") as f:
        config = json.load(f)["providers"]
    return get_provider_config(config, provider_name)

@st.cache_data
def get_vision_models(api_base: str, api_key: str):
    """Gets a list of available vision models."""
    all_models = fetch_models(api_base, api_key)
    return filter_vision_models(all_models)
