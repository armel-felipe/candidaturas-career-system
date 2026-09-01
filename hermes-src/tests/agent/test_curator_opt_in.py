"""Automatic skill review must be an explicit production opt-in."""

from agent.background_review import should_review_skills


def test_skill_review_is_not_started_by_default():
    assert should_review_skills(
        config={"curator": {}},
        valid_tools={"skill_manage"},
    ) is False


def test_skill_review_requires_both_explicit_flags():
    assert should_review_skills(
        config={"curator": {"enabled": True}},
        valid_tools={"skill_manage"},
    ) is False
    assert should_review_skills(
        config={"curator": {"review_skills": True}},
        valid_tools={"skill_manage"},
    ) is False


def test_skill_review_is_enabled_only_with_explicit_opt_in():
    assert should_review_skills(
        config={"curator": {"enabled": True, "review_skills": True}},
        valid_tools={"skill_manage"},
    ) is True

