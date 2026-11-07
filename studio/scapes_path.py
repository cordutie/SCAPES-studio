"""Makes `import SCAPES` work. The SCAPES code is looked for in this order: the SCAPES_PATH variable, the folder SCAPES/
next to this repository (the local layout), a SCAPES that is already installed. Import this module before SCAPES."""
import os
import sys
from pathlib import Path

from studio.config import ROOT


def find_scapes():
    for candidate in (os.environ.get("SCAPES_PATH"), ROOT.parent / "SCAPES"):
        if candidate and (Path(candidate) / "SCAPES" / "pipeline.py").exists():
            return Path(candidate)
    return None


_found = find_scapes()
if _found is not None and str(_found) not in sys.path:
    sys.path.insert(0, str(_found))
