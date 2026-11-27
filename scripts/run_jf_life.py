"""Run a sibling JF LIFE command with standard or embeddable Python."""

import runpy
import sys
from pathlib import Path


if __name__ == "__main__":
    script = Path(sys.argv.pop(1)).resolve()
    # The Windows embeddable distribution does not add the script directory.
    sys.path.insert(0, str(script.parent))
    runpy.run_path(str(script), run_name="__main__")
