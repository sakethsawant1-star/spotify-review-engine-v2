import os
import sys
from pathlib import Path

# Add the parent directory (phase5-dashboard) to the Python path
sys.path.append(str(Path(__file__).parent.parent))

# Import the FastAPI app instance from app.py
from app import app
