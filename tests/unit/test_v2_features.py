from worker.tasks.langid import detect_language
from worker.tasks.safety import gate_query
from worker.tasks.segment import SegmentedScene
from worker.tasks.queries import build_search_query
from worker.tasks.input_validation import validate_audio_url
import pytest


def test_indic_language_detection_and_concrete_query():
    assert detect_language("తెలుగు వంటకం") == "te"
    scene = SegmentedScene(0, "The grind never stops", 0, 2)
    assert build_search_query(scene) == "person working late at desk"


def test_ip_query_is_routed_to_safe_fallback():
    decision = gate_query("movie scene recap", "movie scene")
    assert decision.allowed is False
    assert decision.requires_fallback is True


def test_audio_extension_gate():
    validate_audio_url("https://example.com/voice.m4a")
    with pytest.raises(ValueError, match="UNSUPPORTED_FORMAT"):
        validate_audio_url("https://example.com/voice.mp4")
