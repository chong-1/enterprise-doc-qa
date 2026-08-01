"""pytest 全局 fixtures。"""

import pytest


@pytest.fixture(scope="session")
def anyio_backend():
    """指定 anyio/pytest-asyncio 后端。"""
    return "asyncio"
