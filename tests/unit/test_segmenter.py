"""
Unit tests for scene segmentation and semantic boundary detection.
"""
from worker.tasks.segment import MIN_SCENE_DURATION, segment_narration


def test_every_second_covered():
    """Verify that from 0.0 to total_duration is 100% covered without any gaps."""
    segments = [
        {"start": 0.0, "end": 2.5, "text": "First sentence here."},
        {"start": 2.5, "end": 5.8, "text": "Second sentence follows naturally."},
        {"start": 5.8, "end": 10.0, "text": "Third sentence concludes the thought."},
    ]
    total_duration = 10.0
    scenes = segment_narration(segments, total_duration)

    assert len(scenes) >= 1
    assert scenes[0].start_time == 0.0
    assert scenes[-1].end_time == total_duration

    # Verify continuity
    for i in range(len(scenes) - 1):
        assert scenes[i].end_time == scenes[i + 1].start_time


def test_min_scene_length_respected():
    """Verify that no flashing 0.5s clips exist (pacing >= MIN_SCENE_DURATION)."""
    # Many micro segments
    micro_segments = [
        {"start": i * 0.5, "end": (i + 1) * 0.5, "text": f"word{i}."}
        for i in range(20)
    ]
    scenes = segment_narration(micro_segments, 10.0)

    for s in scenes[:-1]:
        assert s.duration >= MIN_SCENE_DURATION


def test_predefined_scenes():
    predefined = [
        {"text": "Intro line", "visual_hint": "Modern office studio"},
        {"text": "Body explanation", "visual_hint": "Developer typing code"},
        {"text": "Outro CTA", "visual_hint": "Mobile app on smartphone"},
    ]
    scenes = segment_narration([], 15.0, predefined_scenes=predefined)

    assert len(scenes) == 3
    assert scenes[0].start_time == 0.0
    assert scenes[-1].end_time == 15.0
    assert scenes[1].visual_hint == "Developer typing code"


def test_semantic_disambiguation():
    """Words with double meanings: cloud computing, python, value, mouse."""
    segments = [
        {"start": 0.0, "end": 5.0, "text": "Our modern cloud computing architecture scales infinitely."},
        {"start": 5.0, "end": 10.0, "text": "Engineers deploy robust Python applications rapidly."},
    ]
    scenes = segment_narration(segments, 10.0)

    # Cloud computing should resolve to data center / server, not sky clouds
    assert "server" in scenes[0].search_query or "data center" in scenes[0].search_query
    # Python should resolve to developer / code, not reptile
    assert "code" in scenes[1].search_query or "developer" in scenes[1].search_query
