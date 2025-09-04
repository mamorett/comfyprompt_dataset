# run_app.py
import sys
from pathlib import Path

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# Import and run the Streamlit app entrypoint
from app.app import main  # relative imports inside app.app will work now
if __name__ == "__main__":
    main()
