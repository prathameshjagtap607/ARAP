import pytest
from moto import mock_aws
from src import config as config_module
from src.s3 import download_file, ensure_bucket, upload_file


@pytest.fixture
def s3_env(monkeypatch):
    # Mock the settings object to return empty endpoint URL for moto compatibility
    monkeypatch.setattr(config_module.settings, "S3_ENDPOINT_URL", "")
    monkeypatch.setattr(config_module.settings, "S3_ACCESS_KEY", "test")
    monkeypatch.setattr(config_module.settings, "S3_SECRET_KEY", "test")
    monkeypatch.setattr(config_module.settings, "S3_BUCKET_RESUMES", "arap-resumes")


@mock_aws
def test_upload_and_download(s3_env):
    ensure_bucket()
    key = "resumes/test/abc.pdf"
    data = b"fake pdf content for testing upload and download roundtrip"
    returned_key = upload_file(data, key)
    assert returned_key == key
    downloaded = download_file(key)
    assert downloaded == data


@mock_aws
def test_ensure_bucket_idempotent(s3_env):
    ensure_bucket()
    ensure_bucket()  # should not raise


@mock_aws
def test_download_missing_key_raises(s3_env):
    ensure_bucket()
    import botocore.exceptions
    with pytest.raises(botocore.exceptions.ClientError):
        download_file("resumes/nonexistent.pdf")
