import os
import sys
import tempfile
from pathlib import Path

# Configure an isolated, CPU-only environment before the app is imported.
_DATA = tempfile.mkdtemp(prefix="civic-records-test-")
os.environ["CIVIC_RECORDS_DATA_DIR"] = _DATA
os.environ["CIVIC_RECORDS_AI"] = "demo"
os.environ["CIVIC_RECORDS_DEMO"] = "1"
os.environ["CIVIC_RECORDS_FRONTEND_DIST"] = str(Path(_DATA) / "no-frontend")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
