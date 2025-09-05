import streamlit as st
import base64
import json
import os
from .vision_model import get_provider_config, init_client, fetch_models, filter_vision_models



def render_vision_ui():
    """Render the vision model UI as an embeddable section."""
    try:
        with open("config.json") as f:
            config = json.load(f)["providers"] 
        # Sidebar: select provider
        provider_names = list(config.keys())
        selected_provider = st.selectbox("Choose Provider", provider_names)            
    except Exception as e:
        st.error(f"Error loading config.json: {e}")
        # return

    # Provider config and client initialization
    try:
        api_base, api_key = get_provider_config(config, selected_provider)
        client = init_client(api_key, api_base)
    except ValueError as e:
        st.error(str(e))
        return

    # Fetch models (with Streamlit cache)
    @st.cache_data
    def get_models_cached(base, key):
        try:
            return fetch_models(base, key)
        except Exception as e:
            st.error(f"Error fetching models: {e}")
            return []

    all_models = get_models_cached(api_base, api_key)
    vision_models = filter_vision_models(all_models)
    selected_model = st.selectbox("Select Model", vision_models or all_models)

    # Prompt + image
    prompt = st.text_area("Enter your prompt", "Describe this image.")
    uploaded_images = st.file_uploader("Upload one or more images", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
    submit = st.button("Run Inference")

    image_contents = []
    for img in uploaded_images:
        b64_image = base64.b64encode(img.read()).decode("utf-8")
        image_type = img.type
        image_contents.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{image_type};base64,{b64_image}"
            }
        })

    messages = [
        {
            "role": "user",
            "content": [{"type": "text", "text": prompt}] + image_contents
        }
    ]

    if submit:
        if not uploaded_images:
            st.warning("Please upload at least one image before running inference.")
        else:
            with st.spinner("Generating response..."):
                try:
                    response = client.chat.completions.create(
                        model=selected_model,
                        messages=messages,
                        temperature=0.7
                    )
                    output = response.choices[0].message.content
                    if output:
                        st.success("Response:")
                        st.text_area(
                            label="Model Response",
                            value=output,
                            height=400,
                            max_chars=None,
                            key="response_area"
                        )
                except Exception as e:
                    st.error(f"Inference error: {e}")