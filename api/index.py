import sys
from pathlib import Path

# Add backend/ to Python's import path
backend_path = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.main import app

__all__ = ["app"]