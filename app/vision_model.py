import os
import requests
from openai import OpenAI
import json


def get_provider_config(config, selected_provider): 
    provider_config = config[selected_provider]
    api_base = provider_config["base_url"]
    api_key = os.getenv(provider_config["env_key"])
    if not api_key:
        raise ValueError(f"Missing API key for {selected_provider}. Set env variable: {provider_config['env_key']}")
    return api_base, api_key


def init_client(api_key, api_base):
    return OpenAI(api_key=api_key, base_url=api_base)


def fetch_models(base, key):
    headers = {"Authorization": f"Bearer {key}"}
    response = requests.get(f"{base}/models", headers=headers)
    response.raise_for_status()
    models = response.json().get("data", [])
    return [m["id"] for m in models]


def filter_vision_models(all_models):
    return [m for m in all_models if "vision" in m.lower() or "vl" in m.lower() or "llava" in m.lower()]
