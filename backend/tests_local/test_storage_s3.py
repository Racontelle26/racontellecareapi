"""Stockage S3 compatible (Scaleway, R2, Railway Buckets) simulé avec moto."""
import importlib

import pytest


@pytest.fixture
def s3_storage(monkeypatch):
    monkeypatch.setenv("S3_BUCKET", "racontelle-audio")
    monkeypatch.setenv("S3_REGION", "fr-par")
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "test")
    monkeypatch.delenv("S3_ENDPOINT", raising=False)
    boto3 = pytest.importorskip("boto3")
    mock_aws = pytest.importorskip("moto").mock_aws
    with mock_aws():
        boto3.client("s3", region_name="fr-par").create_bucket(
            Bucket="racontelle-audio", CreateBucketConfiguration={"LocationConstraint": "fr-par"}
        )
        import storage

        module = importlib.reload(storage)
        yield module
    monkeypatch.delenv("S3_BUCKET")
    importlib.reload(storage)


def test_s3_round_trip(s3_storage):
    assert s3_storage.storage_ready()
    assert s3_storage.init_storage() == "s3:racontelle-audio"
    s3_storage.put_object("racontelle-care/t1/c1.m4a", b"audio", "audio/m4a")
    assert s3_storage.get_object("racontelle-care/t1/c1.m4a") == (b"audio", "audio/m4a")
    assert s3_storage.delete_object("racontelle-care/t1/c1.m4a") is True
    with pytest.raises(Exception):
        s3_storage.get_object("racontelle-care/t1/c1.m4a")


def test_s3_without_keys_is_not_ready(monkeypatch):
    monkeypatch.setenv("S3_BUCKET", "racontelle-audio")
    monkeypatch.delenv("S3_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("S3_SECRET_ACCESS_KEY", raising=False)
    import storage

    module = importlib.reload(storage)
    try:
        assert not module.storage_ready()
        with pytest.raises(RuntimeError):
            module.init_storage()
    finally:
        monkeypatch.delenv("S3_BUCKET")
        importlib.reload(storage)
