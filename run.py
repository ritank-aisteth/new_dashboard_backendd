"""Local development runner. Use an ASGI process manager in deployed environments."""

import uvicorn

def main() -> None:
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
