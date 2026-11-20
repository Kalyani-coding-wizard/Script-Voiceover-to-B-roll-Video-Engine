import pytest

from batch.batch_runner import _percentile
from app.config import Settings
from footage_providers.fal_ai import FalAIFootageProvider
from worker.tasks.footage import FootageManager
from tts_providers.edge_tts import EdgeTTSProvider
from tts_providers.openai_tts import OpenAITTSProvider


@pytest.mark.asyncio
async def test_provider_availability_requires_configured_credentials():
    fal = FalAIFootageProvider(api_key="")
    assert await fal.is_available() is False

    fal_mock = FalAIFootageProvider(api_key="mock_test")
    assert await fal_mock.is_available() is False


def test_openai_tts_reports_name_and_requires_key():
    provider = OpenAITTSProvider(api_key="")
    assert provider.name == "openai"
    assert provider.api_key == ""


def test_indic_edge_tts_voice_resolution():
    provider = EdgeTTSProvider()
    assert provider._resolve_voice("te-IN-female") == "te-IN-ShrutiNeural"
    assert provider._resolve_voice("ml-IN-male") == "ml-IN-MidhunNeural"


def test_batch_percentile_benchmark_helper():
    assert _percentile([], 0.95) == 0.0
    assert _percentile([1.0, 2.0, 3.0, 4.0], 0.95) == 4.0


def test_fal_is_valid_footage_provider_setting(monkeypatch):
    monkeypatch.setenv("FOOTAGE_PROVIDER", "fal")
    settings = Settings(_env_file=None)
    assert settings.footage_provider == "fal"


def test_footage_manager_accepts_explicit_provider():
    assert FootageManager(mock_mode=False, footage_provider="fal").footage_provider == "fal"
