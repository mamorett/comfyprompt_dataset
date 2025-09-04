# PNG Prompt Extractor & Editor (Streamlit)

A Streamlit app to:
- Scan a dataset of PNG/JPG images (now with subfolder support)
- Extract prompts from PNG metadata (ComfyUI + common formats)
- Edit prompts in a table view
- Export/import as JSONL with portable relative paths
- Bulk actions (select/delete/export and add prefix/suffix)

## Features

- Recursive rescan: include subfolders under your dataset directory
- Portable JSONL:
  - Manifest header: `{"__manifest__":{"base_dir":"./dataset"}}`
  - Each entry `rel_path` is `base_dir/dataset_filename` (e.g. `./dataset/sub/img.png`)
  - No absolute paths in JSONL
- Prompt extraction from:
  - PNG "parameters" text
  - ComfyUI "workflow" or "prompt" JSON (best-effort heuristics)
- Thumbnails and prompt extraction cached for speed
- Bulk actions:
  - Select on current page
  - Clear selection
  - Delete selected (session only)
  - Export selected as JSONL
  - Add prefix/suffix to selected prompts

## Installation

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run
From project root:

```bash
python -m streamlit run app/app.py
```
Ensure app/__init__.py exists (can be empty).

## Usage
- Set “Dataset Directory” in the sidebar (prefer a relative path like ./dataset)
- Click “Rescan Dataset Directory” (enable “Include subfolders” for recursive - scan)
- Edit prompts in the table
- Use bulk actions for selection, delete, export, prefix/suffix
- Save the entire session as JSONL via “Save Data”

## JSONL Format
First line is a manifest:

```json
{"__manifest__":{"base_dir":"./dataset"}}
```
Each subsequent line is an item:

```json
{
  "id": "...sha256...",
  "original_name": "image.png",
  "dataset_filename": "sub/image.png",
  "rel_path": "./dataset/sub/image.png",
  "prompt": "a sample prompt",
  "modified": false,
  "source": "rescanned_dataset"
}
```
To load on another machine:

- Place the dataset folder relative to the project root as in base_dir
- Load the JSONL (the app reconstructs absolute paths from rel_path

## Notes
- Deletion from dataset directory is only performed for items added via upload (to avoid accidental removal of external files). Adjust in app/app.py if needed.
- Caching: thumbnails and prompt extraction are cached by Streamlit (st.cache_data).

## Roadmap
- Graph-aware ComfyUI prompt extraction
- Sidecar save of edits alongside images
- CSV export
- Tests (pytest) and sample PNGs