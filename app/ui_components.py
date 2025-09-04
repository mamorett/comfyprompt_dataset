from typing import List, Tuple
from pathlib import Path
import streamlit as st
from PIL import Image
from .models import ImageEntry
from .io_utils import base64_to_image, load_image_from_path
from .extractors import cached_extract_prompts
from .utils import is_image_file, file_hash

def render_image_row(entry: ImageEntry, debug_mode: bool, dataset_dir: Path):
    col1, col2, col3 = st.columns([1, 3, 1])

    with col1:
        # Display or load thumbnail on demand
        if entry.image_data:
            image = base64_to_image(entry.image_data)
            if image:
                st.image(image, width=150, caption=entry.original_name)
            else:
                st.error("Failed to decode image")
        else:
            if entry.full_path:
                base64_img, dbg = load_image_from_path(Path(entry.full_path))
                if base64_img:
                    entry.image_data = base64_img
                    st.image(base64_to_image(base64_img), width=150, caption=entry.original_name)
                else:
                    st.error("📁 Path not found")
                    st.caption(f"Looking for: {entry.full_path}")
                    if debug_mode and dbg:
                        with st.expander("Debug Info"):
                            st.json(dbg)
            else:
                st.info("📁 No image path")

    with col2:
        st.markdown(f"**📝 {entry.original_name}**")
        if entry.full_path:
            st.caption(f"Path: {entry.full_path}")
        new_prompt = st.text_area(
            "Edit prompt:",
            value=entry.prompt or "",
            height=100,
            key=f"prompt_{entry.id}",
            label_visibility="collapsed",
        )
        if new_prompt != entry.prompt:
            entry.prompt = new_prompt
            entry.modified = True

    with col3:
        st.markdown("**Actions**")
        if st.button("💾 Save", key=f"save_{entry.id}", type="primary"):
            st.success("✅ Updated!")
        if not entry.image_data and entry.full_path:
            if st.button("🔄 Reload", key=f"reload_{entry.id}", type="secondary"):
                base64_img, dbg = load_image_from_path(Path(entry.full_path))
                if base64_img:
                    entry.image_data = base64_img
                    entry.debug_info = dbg
                    st.rerun()
                else:
                    st.error("Could not load image")
                    if debug_mode and dbg:
                        st.json(dbg)

def render_fix_paths(entries: List[ImageEntry]):
    st.subheader("🔧 Fix Image Paths")
    failed = [e for e in entries if not e.image_data and e.source == "jsonl"]
    if not failed:
        st.success("All images loaded successfully!")
        return

    st.warning(f"Found {len(failed)} images that couldn't be loaded")
    col1, col2 = st.columns(2)
    with col1:
        old = st.text_input("Replace this path part:", value="/old/base/")
    with col2:
        new = st.text_input("With this path part:", value="/new/base/")

    if st.button("🔄 Apply Path Replacement"):
        fixed_count = 0
        for e in entries:
            if not e.image_data and e.full_path and old in e.full_path:
                e.full_path = e.full_path.replace(old, new)
                base64_img, dbg = load_image_from_path(Path(e.full_path))
                if base64_img:
                    e.image_data = base64_img
                    e.debug_info = dbg
                    fixed_count += 1
        if fixed_count:
            st.success(f"Fixed {fixed_count} image paths!")
            st.rerun()
        else:
            st.error("No images could be fixed with this path replacement")

    with st.expander("Show failed image paths (first 5)"):
        for e in failed[:5]:
            st.text(f"File: {e.original_name}")
            st.text(f"Path: {e.full_path}")
            if e.debug_info:
                st.json(e.debug_info)

def iter_images(dirpath: Path):
    with os.scandir(dirpath) as it:
        for entry in it:
            if entry.is_file() and is_image_file(entry.name):
                yield entry
