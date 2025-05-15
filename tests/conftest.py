import pytest

# Use pytest-asyncio
pytest_plugins = ("pytest_asyncio",)

@pytest.fixture(scope="module", params=["asyncio", "trio"])
def anyio_backend():
    return ("asyncio", {"debug": True})
