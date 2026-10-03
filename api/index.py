import os
import sys
from pathlib import Path

BASE_DIR = str(Path(__file__).resolve().parent.parent)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import app

handler = app


