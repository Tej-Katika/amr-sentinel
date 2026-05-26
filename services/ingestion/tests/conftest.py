"""Add services/ingestion to sys.path so tests can import the package."""
import sys
from pathlib import Path

# Insert the parent of the package, so `import services.ingestion` works.
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
