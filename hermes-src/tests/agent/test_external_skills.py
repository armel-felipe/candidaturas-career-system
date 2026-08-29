"""Tests for external skill directories (skills.external_dirs config)."""

import json
import os
from unittest.mock import patch

import pytest


@pytest.fixture
def external_skills_dir(tmp_path):
    """Create a temp dir with a sample external skill."""
    ext_dir = tmp_path / "external-skills"
    skill_dir = ext_dir / "my-external-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: my-external-skill\ndescription: A skill from an external directory\n---\n\n# My External Skill\n\nDo external things.\n"
    )
    return ext_dir


@pytest.fixture
def hermes_home(tmp_path):
    """Create a minimal HERMES_HOME with config."""
    home = tmp_path / ".hermes"
    home.mkdir()
    (home / "skills").mkdir()
    return home


class TestGetExternalSkillsDirs:
    def test_empty_config(self, hermes_home):
        (hermes_home / "config.yaml").write_text("skills:\n  external_dirs: []\n")
        with patch.dict(os.environ, {"HERMES_HOME": str(hermes_home)}):
            from agent.skill_utils import get_external_skills_dirs
            result = get_external_skills_dirs()
        assert result == []

    def test_nonexistent_dir_skipped(self, hermes_home):
        (hermes_home / "config.yaml").write_text(
            "skills:\n  external_dirs:\n    - /nonexistent/path\n"
        )
        with patch.dict(os.environ, {"HERMES_HOME": str(hermes_home)}):
            from agent.skill_utils import get_external_skills_dirs
            result = get_external_skills_dirs()
        assert result == []

    def test_valid_dir_returned(self, hermes_home, external_skills_dir):
        (hermes_home / "config.yaml").write_text(
            f"skills:\n  external_dirs:\n    - {external_skills_dir}\n"
        )
        with patch.dict(os.environ, {"HERMES_HOME": str(hermes_home)}):
            from agent.skill_utils import get_external_skills_dirs
            result = get_external_skills_dirs()
        assert len(result) == 1
        assert result[0] == external_skills_dir.resolve()

    def test_duplicate_dirs_deduplicated(self, hermes_home, external_skills_dir):
        (hermes_home / "config.yaml").write_text(
            f"skills:\n  external_dirs:\n    - {external_skills_dir}\n    - {external_skills_dir}\n"
        )
        with patch.dict(os.environ, {"HERMES_HOME": str(hermes_home)}):
            from agent.skill_utils import get_external_skills_dirs
            result = get_external_skills_dirs()
        assert len(result) == 1

    def test_local_skills_dir_excluded(self, hermes_home):
        local_skills = hermes_home / "skills"
        (hermes_home / "config.yaml").write_text(
            f"skills:\n  external_dirs:\n    - {local_skills}\n"
        )
        with patch.dict(os.environ, {"HERMES_HOME": str(hermes_home)}):
            from agent.skill_utils import get_external_skills_dirs
            result = get_external_skills_dirs()
        assert result == []

    def test_no_config_file(self, hermes_home):
        # No config.yaml at all
        with patch.dict(os.environ, {"HERMES_HOME": str(hermes_home)}):
            from agent.skill_utils import get_external_skills_dirs
            result = get_external_skills_dirs()
        assert result == []

    def test_string_value_converted_to_list(self, hermes_home, external_skills_dir):
        (hermes_home / "config.yaml").write_text(
            f"skills:\n  external_dirs: {external_skills_dir}\n"
        )
        with patch.dict(os.environ, {"HERMES_HOME": str(hermes_home)}):
            from agent.skill_utils import get_external_skills_dirs
            result = get_external_skills_dirs()
        assert len(result) == 1


class TestGetAllSkillsDirs:
    def test_external_tier_precedes_profile_tier(self, hermes_home, external_skills_dir):
        (hermes_home / "config.yaml").write_text(
            f"skills:\n  external_dirs:\n    - {external_skills_dir}\n"
        )
        with patch.dict(os.environ, {"HERMES_HOME": str(hermes_home)}):
            from agent.skill_utils import get_all_skills_dirs
            result = get_all_skills_dirs()
        assert result[0] == external_skills_dir.resolve()
        assert result[1] == hermes_home / "skills"


def _make_named_skill(skills_dir, name, body="Body"):
    skill_dir = skills_dir / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Description for {name}.\n---\n\n{body}\n",
        encoding="utf-8",
    )
    return skill_dir


class TestProjectSkillPrecedence:
    def test_invalid_declared_precedence_is_rejected(self, hermes_home):
        (hermes_home / "config.yaml").write_text(
            "skills:\n  source_precedence: [profile, global, project]\n",
            encoding="utf-8",
        )

        with patch.dict(os.environ, {"HERMES_HOME": str(hermes_home)}):
            from agent.skill_utils import get_skill_search_dirs

            with pytest.raises(ValueError, match="source_precedence"):
                get_skill_search_dirs()

    def test_project_roots_precede_external_and_profile(self, hermes_home, tmp_path):
        project = tmp_path / "project"
        external = tmp_path / "external"
        project.mkdir()
        external.mkdir()
        local = hermes_home / "skills"
        _make_named_skill(project, "shared", body="PROJECT")
        _make_named_skill(external, "shared", body="GLOBAL")
        _make_named_skill(local, "shared", body="PROFILE")
        (hermes_home / "config.yaml").write_text(
            f"skills:\n  project_dirs:\n    - {project}\n"
            f"  external_dirs:\n    - {external}\n",
            encoding="utf-8",
        )

        with patch.dict(os.environ, {"HERMES_HOME": str(hermes_home)}):
            from agent.skill_utils import get_skill_search_dirs

            assert get_skill_search_dirs() == [
                project.resolve(),
                external.resolve(),
                local,
            ]

    def test_project_skill_resolution_wins_for_discovery(self, hermes_home, tmp_path):
        project = tmp_path / "project"
        external = tmp_path / "external"
        project.mkdir()
        external.mkdir()
        local = hermes_home / "skills"
        _make_named_skill(project, "shared", body="PROJECT")
        _make_named_skill(external, "shared", body="GLOBAL")
        _make_named_skill(local, "profile-only", body="PROFILE ONLY")
        (hermes_home / "config.yaml").write_text(
            f"skills:\n  project_dirs:\n    - {project}\n"
            f"  external_dirs:\n    - {external}\n",
            encoding="utf-8",
        )

        with (
            patch.dict(os.environ, {"HERMES_HOME": str(hermes_home)}),
            patch("tools.skills_tool.SKILLS_DIR", local),
        ):
            from tools.skills_tool import _find_all_skills

            skills = _find_all_skills()

        matching = [skill for skill in skills if skill["name"] == "shared"]
        assert len(matching) == 1
        assert matching[0]["description"] == "Description for shared."
        assert any(skill["name"] == "profile-only" for skill in skills)

    def test_project_shadowing_is_reported(self, hermes_home, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        local = hermes_home / "skills"
        _make_named_skill(project, "shared")
        _make_named_skill(local, "shared")
        (hermes_home / "config.yaml").write_text(
            f"skills:\n  project_dirs:\n    - {project}\n",
            encoding="utf-8",
        )

        with patch.dict(os.environ, {"HERMES_HOME": str(hermes_home)}):
            from agent.skill_utils import validate_project_skill_sources

            with pytest.raises(RuntimeError, match="shared"):
                validate_project_skill_sources()


class TestExternalSkillsInFindAll:
    def test_external_skills_found(self, hermes_home, external_skills_dir):
        (hermes_home / "config.yaml").write_text(
            f"skills:\n  external_dirs:\n    - {external_skills_dir}\n"
        )
        local_skills = hermes_home / "skills"
        with (
            patch.dict(os.environ, {"HERMES_HOME": str(hermes_home)}),
            patch("tools.skills_tool.SKILLS_DIR", local_skills),
        ):
            from tools.skills_tool import _find_all_skills
            skills = _find_all_skills()
        names = [s["name"] for s in skills]
        assert "my-external-skill" in names

    def test_external_takes_precedence_over_profile(self, hermes_home, external_skills_dir):
        """If the same skill name exists externally and locally, external wins."""
        local_skills = hermes_home / "skills"
        local_skill = local_skills / "my-external-skill"
        local_skill.mkdir(parents=True)
        (local_skill / "SKILL.md").write_text(
            "---\nname: my-external-skill\ndescription: Profile version\n---\n\nProfile.\n"
        )
        (hermes_home / "config.yaml").write_text(
            f"skills:\n  external_dirs:\n    - {external_skills_dir}\n"
        )
        with (
            patch.dict(os.environ, {"HERMES_HOME": str(hermes_home)}),
            patch("tools.skills_tool.SKILLS_DIR", local_skills),
        ):
            from tools.skills_tool import _find_all_skills
            skills = _find_all_skills()
        matching = [s for s in skills if s["name"] == "my-external-skill"]
        assert len(matching) == 1
        assert matching[0]["description"] == "A skill from an external directory"


class TestExternalSkillView:
    def test_skill_view_finds_external(self, hermes_home, external_skills_dir):
        (hermes_home / "config.yaml").write_text(
            f"skills:\n  external_dirs:\n    - {external_skills_dir}\n"
        )
        local_skills = hermes_home / "skills"
        with (
            patch.dict(os.environ, {"HERMES_HOME": str(hermes_home)}),
            patch("tools.skills_tool.SKILLS_DIR", local_skills),
        ):
            from tools.skills_tool import skill_view
            result = json.loads(skill_view("my-external-skill"))
        assert result["success"] is True
        assert "external things" in result["content"]
