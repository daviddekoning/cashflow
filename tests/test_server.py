"""Tests for the cashflow web editor server."""

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cashflow.ui.server import create_app


@pytest.fixture()
def data_dir(tmp_path):
    """Create a temp directory with a sample cashflow file."""
    sample = [
        {
            "name": "Test Pay",
            "details": {
                "type": "interval",
                "first_date": "2022-01-01",
                "interval": 14,
                "amount": 1000,
            },
        },
        {
            "name": "Group",
            "details": {
                "type": "composite",
                "cashflows": [
                    {
                        "name": "Sub Item",
                        "details": {
                            "type": "monthly",
                            "day": 1,
                            "amount": -100,
                            "months": [1, 2, 3],
                        },
                    }
                ],
            },
        },
    ]
    (tmp_path / "test.json").write_text(json.dumps(sample, indent=2))
    return tmp_path


@pytest.fixture()
def client(data_dir):
    app = create_app(data_dir=str(data_dir))
    return TestClient(app)


# ── File listing ────────────────────────────────────────────────────────────

class TestListFiles:
    def test_lists_json_files(self, client, data_dir):
        resp = client.get("/api/files")
        assert resp.status_code == 200
        files = resp.json()
        assert len(files) == 1
        assert files[0]["name"] == "test.json"
        assert "size" in files[0]
        assert "modified" in files[0]

    def test_lists_multiple_files(self, client, data_dir):
        (data_dir / "second.json").write_text("[]")
        resp = client.get("/api/files")
        names = [f["name"] for f in resp.json()]
        assert "second.json" in names
        assert "test.json" in names

    def test_ignores_non_json(self, client, data_dir):
        (data_dir / "readme.txt").write_text("hello")
        resp = client.get("/api/files")
        names = [f["name"] for f in resp.json()]
        assert "readme.txt" not in names


# ── Create file ─────────────────────────────────────────────────────────────

class TestCreateFile:
    def test_create_new_file(self, client, data_dir):
        resp = client.post("/api/files", json={"name": "budget"})
        assert resp.status_code == 201
        assert (data_dir / "budget.json").exists()
        content = json.loads((data_dir / "budget.json").read_text())
        assert content == []

    def test_create_adds_json_extension(self, client, data_dir):
        resp = client.post("/api/files", json={"name": "savings"})
        assert resp.status_code == 201
        assert (data_dir / "savings.json").exists()

    def test_create_with_json_extension(self, client, data_dir):
        resp = client.post("/api/files", json={"name": "trip.json"})
        assert resp.status_code == 201
        assert (data_dir / "trip.json").exists()

    def test_create_duplicate_fails(self, client):
        resp = client.post("/api/files", json={"name": "test.json"})
        assert resp.status_code == 409

    def test_create_empty_name_fails(self, client):
        resp = client.post("/api/files", json={"name": ""})
        assert resp.status_code == 400

    def test_create_traversal_fails(self, client):
        resp = client.post("/api/files", json={"name": "../evil"})
        assert resp.status_code == 400


# ── Read file ───────────────────────────────────────────────────────────────

class TestReadFile:
    def test_read_existing_file(self, client):
        resp = client.get("/api/files/test.json")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["name"] == "Test Pay"

    def test_read_missing_file(self, client):
        resp = client.get("/api/files/nope.json")
        assert resp.status_code == 404

    def test_read_non_json_rejected(self, client):
        resp = client.get("/api/files/readme.txt")
        assert resp.status_code == 400


# ── Update file ─────────────────────────────────────────────────────────────

class TestUpdateFile:
    def test_update_file(self, client, data_dir):
        new_data = [{"name": "Updated", "details": {"type": "monthly", "day": 5, "amount": 500, "months": [1]}}]
        resp = client.put("/api/files/test.json", json=new_data)
        assert resp.status_code == 200
        # Verify on disk
        on_disk = json.loads((data_dir / "test.json").read_text())
        assert on_disk[0]["name"] == "Updated"

    def test_update_missing_file(self, client):
        resp = client.put("/api/files/nope.json", json=[])
        assert resp.status_code == 404

    def test_round_trip(self, client):
        """Read → modify → write → re-read round trip."""
        data = client.get("/api/files/test.json").json()
        data.append({"name": "New Item", "details": {"type": "one-time", "date": "2024-06-01", "amount": 42}})
        client.put("/api/files/test.json", json=data)
        reloaded = client.get("/api/files/test.json").json()
        assert len(reloaded) == 3
        assert reloaded[2]["name"] == "New Item"


# ── Delete file ─────────────────────────────────────────────────────────────

class TestDeleteFile:
    def test_delete_file(self, client, data_dir):
        resp = client.delete("/api/files/test.json")
        assert resp.status_code == 200
        assert not (data_dir / "test.json").exists()

    def test_delete_missing_file(self, client):
        resp = client.delete("/api/files/nope.json")
        assert resp.status_code == 404


# ── Duplicate file ──────────────────────────────────────────────────────────

class TestDuplicateFile:
    def test_duplicate_prepends_date(self, client, data_dir):
        resp = client.post("/api/files/test.json/duplicate")
        assert resp.status_code == 201
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        expected = f"{today}-test.json"
        assert resp.json()["name"] == expected
        assert (data_dir / expected).exists()
        # Contents should match
        original = json.loads((data_dir / "test.json").read_text())
        copy = json.loads((data_dir / expected).read_text())
        assert original == copy

    def test_duplicate_replaces_existing_date(self, client, data_dir):
        """If file already has a date prefix, replace it with today's date."""
        (data_dir / "2020-01-15-budget.json").write_text('[{"name":"old"}]')
        resp = client.post("/api/files/2020-01-15-budget.json/duplicate")
        assert resp.status_code == 201
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        assert resp.json()["name"] == f"{today}-budget.json"

    def test_duplicate_conflict(self, client, data_dir):
        """If the target file already exists, return 409."""
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        (data_dir / f"{today}-test.json").write_text("[]")
        resp = client.post("/api/files/test.json/duplicate")
        assert resp.status_code == 409

    def test_duplicate_missing_source(self, client):
        resp = client.post("/api/files/nope.json/duplicate")
        assert resp.status_code == 404


# ── Frontend ────────────────────────────────────────────────────────────────

class TestFrontend:
    def test_serves_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Cashflow Editor" in resp.text


# ── Edge cases and CLI ──────────────────────────────────────────────────────

class TestEdgeCases:
    def test_default_data_dir(self):
        """create_app with no args uses project root (which has cashflows.json)."""
        app = create_app()
        assert app.state.data_dir.is_dir()

    def test_missing_data_dir(self, tmp_path):
        """create_app raises for a non-existent directory."""
        with pytest.raises(FileNotFoundError):
            create_app(data_dir=str(tmp_path / "nope"))

    def test_read_invalid_json(self, client, data_dir):
        """Reading a file with invalid JSON returns 422."""
        (data_dir / "bad.json").write_text("{not valid json!!")
        resp = client.get("/api/files/bad.json")
        assert resp.status_code == 422

    def test_safe_path_traversal_read(self, client):
        """Path traversal via _safe_path in read endpoint."""
        resp = client.get("/api/files/..evil.json")
        assert resp.status_code == 400

    def test_safe_path_traversal_update(self, client):
        resp = client.put("/api/files/..evil.json", json=[])
        assert resp.status_code == 400

    def test_safe_path_traversal_delete(self, client):
        resp = client.delete("/api/files/..evil.json")
        assert resp.status_code == 400


class TestCLI:
    def test_main_function_exists(self):
        """main() is importable (CLI entry point)."""
        from cashflow.ui.server import main
        assert callable(main)
