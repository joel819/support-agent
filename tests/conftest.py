"""Tests run fully offline: temp data dir, hash embedder (no model download), no API key.
Env is set before the app is imported and overrides any local .env."""
import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="support-agent-tests-")
os.environ.update(
    DATA_DIR=_tmp,
    DATABASE_URL="",
    SEED_ON_STARTUP="false",
    GROQ_API_KEY="",
    EMBEDDING_BACKEND="hash",
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, SessionLocal, engine, init_db  # noqa: E402
from main import app  # noqa: E402
from scripts.seed import seed  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_state():
    init_db()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed(verbose=False)
    yield


@pytest.fixture
def db():
    with SessionLocal() as s:
        yield s


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
