
import os
import sys
from pathlib import Path
import runpy

if __name__ == "__main__":
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        if idx + 1 < len(sys.argv):
            os.environ["KOM_PORT"] = sys.argv[idx + 1]
    here = Path(__file__).resolve().parent
    runpy.run_path(str(here / "backend" / "server.py"), run_name="__main__")
