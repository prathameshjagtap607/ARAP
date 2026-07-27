import uuid
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def org_id():
    return uuid.uuid4()


@pytest.fixture
def session_id():
    return uuid.uuid4()


@pytest.fixture
def mock_db():
    return MagicMock()
