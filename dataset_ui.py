import streamlit as st
import json
import os
import tempfile
from PIL import Image
from typing import Dict, Any, Optional, List
import uuid
import base64
from io import BytesIO
import pandas as pd
import time
from datetime import datetime

# Your existing extraction functions
def extract_positive_prompt(file_path: str) -> Optional[str]:
    """Extract the Positive Prompt from PNG metadata parameters key (original method)"""
    try:
        with Image.open(file_path) as img:
            if img.format != 'PNG':
                return None
            
            metadata = img.info
            
            if 'parameters' not in metadata:
                return None
            
            parameters_data = metadata['parameters']
            
            # Try to parse as JSON first
            try:
                parsed_params = json.loads(parameters_data)
                
                if isinstance(parsed_params, dict):
                    possible_keys = [
                        'Positive prompt', 'positive prompt', 'Positive Prompt',
                        'positive_prompt', 'prompt', 'Prompt'
                    ]
                    
                    for key in possible_keys:
                        if key in parsed_params:
                            return parsed_params[key]
                
            except json.JSONDecodeError:
                pass
            
            # Parse as text format
            lines = parameters_data.split('\n')
            
            for i, line in enumerate(lines):
                line = line.strip()
                
                if line.lower().startswith('positive prompt:'):
                    prompt_text = line.split(':', 1)[1].strip()
                    
                    j = i + 1
                    while j < len(lines):
                        next_line = lines[j].strip()
                        
                        if ':' in next_line or not next_line:
                            break
                        
                        prompt_text += ' ' + next_line
                        j += 1
                    
                    return prompt_text
            
            return None
            
    except Exception as e:
        return None

# ComfyUI extraction functions
def extract_positive_prompts_comfyui(file_path: str) -> List[str]:
    """Extract positive prompts from ComfyUI PNG metadata"""
    try:
        with Image.open(file_path) as img:
            if img.format != 'PNG':
                return []
            
            metadata = img.info
            positive_prompts = []
            processed_nodes = set()
            
            # Try workflow first
            if 'workflow' in metadata:
                try:
                    workflow_data = json.loads(metadata['workflow'])
                    prompts = extract_positive_from_workflow(workflow_data, processed_nodes)
                    positive_prompts.extend([p['text'] for p in prompts])
                except json.JSONDecodeError:
                    pass
            
            # Try prompt data if no workflow results
            if not positive_prompts and 'prompt' in metadata:
                try:
                    prompt_data = json.loads(metadata['prompt'])
                    prompts = extract_positive_from_prompt_data(prompt_data, processed_nodes)
                    positive_prompts.extend([p['text'] for p in prompts])
                except json.JSONDecodeError:
                    pass
            
            return positive_prompts
            
    except Exception as e:
        return []

def extract_positive_from_workflow(workflow_data: Dict, processed_nodes: set) -> List[Dict]:
    """Extract positive prompts from workflow nodes"""
    positive_prompts = []
    
    nodes = workflow_data.get('nodes', [])
    
    for node in nodes:
        node_id = node.get('id')
        node_type = node.get('type', '')
        title = node.get('title', '').lower()
        
        if node_id in processed_nodes:
            continue
        
        if (node_type == 'CLIPTextEncode' or 
            'cliptext' in node_type.lower() or 
            node.get('properties', {}).get('Node name for S&R') == 'CLIPTextEncode'):
            
            widgets_values = node.get('widgets_values', [])
            
            if widgets_values and len(widgets_values) > 0:
                prompt_text = widgets_values[0]
                
                is_positive = (
                    'positive' in title or 
                    'pos' in title or
                    (title == '' and prompt_text.strip() != '' and 'negative' not in prompt_text.lower()[:50]) or
                    (title == 'untitled' and prompt_text.strip() != '' and 'negative' not in prompt_text.lower()[:50])
                )
                
                is_negative = (
                    'negative' in title or 
                    'neg' in title or
                    prompt_text.strip() == '' or
                    prompt_text.lower().strip().startswith('negative')
                )
                
                if is_positive and not is_negative:
                    prompt_info = {
                        'text': prompt_text,
                        'node_id': node_id,
                        'node_type': node_type,
                        'title': node.get('title', 'Untitled'),
                        'source': 'workflow'
                    }
                    
                    positive_prompts.append(prompt_info)
                    processed_nodes.add(node_id)
    
    return positive_prompts

def extract_positive_from_prompt_data(prompt_data: Dict, processed_nodes: set) -> List[Dict]:
    """Extract positive prompts from prompt data structure"""
    positive_prompts = []
    
    for key, value in prompt_data.items():
        if isinstance(value, dict):
            class_type = value.get('class_type', '')
            
            if key in processed_nodes:
                continue
            
            if class_type == 'CLIPTextEncode':
                inputs = value.get('inputs', {})
                
                text_content = ""
                if 'text' in inputs:
                    text_content = inputs['text']
                elif 'prompt' in inputs:
                    text_content = inputs['prompt']
                
                if text_content and text_content.strip():
                    is_negative = (
                        text_content.strip() == '' or
                        'negative' in str(text_content).lower()[:50]
                    )
                    
                    if not is_negative:
                        prompt_info = {
                            'text': text_content,
                            'node_id': key,
                            'class_type': class_type,
                            'title': f"Node {key}",
                            'source': 'prompt_data'
                        }
                        
                        positive_prompts.append(prompt_info)
                        processed_nodes.add(key)
    
    return positive_prompts

def extract_all_prompts(file_path: str) -> str:
    """Extract prompts using all available methods - return clean prompt without source labels"""
    prompts = []
    
    # Method 1: Original parameters extraction
    original_prompt = extract_positive_prompt(file_path)
    if original_prompt:
        prompts.append(original_prompt.strip())
    
    # Method 2: ComfyUI extraction
    comfyui_prompts = extract_positive_prompts_comfyui(file_path)
    for prompt in comfyui_prompts:
        clean_prompt = prompt.strip()
        if clean_prompt and clean_prompt not in prompts:  # Avoid duplicates
            prompts.append(clean_prompt)
    
    if prompts:
        # Return the longest/most detailed prompt, or combine if they're different
        if len(prompts) == 1:
            return prompts[0]
        else:
            # If multiple prompts found, return the longest one (usually most detailed)
            return max(prompts, key=len)
    else:
        return "No prompt found - please add manually"

def image_to_base64(image_path: str) -> str:
    """Convert image to base64 string for storage"""
    try:
        with Image.open(image_path) as img:
            # Create thumbnail for display
            img.thumbnail((150, 150), Image.Resampling.LANCZOS)
            
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()
            return img_str
    except Exception as e:
        return ""

def check_file_access(file_path: str) -> Dict[str, Any]:
    """Check file accessibility and return detailed info"""
    info = {
        'exists': False,
        'readable': False,
        'size': 0,
        'error': None,
        'absolute_path': None
    }
    
    try:
        # Get absolute path
        abs_path = os.path.abspath(file_path)
        info['absolute_path'] = abs_path
        
        # Check if file exists
        info['exists'] = os.path.exists(file_path)
        
        if info['exists']:
            # Check if readable
            info['readable'] = os.access(file_path, os.R_OK)
            
            # Get file size
            info['size'] = os.path.getsize(file_path)
        
    except Exception as e:
        info['error'] = str(e)
    
    return info

def load_image_from_path(file_path: str) -> tuple[str, Dict[str, Any]]:
    """Load image from file path and convert to base64, return debug info"""
    debug_info = check_file_access(file_path)
    
    try:
        if debug_info['exists'] and debug_info['readable']:
            img_base64 = image_to_base64(file_path)
            return img_base64, debug_info
        else:
            return "", debug_info
    except Exception as e:
        debug_info['load_error'] = str(e)
        return "", debug_info
    

def rescan_dataset_directory():
    """Rescan dataset directory for new images and add them without duplicates"""
    if 'dataset_dir' not in st.session_state or not os.path.exists(st.session_state.dataset_dir):
        st.error("Dataset directory not configured or doesn't exist")
        return
    
    dataset_dir = st.session_state.dataset_dir
    
    # Get existing dataset filenames to avoid duplicates
    existing_dataset_files = set()
    existing_full_paths = set()
    
    for img in st.session_state.image_data:
        if img.get('dataset_filename'):
            existing_dataset_files.add(img['dataset_filename'])
        if img.get('full_path'):
            existing_full_paths.add(img['full_path'])
    
    # Scan directory for images
    new_images_count = 0
    
    try:
        for filename in os.listdir(dataset_dir):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                full_path = os.path.join(dataset_dir, filename)
                
                # Skip if already exists (check both dataset_filename and full_path)
                if filename in existing_dataset_files or full_path in existing_full_paths:
                    continue
                
                # Process new image
                try:
                    extracted_prompt = extract_all_prompts(full_path)
                    img_base64 = image_to_base64(full_path)
                    
                    if img_base64:
                        image_entry = {
                            'id': str(uuid.uuid4()),
                            'original_name': filename,  # Use filename as original name
                            'dataset_filename': filename,
                            'full_path': os.path.abspath(full_path),
                            'image_data': img_base64,
                            'prompt': extracted_prompt,
                            'modified': False,
                            'source': 'rescanned_dataset'
                        }
                        
                        st.session_state.image_data.append(image_entry)
                        new_images_count += 1
                        
                except Exception as e:
                    st.warning(f"Could not process {filename}: {e}")
    
    except Exception as e:
        st.error(f"Error scanning dataset directory: {e}")
        return
    
    return new_images_count


def base64_to_image(base64_str: str) -> Image.Image:
    """Convert base64 string back to PIL Image"""
    try:
        img_data = base64.b64decode(base64_str)
        img = Image.open(BytesIO(img_data))
        return img
    except Exception as e:
        return None

# Streamlit App Configuration
st.set_page_config(
    page_title="PNG Prompt Extractor & Editor",
    page_icon="🖼️",
    layout="wide"
)

# Initialize session state
def init_session_state():
    if 'image_data' not in st.session_state:
        st.session_state.image_data = []
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 0
    if 'images_per_page' not in st.session_state:
        st.session_state.images_per_page = 10
    if 'processed_files' not in st.session_state:
        st.session_state.processed_files = set()
    if 'debug_mode' not in st.session_state:
        st.session_state.debug_mode = False
    if 'image_directory_map' not in st.session_state:
        st.session_state.image_directory_map = {}
    if 'dataset_dir' not in st.session_state:  # Add this line
        st.session_state.dataset_dir = './dataset'


def process_uploaded_files(uploaded_files):
    """Process uploaded files and save to dataset directory"""
    if not uploaded_files:
        return
    
    if 'dataset_dir' not in st.session_state:
        st.error("Please configure dataset directory first!")
        return
    
    dataset_dir = st.session_state.dataset_dir
    
    # Create dataset directory if it doesn't exist
    try:
        os.makedirs(dataset_dir, exist_ok=True)
    except Exception as e:
        st.error(f"Cannot create dataset directory: {e}")
        return
    
    new_images_count = 0
    
    for uploaded_file in uploaded_files:
        file_id = f"{uploaded_file.name}_{uploaded_file.size}"
        
        if file_id in st.session_state.processed_files:
            continue
            
        if uploaded_file.type.startswith('image/'):
            try:
                # Generate unique filename to avoid conflicts
                timestamp = int(time.time() * 1000)
                name_part, ext = os.path.splitext(uploaded_file.name)
                unique_filename = f"{timestamp}_{name_part}{ext}"
                dataset_path = os.path.join(dataset_dir, unique_filename)
                
                # Save to dataset directory
                with open(dataset_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # Extract prompt from saved file
                extracted_prompt = extract_all_prompts(dataset_path)
                
                # Convert to base64 for display
                img_base64 = image_to_base64(dataset_path)
                
                if img_base64:
                    image_entry = {
                        'id': str(uuid.uuid4()),
                        'original_name': uploaded_file.name,
                        'dataset_filename': unique_filename,
                        'full_path': os.path.abspath(dataset_path),  # Real path in dataset
                        'image_data': img_base64,
                        'prompt': extracted_prompt,
                        'modified': False,
                        'source': 'uploaded_to_dataset'
                    }
                    
                    st.session_state.image_data.append(image_entry)
                    st.session_state.processed_files.add(file_id)
                    new_images_count += 1
                    
            except Exception as e:
                st.error(f"Error processing {uploaded_file.name}: {e}")
    
    if new_images_count > 0:
        st.success(f"Successfully saved {new_images_count} images to dataset!")
        st.rerun()


def load_jsonl_data(jsonl_content: str):
    """Load data from JSONL content and try to load images from full_path"""
    try:
        lines = jsonl_content.strip().split('\n')
        loaded_data = []
        
        for line in lines:
            if line.strip():
                data = json.loads(line)
                
                # Try to load image from full_path
                if 'full_path' in data:
                    img_base64, debug_info = load_image_from_path(data['full_path'])
                    data['image_data'] = img_base64
                    data['debug_info'] = debug_info  # Store debug info for troubleshooting
                    data['source'] = 'jsonl'  # Mark as loaded from JSONL
                else:
                    data['image_data'] = ""
                    data['debug_info'] = {'error': 'No full_path provided'}
                    data['source'] = 'jsonl'
                
                # Ensure we have full_path
                if 'full_path' not in data and 'original_name' in data:
                    data['full_path'] = data['original_name']
                
                loaded_data.append(data)
        
        return loaded_data
    except Exception as e:
        st.error(f"Error parsing JSONL: {e}")
        return []

def save_to_jsonl_content(data: List[Dict]) -> str:
    """Convert data to JSONL content string with dataset paths"""
    lines = []
    for item in data:
        jsonl_item = {
            'id': item.get('id'),
            'original_name': item.get('original_name'),
            'dataset_filename': item.get('dataset_filename'),  # Track dataset filename
            'full_path': item.get('full_path'),  # Real path in dataset
            'prompt': item.get('prompt'),
            'modified': item.get('modified', False),
            'source': item.get('source')
        }
        lines.append(json.dumps(jsonl_item, ensure_ascii=False))
    return '\n'.join(lines)


def get_paginated_data():
    """Get data for current page"""
    start_idx = st.session_state.current_page * st.session_state.images_per_page
    end_idx = start_idx + st.session_state.images_per_page
    return st.session_state.image_data[start_idx:end_idx]

def refresh_image_data():
    """Refresh image data by reloading from file paths"""
    refreshed_count = 0
    for i, img_data in enumerate(st.session_state.image_data):
        if 'full_path' in img_data and not img_data.get('image_data') and img_data.get('source') != 'uploaded':
            img_base64, debug_info = load_image_from_path(img_data['full_path'])
            if img_base64:
                st.session_state.image_data[i]['image_data'] = img_base64
                refreshed_count += 1
            st.session_state.image_data[i]['debug_info'] = debug_info
    
    return refreshed_count

def fix_image_paths():
    """Allow users to fix incorrect paths"""
    st.subheader("🔧 Fix Image Paths")
    
    # Find images that failed to load
    failed_images = [img for img in st.session_state.image_data 
                    if not img.get('image_data') and img.get('source') == 'jsonl']
    
    if not failed_images:
        st.success("All images loaded successfully!")
        return
    
    st.warning(f"Found {len(failed_images)} images that couldn't be loaded")
    
    # Path replacement tool
    st.markdown("**Bulk Path Replacement:**")
    col1, col2 = st.columns(2)
    
    with col1:
        old_path = st.text_input("Replace this path part:", value="/gorgon/ia/comfyprompt_dataset/")
    
    with col2:
        new_path = st.text_input("With this path part:", value="/gorgon/ia/ComfyUI/output/")
    
    if st.button("🔄 Apply Path Replacement"):
        fixed_count = 0
        for i, img_data in enumerate(st.session_state.image_data):
            if not img_data.get('image_data') and old_path in img_data.get('full_path', ''):
                # Replace the path
                new_full_path = img_data['full_path'].replace(old_path, new_path)
                
                # Try to load with new path
                img_base64, debug_info = load_image_from_path(new_full_path)
                if img_base64:
                    st.session_state.image_data[i]['image_data'] = img_base64
                    st.session_state.image_data[i]['full_path'] = new_full_path
                    st.session_state.image_data[i]['debug_info'] = debug_info
                    fixed_count += 1
        
        if fixed_count > 0:
            st.success(f"Fixed {fixed_count} image paths!")
            st.rerun()
        else:
            st.error("No images could be fixed with this path replacement")
    
    # Show some examples of failed paths
    if failed_images:
        with st.expander("Show failed image paths (first 5)"):
            for img in failed_images[:5]:
                st.text(f"File: {img['original_name']}")
                st.text(f"Path: {img['full_path']}")
                if 'debug_info' in img:
                    st.json(img['debug_info'])
                st.markdown("---")

def main():
    init_session_state()
    
    st.title("🖼️ PNG Prompt Extractor & Editor")
    st.markdown("Upload PNG images to extract and edit their embedded prompts")
    
    # Sidebar for controls
    with st.sidebar:
        st.header("📁 File Operations")
        
        # Debug mode toggle
        st.session_state.debug_mode = st.checkbox("🐛 Debug Mode", value=st.session_state.debug_mode)


        st.subheader("📁 Dataset Configuration")

        # Initialize dataset_dir in session state if not exists
        if 'dataset_dir' not in st.session_state:
            st.session_state.dataset_dir = './dataset'

        dataset_dir = st.text_input(
            "Dataset Directory:",
            value=st.session_state.dataset_dir,
            help="Directory where uploaded images will be saved",
            key="dataset_dir_input"
        )

        # Update session state when input changes
        if dataset_dir != st.session_state.dataset_dir:
            st.session_state.dataset_dir = dataset_dir

        if st.button("📂 Create/Verify Dataset Directory"):
            try:
                os.makedirs(st.session_state.dataset_dir, exist_ok=True)
                if os.path.exists(st.session_state.dataset_dir):
                    st.success(f"✅ Dataset directory ready: {st.session_state.dataset_dir}")
                else:
                    st.error(f"❌ Could not create directory: {st.session_state.dataset_dir}")
            except Exception as e:
                st.error(f"Error creating directory: {e}")


        if st.button("🔄 Rescan Dataset Directory"):
            if os.path.exists(st.session_state.dataset_dir):
                with st.spinner("Scanning dataset directory for new images..."):
                    new_count = rescan_dataset_directory()
                    
                if new_count > 0:
                    st.success(f"✅ Found and added {new_count} new images!")
                    st.rerun()
                else:
                    st.info("No new images found in dataset directory")
            else:
                st.error("Dataset directory does not exist")


        # Show dataset info
        if os.path.exists(st.session_state.dataset_dir):
            try:
                image_count = len([f for f in os.listdir(st.session_state.dataset_dir) 
                                if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
                st.info(f"📊 Dataset contains {image_count} images")
                st.success(f"✅ Using: {st.session_state.dataset_dir}")
            except:
                st.warning("Dataset directory not accessible")
        else:
            st.warning("Dataset directory does not exist")


        auto_rescan = st.checkbox(
            "🔄 Auto-rescan on page load",
            help="Automatically check for new images when the app loads"
        )

        if auto_rescan and 'last_rescan' not in st.session_state:
            st.session_state.last_rescan = True
            with st.spinner("Auto-scanning dataset directory..."):
                new_count = rescan_dataset_directory()
                if new_count > 0:
                    st.success(f"Auto-scan found {new_count} new images!")
                    st.rerun()


        # Show current working directory
        if st.session_state.debug_mode:
            st.subheader("🔍 Debug Info")
            st.text(f"Current working directory:\n{os.getcwd()}")
            
            # Test file access
            test_path = st.text_input("Test file path:", value="/gorgon/ia/ComfyUI/output/2025-08-31/2025-08-31-100203_-1.png")
            if st.button("Test Path Access"):
                debug_info = check_file_access(test_path)
                st.json(debug_info)
        
        # Load existing JSONL
        st.subheader("Load Existing Data")
        uploaded_jsonl = st.file_uploader("Upload JSONL file", type=['jsonl'], key="jsonl_upload")
        
        if uploaded_jsonl and st.button("Load JSONL Data"):
            jsonl_content = uploaded_jsonl.read().decode('utf-8')
            loaded_data = load_jsonl_data(jsonl_content)
            
            if loaded_data:
                existing_ids = {img['id'] for img in st.session_state.image_data}
                new_count = 0
                loaded_images_count = 0
                failed_images = []
                
                for item in loaded_data:
                    if item.get('id') not in existing_ids:
                        st.session_state.image_data.append(item)
                        new_count += 1
                        if item.get('image_data'):
                            loaded_images_count += 1
                        else:
                            failed_images.append(item.get('original_name', 'Unknown'))
                
                st.success(f"Loaded {new_count} new entries from JSONL")
                if loaded_images_count > 0:
                    st.info(f"Successfully loaded {loaded_images_count} images from file paths")
                
                if failed_images:
                    st.warning(f"Failed to load {len(failed_images)} images - use Path Fixer below")
                
                st.rerun()
        
        # Path fixer section
        if st.session_state.image_data:
            failed_count = sum(1 for img in st.session_state.image_data 
                             if not img.get('image_data') and img.get('source') == 'jsonl')
            if failed_count > 0:
                st.error(f"⚠️ {failed_count} images need path fixing")
        
        # Refresh images button
        if st.session_state.image_data:
            st.subheader("🔄 Refresh Images")
            if st.button("Reload Images from Paths"):
                with st.spinner("Reloading images..."):
                    refreshed_count = refresh_image_data()
                if refreshed_count > 0:
                    st.success(f"Refreshed {refreshed_count} images")
                    st.rerun()
                else:
                    st.info("No new images loaded")
        
        # Save current data
        st.subheader("Save Data")

        # Generate filename with date and time (always available)
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        jsonl_filename = f"image_prompts_{timestamp}.jsonl"

        if st.session_state.image_data:
            jsonl_content = save_to_jsonl_content(st.session_state.image_data)
            
            st.download_button(
                label="💾 Download JSONL",
                data=jsonl_content,
                file_name=jsonl_filename,
                mime="application/json"
            )
            
            # Show what the filename will be
            st.caption(f"📄 Will save as: {jsonl_filename}")
        else:
            st.info("No data to save")
            st.caption(f"📄 Would save as: {jsonl_filename}")


        
        # Pagination settings
        st.subheader("📄 Pagination")
        new_per_page = st.selectbox(
            "Images per page",
            [5, 10, 15, 20],
            index=1
        )
        
        if new_per_page != st.session_state.images_per_page:
            st.session_state.images_per_page = new_per_page
            st.session_state.current_page = 0
            st.rerun()
        
        # Statistics
        st.subheader("📊 Statistics")
        st.metric("Total Images", len(st.session_state.image_data))
        modified_count = sum(1 for img in st.session_state.image_data if img.get('modified', False))
        st.metric("Modified Prompts", modified_count)
        
        # Image loading statistics
        if st.session_state.image_data:
            loaded_images = sum(1 for img in st.session_state.image_data if img.get('image_data'))
            failed_images = sum(1 for img in st.session_state.image_data 
                              if not img.get('image_data') and img.get('source') == 'jsonl')
            st.metric("Images Loaded", f"{loaded_images}/{len(st.session_state.image_data)}")
            if failed_images > 0:
                st.metric("Failed to Load", failed_images)
        
        # Clear all button
        if st.session_state.image_data:
            st.subheader("🗑️ Actions")
            if st.button("Clear All Images", type="secondary"):
                st.session_state.image_data = []
                st.session_state.current_page = 0
                st.session_state.processed_files = set()
                st.rerun()
    
    # Main content area
    st.header("📤 Upload Images")
    
    # File uploader
    uploaded_files = st.file_uploader(
        "Choose PNG/JPG images",
        type=['png', 'jpg', 'jpeg'],
        accept_multiple_files=True,
        key="image_uploader"
    )
    
    # Process uploaded files
    if uploaded_files:
        with st.spinner("Processing uploaded images..."):
            process_uploaded_files(uploaded_files)
    
    # Path fixer tool (show if there are failed images)
    if st.session_state.image_data:
        failed_count = sum(1 for img in st.session_state.image_data 
                          if not img.get('image_data') and img.get('source') == 'jsonl')
        if failed_count > 0:
            fix_image_paths()
    
    # Display images in tabular format
    if st.session_state.image_data:
        st.header("🖼️ Images & Prompts Table")
        
        # Pagination controls
        total_pages = (len(st.session_state.image_data) - 1) // st.session_state.images_per_page + 1
        
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col1:
            if st.button("⬅️ Previous", disabled=st.session_state.current_page == 0):
                st.session_state.current_page -= 1
                st.rerun()
        
        with col2:
            st.write(f"Page {st.session_state.current_page + 1} of {total_pages}")
        
        with col3:
            if st.button("➡️ Next", disabled=st.session_state.current_page >= total_pages - 1):
                st.session_state.current_page += 1
                st.rerun()
        
        # Get current page data
        current_images = get_paginated_data()
        
        # Create tabular layout
        st.markdown("---")
        
        for i, img_data in enumerate(current_images):
            # Create columns for tabular layout
            col1, col2, col3 = st.columns([1, 3, 1])
            
            with col1:
                # Display thumbnail
                try:
                    if img_data.get('image_data'):
                        image = base64_to_image(img_data['image_data'])
                        if image:
                            st.image(image, width=150, caption=img_data['original_name'])
                        else:
                            st.error("Failed to decode image")
                    else:
                        # Try to load image from path if not already loaded
                        if 'full_path' in img_data and img_data.get('source') != 'uploaded':
                            img_base64, debug_info = load_image_from_path(img_data['full_path'])
                            if img_base64:
                                # Update the image data
                                for idx, img in enumerate(st.session_state.image_data):
                                    if img['id'] == img_data['id']:
                                        st.session_state.image_data[idx]['image_data'] = img_base64
                                        st.session_state.image_data[idx]['debug_info'] = debug_info
                                        break
                                
                                image = base64_to_image(img_base64)
                                if image:
                                    st.image(image, width=150, caption=img_data['original_name'])
                                else:
                                    st.error("Failed to decode image")
                            else:
                                st.error(f"📁 Path not found")
                                st.caption(f"Looking for: {img_data['full_path']}")
                                if st.session_state.debug_mode and 'debug_info' in img_data:
                                    with st.expander("Debug Info"):
                                        st.json(img_data['debug_info'])
                        else:
                            st.info("📁 No image path")
                except Exception as e:
                    st.error(f"Error loading image: {str(e)}")
            
            with col2:
                # Prompt editor
                st.markdown(f"**📝 {img_data['original_name']}**")
                if 'full_path' in img_data:
                    st.caption(f"Path: {img_data['full_path']}")
                
                prompt_key = f"prompt_{img_data['id']}"
                
                new_prompt = st.text_area(
                    "Edit prompt:",
                    value=img_data['prompt'],
                    height=100,
                    key=prompt_key,
                    label_visibility="collapsed"
                )
                
                # Update prompt if changed
                if new_prompt != img_data['prompt']:
                    for idx, img in enumerate(st.session_state.image_data):
                        if img['id'] == img_data['id']:
                            st.session_state.image_data[idx]['prompt'] = new_prompt
                            st.session_state.image_data[idx]['modified'] = True
                            break
            
            with col3:
                # Action buttons
                st.markdown("**Actions**")
                
                if st.button(f"💾 Save", key=f"save_{img_data['id']}", type="primary"):
                    st.success("✅ Updated!")
                
                # Reload image button for individual images
                if not img_data.get('image_data') and img_data.get('full_path') and img_data.get('source') != 'uploaded':
                    if st.button(f"🔄 Reload", key=f"reload_{img_data['id']}", type="secondary"):
                        img_base64, debug_info = load_image_from_path(img_data['full_path'])
                        if img_base64:
                            for idx, img in enumerate(st.session_state.image_data):
                                if img['id'] == img_data['id']:
                                    st.session_state.image_data[idx]['image_data'] = img_base64
                                    st.session_state.image_data[idx]['debug_info'] = debug_info
                                    break
                            st.rerun()
                        else:
                            st.error("Could not load image")
                            if st.session_state.debug_mode:
                                st.json(debug_info)
                

            if st.button(f"🗑️ Remove", key=f"remove_{img_data['id']}", type="secondary"):
                # Delete from dataset if it's a dataset image
                if (img_data.get('source') == 'uploaded_to_dataset' and 
                    'dataset_filename' in img_data and 
                    'dataset_dir' in st.session_state):
                    
                    dataset_path = os.path.join(st.session_state.dataset_dir, img_data['dataset_filename'])
                    try:
                        if os.path.exists(dataset_path):
                            os.remove(dataset_path)
                            st.success(f"🗑️ Deleted {img_data['dataset_filename']} from dataset")
                    except Exception as e:
                        st.error(f"Could not delete file: {e}")
                
                # Remove from session data
                st.session_state.image_data = [
                    img for img in st.session_state.image_data 
                    if img['id'] != img_data['id']
                ]
                
                if st.session_state.image_data:
                    max_page = (len(st.session_state.image_data) - 1) // st.session_state.images_per_page
                    if st.session_state.current_page > max_page:
                        st.session_state.current_page = max(0, max_page)
                else:
                    st.session_state.current_page = 0
                
                st.rerun()

                
                # Show modification status
                if img_data.get('modified', False):
                    st.markdown("🔄 *Modified*")
                
                # Show source type
                source = img_data.get('source', 'unknown')
                if source == 'uploaded':
                    st.markdown("📤 *Uploaded*")
                elif source == 'jsonl':
                    st.markdown("📄 *From JSONL*")
            
            # Add separator between rows
            st.markdown("---")
    
    else:
        st.info("👆 Upload some images to get started!")
        st.markdown("""
        ### How to use this app:
        1. **Upload Images**: Use the file uploader to select PNG/JPG images
        2. **Load JSONL**: Upload existing JSONL files to continue previous work
        3. **Fix Paths**: If images don't load from JSONL, use the Path Fixer tool
        4. **Edit Prompts**: Browse through your images and edit their prompts
        5. **Save Data**: Download your work as a JSONL file
        
        ### Path Issues:
        If you see "📁 Path not found" errors after loading a JSONL file:
        - The images were moved or the paths in the JSONL are incorrect
        - Use the **Path Fixer** tool that appears above the image table
        - Replace the old path part with the correct path part
        - Example: Replace `/gorgon/ia/comfyprompt_dataset/` with `/gorgon/ia/ComfyUI/output/`
        
        ### Features:
        - **Automatic prompt extraction** from PNG metadata (ComfyUI and standard formats)
        - **Bulk path replacement** for fixing incorrect file paths
        - **Debug mode** for troubleshooting file access issues
        - **Pagination** for handling large image collections
        - **JSONL export/import** for data persistence
        """)

if __name__ == "__main__":
    main()
