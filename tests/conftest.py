"""Prioritize this checkout over editable installs in the shared Python environment."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in [ROOT / 'backend', *sorted((ROOT / 'integrations/ru-marketplace-mcp/packages').glob('*/src'))]:
    sys.path.insert(0, str(path))
