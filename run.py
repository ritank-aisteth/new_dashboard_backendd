"""Local development runner. Use an ASGI process manager in deployed environments."""

import sys
from pathlib import Path

import uvicorn


PACKAGE_PARENT = Path(__file__).resolve().parent.parent
if str(PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT))


def main() -> None:
    uvicorn.run("backend_dashboard.main:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
