import pytest
import uuid
from unittest.mock import MagicMock


@pytest.fixture
def org_id():
    return uuid.uuid4()


@pytest.fixture
def session_id():
    return uuid.uuid4()


@pytest.fixture
def mock_db():
    return MagicMock()
