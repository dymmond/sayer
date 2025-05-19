import shutil
from pathlib import Path

import pytest

pytest_plugins = ("pytest_asyncio",)


@pytest.fixture(scope="module", params=["asyncio", "trio"])
def anyio_backend():
    return ("asyncio", {"debug": True})


@pytest.fixture(autouse=True)
def isolate_fs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    for name in ("docs", "commands", "out_docs", "custom_docs", "outdocs", "custom_docs"):
        p = Path(name)
        if p.exists():
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()

    yield

    for name in ("docs", "commands", "out_docs", "custom_docs", "outdocs", "custom_docs"):
        p = Path(name)
        if p.exists():
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
