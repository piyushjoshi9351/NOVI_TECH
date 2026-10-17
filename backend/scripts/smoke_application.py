"""Parent-first HTTP flow plus student reads and a disposable passport write."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.parent_first_smoke import main

if __name__ == "__main__":
    raise SystemExit(main("application"))
