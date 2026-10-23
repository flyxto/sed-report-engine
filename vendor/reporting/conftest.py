"""Make the repo root importable as the `reporting` package during tests.

The repo root *is* the package (it has __init__.py — see ARCHITECTURE.md), so
putting its parent directory on sys.path lets `import reporting` resolve
deterministically, without depending on a fragile editable install.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
