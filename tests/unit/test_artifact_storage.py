from pathlib import Path
import shutil

from app.config import Settings
from app.storage import ArtifactStorage


def test_local_artifact_storage_round_trip():
    root = Path(".test-artifacts")
    shutil.rmtree(root, ignore_errors=True)
    source = root / "source.mp4"
    root.mkdir(parents=True)
    source.write_bytes(b"video")

    storage = ArtifactStorage(Settings(mock_mode=True, artifact_backend="local"))
    storage.local_root = root

    key = storage.upload_file("job-local", source)
    assert key == "job-local/source.mp4"
    assert storage.exists("job-local", "source.mp4")

    destination = root / "downloaded.mp4"
    storage.download_file("job-local", "source.mp4", destination)
    assert destination.read_bytes() == b"video"
    shutil.rmtree(root, ignore_errors=True)


class FailingS3Client:
    def head_bucket(self, Bucket):
        return {}

    def upload_file(self, filename, bucket, key):
        raise ConnectionError("MinIO unavailable")


def test_s3_failure_falls_back_to_local():
    root = Path(".test-artifacts")
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    source = root / "manifest.json"
    source.write_text('{"ok": true}')

    storage = ArtifactStorage(Settings(mock_mode=False, artifact_backend="s3"))
    storage.local_root = root
    storage._client = FailingS3Client()

    key = storage.upload_file("job-fallback", source)
    assert key == "job-fallback/manifest.json"
    assert storage.backend == "local"
    assert (root / "job-fallback" / "manifest.json").exists()
    shutil.rmtree(root, ignore_errors=True)
