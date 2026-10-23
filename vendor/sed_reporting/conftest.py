"""Make the repo root importable as the `sed_reporting` package during tests.

The repo root *is* the package, so its parent directory goes on sys.path. That
parent also holds the sibling `reporting` checkout (~/dev locally), which is how
this repo finds `reporting` — the same arrangement as /opt in the Docker image.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
