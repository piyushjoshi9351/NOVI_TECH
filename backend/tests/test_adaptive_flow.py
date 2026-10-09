"""Adaptive flow unit tests — pure logic, no database needed.

Covers the skip rules, next-step selection and question personalisation that
make onboarding questions rearrange and adapt based on earlier answers.
"""
from types import SimpleNamespace

from app.onboarding.steps import ONBOARDING_STEPS
from app.routers.onboarding import _next_step, _question_for, _reachable_steps, _skip_reason


def _step(step_id):
    return next(s for s in ONBOARDING_STEPS if s["id"] == step_id)


def _prof(**kwargs):
    base = dict(
        preferred_name="Aaru",
        enjoyed_subjects=None,
        has_career_in_mind=None,
        career_name=None,
        career_interest_reason=None,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_hard_subjects_skipped_only_after_enjoyed_answered():
    before = _prof()
    assert _skip_reason(before, _step("hard_subjects"), set()) is None
    assert _skip_reason(before, _step("hard_subjects"), {"enjoyed_subjects"}) == "no subjects enjoyed"
    with_enjoyed = _prof(enjoyed_subjects=["Science"])
    assert _skip_reason(with_enjoyed, _step("hard_subjects"), {"enjoyed_subjects"}) is None


def test_career_substeps_skipped_when_no_career_in_mind():
    no_career = _prof(has_career_in_mind=False)
    assert _skip_reason(no_career, _step("career_name"), {"career"}) == "no career in mind"
    has_career = _prof(has_career_in_mind=True)
    assert _skip_reason(has_career, _step("career_name"), {"career"}) is None


def test_next_after_career_depends_on_answer():
    no_career = _prof(has_career_in_mind=False)
    assert _next_step(no_career, _step("career"), {"career"}) == _step("primary_goal")
    has_career = _prof(has_career_in_mind=True)
    assert _next_step(has_career, _step("career"), {"career"}) == _step("career_name")


def test_next_skips_hard_subjects_when_nothing_enjoyed():
    prof = _prof(enjoyed_subjects=[])
    got = _next_step(prof, _step("enjoyed_subjects"), {"enjoyed_subjects"})
    assert got == _step("learning_style")


def test_next_returns_none_after_last_step():
    prof = _prof(has_career_in_mind=True, career_name="Software engineer")
    assert _next_step(prof, _step("primary_goal"), {"primary_goal"}) is None


def test_reachable_total_excludes_skipped():
    prof = _prof(enjoyed_subjects=[], has_career_in_mind=False)
    ids = {s["id"] for s in _reachable_steps(prof, {"enjoyed_subjects", "career"})}
    assert "hard_subjects" not in ids
    assert "career_name" not in ids and "career_reason" not in ids
    assert len(ids) == len(ONBOARDING_STEPS) - 3


def test_primary_goal_personalised_with_name():
    with_name = _question_for(_step("primary_goal"), _prof())
    assert "Aaru" in with_name and "one thing" in with_name
    anonymous = _question_for(_step("primary_goal"), _prof(preferred_name=""))
    assert anonymous == "If Novi could help you with one thing, what would you want it to be?"


def test_career_reason_references_named_career():
    prof = _prof(career_name="Astronaut")
    assert "Astronaut" in _question_for(_step("career_reason"), prof)
    assert _question_for(_step("career_reason"), _prof()) == "What makes you interested in it?"


def test_hard_subjects_references_enjoyed():
    prof = _prof(enjoyed_subjects=["Science", "Art"])
    q = _question_for(_step("hard_subjects"), prof)
    assert "Science" in q and "Art" in q


def test_university_personalised_with_name():
    assert "Aaru" in _question_for(_step("university"), _prof())
    assert "Aaru" not in _question_for(_step("university"), None)