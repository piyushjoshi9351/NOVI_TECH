"""Empathetic reply unit tests — pure logic, no database needed."""
from types import SimpleNamespace

from app.routers.onboarding import _empathy_reply, UNSURE_PATTERN


def _user(first_name="Aarav"):
    return SimpleNamespace(first_name=first_name)


def _profile(preferred_name="Aaru"):
    return SimpleNamespace(preferred_name=preferred_name)


def test_select_uncertainty_answers():
    for step, answer in [
        ("career", "No idea"),
        ("career", "Rather not say"),
        ("confidence", "Often doubt myself"),
        ("confidence", "Better when I prepare first"),
        ("confidence", "Hard to choose"),
    ]:
        out = _empathy_reply(step, answer, _user(), _profile())
        assert out and "Aaru" in out, (step, answer)


def test_multiselect_hard_subjects_threshold():
    assert _empathy_reply("hard_subjects", ["Maths", "Physics", "Chemistry"], _user(), _profile())
    assert not _empathy_reply("hard_subjects", ["Maths"], _user(), _profile())


def test_free_text_unsure_cues():
    for step, answer in [
        ("university", "I don't know"),
        ("career_name", "idk"),
        ("career_reason", "not sure really"),
        ("primary_goal", "i have no idea"),
    ]:
        assert _empathy_reply(step, answer, _user(), _profile()), (step, answer)


def test_unsure_pattern_matches():
    assert all(UNSURE_PATTERN.search(t) for t in ["idk", "I don't know", "no idea", "not sure", "dunno"])


def test_flat_negatives_trigger_empathy():
    for step, answer in [
        ("university", "no"),
        ("university", "nope"),
        ("university", "nah"),
        ("university", "not really"),
        ("university", "not at all"),
        ("university", "I don't have one"),
        ("university", "Not yet"),
    ]:
        assert _empathy_reply(step, answer, _user(), _profile()), (step, answer)
    assert not _empathy_reply("university", "I'm applying to Stanford", _user(), _profile())


def test_no_empathy_for_positive_answers():
    assert not _empathy_reply("career_name", "engineering", _user(), _profile())
    assert not _empathy_reply("career", "I have a few ideas", _user(), _profile())
    assert not _empathy_reply("saturday", "Gaming", _user(), _profile())


def test_name_fallback_to_account():
    assert "Aarav" in _empathy_reply("career", "No idea", _user(), None)


def test_no_name_drops_comma():
    out = _empathy_reply("primary_goal", "no idea", _user(first_name=""), None)
    assert out is not None
    assert ", —" not in out and ",you" not in out  # no dangling comma when name unknown