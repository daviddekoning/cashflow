"""
Cashflow Web Editor — FastAPI server.

Manages cashflow JSON files in a directory and serves the editor UI.

Usage:
    uv run python -m cashflow.ui.server [--dir PATH] [--port PORT]
"""

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(data_dir: str | None = None) -> FastAPI:
    """Create the FastAPI application.

    Parameters
    ----------
    data_dir : str or None
        Directory containing cashflow JSON files.
        Defaults to the project root (two levels up from this file).
    """
    if data_dir is None:
        data_dir = str(Path(__file__).resolve().parents[2])

    data_path = Path(data_dir).resolve()
    if not data_path.is_dir():
        raise FileNotFoundError(f"Data directory does not exist: {data_path}")

    app = FastAPI(title="Cashflow Editor")
    app.state.data_dir = data_path

    # --- API routes --------------------------------------------------------

    @app.get("/api/files")
    async def list_files():
        """List all *.json files in the data directory."""
        files = []
        for p in sorted(data_path.glob("*.json")):
            stat = p.stat()
            files.append(
                {
                    "name": p.name,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat(),
                }
            )
        return files

    @app.post("/api/files", status_code=201)
    async def create_file(request: Request):
        """Create a new empty cashflow file."""
        body = await request.json()
        name = body.get("name", "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="File name is required.")
        if not name.endswith(".json"):
            name += ".json"

        # Prevent path traversal
        if "/" in name or "\\" in name or ".." in name:
            raise HTTPException(status_code=400, detail="Invalid file name.")

        filepath = data_path / name
        if filepath.exists():
            raise HTTPException(
                status_code=409, detail=f"File '{name}' already exists."
            )

        filepath.write_text(json.dumps([], indent=2) + "\n")
        return {"name": name, "message": f"Created {name}"}

    @app.get("/api/files/{name}")
    async def read_file(name: str):
        """Read the contents of a cashflow JSON file."""
        filepath = _safe_path(data_path, name)
        try:
            content = json.loads(filepath.read_text())
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=422, detail=f"Invalid JSON in {name}: {e}"
            )
        return content

    @app.put("/api/files/{name}")
    async def update_file(name: str, request: Request):
        """Overwrite a cashflow JSON file."""
        filepath = _safe_path(data_path, name)
        body = await request.json()
        filepath.write_text(json.dumps(body, indent=1) + "\n")
        return {"message": f"Saved {name}"}

    @app.delete("/api/files/{name}")
    async def delete_file(name: str):
        """Delete a cashflow JSON file."""
        filepath = _safe_path(data_path, name)
        filepath.unlink()
        return {"message": f"Deleted {name}"}

    @app.post("/api/files/{name}/duplicate", status_code=201)
    async def duplicate_file(name: str):
        """Duplicate a file, prepending today's date (replacing existing date prefix)."""
        import re

        filepath = _safe_path(data_path, name)
        content = filepath.read_text()

        stem = filepath.stem  # e.g. "2026-04-29-cashflows"
        ext = filepath.suffix  # e.g. ".json"

        # Strip existing yyyy-mm-dd prefix if present
        stripped = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", stem)

        today = datetime.now().strftime("%Y-%m-%d")
        new_name = f"{today}-{stripped}{ext}"
        new_path = data_path / new_name

        if new_path.exists():
            raise HTTPException(
                status_code=409, detail=f"File '{new_name}' already exists."
            )

        new_path.write_text(content)
        return {"name": new_name, "message": f"Duplicated to {new_name}"}

    # --- Static frontend ---------------------------------------------------

    _html_path = Path(__file__).resolve().parent / "pages" / "index.html"

    @app.get("/", response_class=HTMLResponse)
    async def index():
        """Serve the single-page editor UI."""
        return HTMLResponse(_html_path.read_text())

    return app


def _safe_path(data_dir: Path, name: str) -> Path:
    """Resolve a filename within data_dir, guarding against traversal."""
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(status_code=400, detail="Invalid file name.")
    if not name.endswith(".json"):
        raise HTTPException(status_code=400, detail="Only .json files are supported.")
    filepath = data_dir / name
    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"File '{name}' not found.")
    return filepath


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Cashflow Web Editor")
    parser.add_argument(
        "--dir",
        default=None,
        help="Directory containing cashflow JSON files (default: project root)",
    )
    parser.add_argument("--port", type=int, default=8000, help="Port to serve on")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    args = parser.parse_args()

    app = create_app(data_dir=args.dir)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
