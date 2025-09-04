import os
from pathlib import Path
import time
import uuid
import streamlit as st
from datetime import datetime

from .models import ImageEntry
from .io_utils import load_image_from_path, check_file_access, cached_thumbnail
from .persistence import save_to_jsonl_content, load_jsonl_data
from .extractors import cached_extract_prompts
from .ui_components import render_image_row, render_fix_paths
from .utils import is_image_file, file_hash

st.set_page_config(page_title="PNG Prompt Extractor & Editor", page_icon="🖼️", layout="wide")

def init_session_state():
    ss = st.session_state
    ss.setdefault("image_data", [])  # List[ImageEntry] stored as dicts
    ss.setdefault("current_page", 0)
    ss.setdefault("images_per_page", 10)
    ss.setdefault("processed_files", [])  # list instead of set for serialization stability
    ss.setdefault("debug_mode", False)
    ss.setdefault("dataset_dir", "./dataset")
    ss.setdefault("auto_rescan_done", False)

def get_paginated_data() -> list[ImageEntry]:
    start_idx = st.session_state.current_page * st.session_state.images_per_page
    end_idx = start_idx + st.session_state.images_per_page
    return st.session_state.image_data[start_idx:end_idx]

def rescan_dataset_directory() -> int:
    if "dataset_dir" not in st.session_state or not Path(st.session_state.dataset_dir).exists():
        st.error("Dataset directory not configured or doesn't exist")
        return 0

    dataset_dir = Path(st.session_state.dataset_dir)
    existing_names = {e["dataset_filename"] for e in st.session_state.image_data if e.get("dataset_filename")}
    existing_paths = {e["full_path"] for e in st.session_state.image_data if e.get("full_path")}

    entries = []
    try:
        with os.scandir(dataset_dir) as it:
            for entry in it:
                if not entry.is_file():
                    continue
                if not is_image_file(entry.name):
                    continue
                entries.append(entry)
    except Exception as e:
        st.error(f"Error scanning dataset directory: {e}")
        return 0

    new_images = 0
    progress = st.progress(0.0)
    total = len(entries) or 1

    for idx, ent in enumerate(entries):
        name = ent.name
        full_path = str(Path(ent.path).resolve())
        if name in existing_names or full_path in existing_paths:
            progress.progress((idx + 1) / total)
            continue

        # Extract prompt (cached)
        prompt = cached_extract_prompts(full_path) or ""
        thumb_b64 = cached_thumbnail(full_path)

        img_entry = ImageEntry(
            id=file_hash(Path(full_path)),
            original_name=name,
            dataset_filename=name,
            full_path=full_path,
            image_data=thumb_b64,
            prompt=prompt,
            modified=False,
            source="rescanned_dataset",
            debug_info=None,
        )
        st.session_state.image_data.append(img_entry.__dict__)
        new_images += 1
        progress.progress((idx + 1) / total)

    return new_images

def process_uploaded_files(uploaded_files):
    if not uploaded_files:
        return

    dataset_dir = Path(st.session_state.dataset_dir)
    try:
        dataset_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        st.error(f"Cannot create dataset directory: {e}")
        return

    new_images = 0
    for up in uploaded_files:
        file_id = f"{up.name}_{up.size}"
        if file_id in st.session_state.processed_files:
            continue
        if not up.type.startswith("image/"):
            continue

        try:
            ts = int(time.time() * 1000)
            name_part, ext = os.path.splitext(up.name)
            unique_filename = f"{ts}_{name_part}{ext}"
            dataset_path = dataset_dir / unique_filename

            with dataset_path.open("wb") as f:
                f.write(up.getbuffer())

            prompt = cached_extract_prompts(str(dataset_path)) or ""
            thumb_b64 = cached_thumbnail(str(dataset_path))

            entry = ImageEntry(
                id=file_hash(dataset_path),
                original_name=up.name,
                dataset_filename=unique_filename,
                full_path=str(dataset_path.resolve()),
                image_data=thumb_b64,
                prompt=prompt,
                modified=False,
                source="uploaded_to_dataset",
                debug_info=None,
            )
            st.session_state.image_data.append(entry.__dict__)
            st.session_state.processed_files.append(file_id)
            new_images += 1
        except Exception as e:
            st.error(f"Error processing {up.name}: {e}")

    if new_images:
        st.success(f"Successfully saved {new_images} images to dataset!")
        st.rerun()

def refresh_image_data() -> int:
    refreshed = 0
    for i, d in enumerate(st.session_state.image_data):
        entry = ImageEntry(**d)
        if entry.full_path and not entry.image_data and entry.source != "uploaded":
            b64, dbg = load_image_from_path(Path(entry.full_path))
            if b64:
                entry.image_data = b64
                entry.debug_info = dbg
                st.session_state.image_data[i] = entry.__dict__
                refreshed += 1
    return refreshed

def main():
    init_session_state()
    st.title("🖼️ PNG Prompt Extractor & Editor")
    st.markdown("Upload PNG/JPG images to extract and edit their embedded prompts")

    with st.sidebar:
        st.header("📁 File Operations")

        st.session_state.debug_mode = st.checkbox("🐛 Debug Mode", value=st.session_state.debug_mode)

        st.subheader("📁 Dataset Configuration")
        dataset_dir_input = st.text_input(
            "Dataset Directory:", value=st.session_state.dataset_dir, help="Directory where uploaded images will be saved"
        )
        if dataset_dir_input != st.session_state.dataset_dir:
            st.session_state.dataset_dir = dataset_dir_input

        if st.button("📂 Create/Verify Dataset Directory"):
            try:
                Path(st.session_state.dataset_dir).mkdir(parents=True, exist_ok=True)
                if Path(st.session_state.dataset_dir).exists():
                    st.success(f"✅ Dataset directory ready: {st.session_state.dataset_dir}")
                else:
                    st.error(f"❌ Could not create directory: {st.session_state.dataset_dir}")
            except Exception as e:
                st.error(f"Error creating directory: {e}")

        if st.button("🔄 Rescan Dataset Directory"):
            if Path(st.session_state.dataset_dir).exists():
                with st.spinner("Scanning dataset directory for new images..."):
                    new_count = rescan_dataset_directory()
                if new_count > 0:
                    st.success(f"✅ Found and added {new_count} new images!")
                    st.rerun()
                else:
                    st.info("No new images found in dataset directory")
            else:
                st.error("Dataset directory does not exist")

        # Dataset info
        ds_path = Path(st.session_state.dataset_dir)
        if ds_path.exists():
            try:
                image_count = sum(1 for f in ds_path.iterdir() if f.is_file() and is_image_file(f.name))
                st.info(f"📊 Dataset contains {image_count} images")
                st.success(f"✅ Using: {st.session_state.dataset_dir}")
            except Exception:
                st.warning("Dataset directory not accessible")
        else:
            st.warning("Dataset directory does not exist")

        auto_rescan = st.checkbox("🔄 Auto-rescan on page load", value=False)
        if auto_rescan and not st.session_state.auto_rescan_done:
            st.session_state.auto_rescan_done = True
            with st.spinner("Auto-scanning dataset directory..."):
                new_count = rescan_dataset_directory()
                if new_count > 0:
                    st.success(f"Auto-scan found {new_count} new images!")
                    st.rerun()

        if st.session_state.debug_mode:
            st.subheader("🔍 Debug Info")
            st.text(f"Current working directory:\n{os.getcwd()}")
            test_path = st.text_input("Test file path:", value=str(ds_path / "test.png"))
            if st.button("Test Path Access"):
                st.json(check_file_access(Path(test_path)))

        # Load JSONL
        st.subheader("Load Existing Data")
        uploaded_jsonl = st.file_uploader("Upload JSONL file", type=["jsonl"], key="jsonl_upload")
        if uploaded_jsonl and st.button("Load JSONL Data"):
            jsonl_content = uploaded_jsonl.read().decode("utf-8")
            loaded_data, base_dir = load_jsonl_data(jsonl_content)
            if loaded_data:
                existing_ids = {d["id"] for d in st.session_state.image_data}
                new_count, loaded_images_count, failed = 0, 0, []
                for item in loaded_data:
                    if item.id not in existing_ids:
                        # Try to load image immediately for preview
                        b64, dbg = ("", None)
                        if item.full_path:
                            b64, dbg = load_image_from_path(Path(item.full_path))
                        item.image_data = b64
                        item.debug_info = dbg
                        st.session_state.image_data.append(item.__dict__)
                        new_count += 1
                        if b64:
                            loaded_images_count += 1
                        else:
                            failed.append(item.original_name or "Unknown")
                st.success(f"Loaded {new_count} new entries from JSONL")
                if loaded_images_count:
                    st.info(f"Successfully loaded {loaded_images_count} images from file paths")
                if failed:
                    st.warning(f"Failed to load {len(failed)} images - use Path Fixer below")
                st.rerun()

        # Refresh images
        if st.session_state.image_data:
            st.subheader("🔄 Refresh Images")
            if st.button("Reload Images from Paths"):
                with st.spinner("Reloading images..."):
                    refreshed_count = refresh_image_data()
                if refreshed_count:
                    st.success(f"Refreshed {refreshed_count} images")
                    st.rerun()
                else:
                    st.info("No new images loaded")

        # Save current data
        st.subheader("Save Data")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        jsonl_filename = f"image_prompts_{timestamp}.jsonl"
        if st.session_state.image_data:
            # Convert dicts back to ImageEntry to ensure schema
            entries = [ImageEntry(**d) for d in st.session_state.image_data]
            jsonl_content = save_to_jsonl_content(entries, Path(st.session_state.dataset_dir))
            st.download_button(
                label="💾 Download JSONL",
                data=jsonl_content,
                file_name=jsonl_filename,
                mime="application/json",
            )
            st.caption(f"📄 Will save as: {jsonl_filename}")
        else:
            st.info("No data to save")
            st.caption(f"📄 Would save as: {jsonl_filename}")

        # Pagination settings
        st.subheader("📄 Pagination")
        new_per_page = st.selectbox("Images per page", [5, 10, 15, 20], index=1)
        if new_per_page != st.session_state.images_per_page:
            st.session_state.images_per_page = new_per_page
            st.session_state.current_page = 0
            st.rerun()

        # Statistics
        st.subheader("📊 Statistics")
        st.metric("Total Images", len(st.session_state.image_data))
        modified_count = sum(1 for d in st.session_state.image_data if d.get("modified", False))
        st.metric("Modified Prompts", modified_count)
        if st.session_state.image_data:
            loaded_images = sum(1 for d in st.session_state.image_data if d.get("image_data"))
            failed_images = sum(1 for d in st.session_state.image_data if not d.get("image_data") and d.get("source") == "jsonl")
            st.metric("Images Loaded", f"{loaded_images}/{len(st.session_state.image_data)}")
            if failed_images > 0:
                st.metric("Failed to Load", failed_images)

        # Clear all
        if st.session_state.image_data:
            st.subheader("🗑️ Actions")
            if st.button("Clear All Images", type="secondary"):
                st.session_state.image_data = []
                st.session_state.current_page = 0
                st.session_state.processed_files = []
                st.rerun()

    # Main content area
    st.header("📤 Upload Images")
    uploaded_files = st.file_uploader("Choose PNG/JPG images", type=["png", "jpg", "jpeg"], accept_multiple_files=True, key="image_uploader")
    if uploaded_files:
        with st.spinner("Processing uploaded images..."):
            process_uploaded_files(uploaded_files)

    # Path fixer tool if needed
    if st.session_state.image_data:
        failed_count = sum(1 for d in st.session_state.image_data if not d.get("image_data") and d.get("source") == "jsonl")
        if failed_count > 0:
            render_fix_paths([ImageEntry(**d) for d in st.session_state.image_data])

    # Table of images
    if st.session_state.image_data:
        st.header("🖼️ Images & Prompts Table")

        total_pages = (len(st.session_state.image_data) - 1) // st.session_state.images_per_page + 1
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            if st.button("⬅️ Previous", disabled=st.session_state.current_page == 0):
                st.session_state.current_page -= 1
                st.rerun()
        with c2:
            st.write(f"Page {st.session_state.current_page + 1} of {total_pages}")
        with c3:
            if st.button("➡️ Next", disabled=st.session_state.current_page >= total_pages - 1):
                st.session_state.current_page += 1
                st.rerun()

        st.markdown("---")
        current = get_paginated_data()
        for d in current:
            entry = ImageEntry(**d)
            render_image_row(entry, st.session_state.debug_mode, Path(st.session_state.dataset_dir))
            # persist any edits back into session state
            for i, sd in enumerate(st.session_state.image_data):
                if sd["id"] == entry.id:
                    st.session_state.image_data[i] = entry.__dict__
                    break
            if st.button(f"🗑️ Remove", key=f"remove_{entry.id}", type="secondary"):
                # optional: remove physical file only if inside dataset_dir and source == uploaded_to_dataset
                try:
                    if entry.source == "uploaded_to_dataset":
                        file_path = Path(entry.full_path)
                        ds = Path(st.session_state.dataset_dir).resolve()
                        if file_path.exists() and ds in file_path.resolve().parents:
                            # safer delete: comment out if you want hard delete
                            # from send2trash import send2trash
                            # send2trash(str(file_path))
                            os.remove(str(file_path))
                            st.success(f"🗑️ Deleted {file_path.name} from dataset")
                except Exception as e:
                    st.error(f"Could not delete file: {e}")

                st.session_state.image_data = [sd for sd in st.session_state.image_data if sd["id"] != entry.id]
                if st.session_state.image_data:
                    max_page = (len(st.session_state.image_data) - 1) // st.session_state.images_per_page
                    st.session_state.current_page = min(st.session_state.current_page, max_page)
                else:
                    st.session_state.current_page = 0
                st.rerun()

            if entry.modified:
                st.markdown("🔄 Modified")
            if entry.source == "uploaded_to_dataset":
                st.markdown("📤 Uploaded")
            elif entry.source == "jsonl":
                st.markdown("📄 From JSONL")
            st.markdown("---")
    else:
        st.info("👆 Upload some images to get started!")
        st.markdown("""
        - Upload images to extract prompts
        - Load a JSONL to continue previous work
        - Use Path Fixer if paths changed
        - Edit prompts and export JSONL
        """)

if __name__ == "__main__":
    main()
