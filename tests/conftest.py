import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def client(tmp_path, monkeypatch):
    import app as usagi
    monkeypatch.setattr(usagi, "DATABASE", str(tmp_path / "test.db"))
    usagi.init_db()
    usagi.app.config["TESTING"] = True
    with usagi.app.test_client() as c:
        yield c


def login(client, username="tanaka", password="password"):
    return client.post("/login", data={"username": username, "password": password})
