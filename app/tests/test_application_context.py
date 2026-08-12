from __future__ import annotations

import pytest

from career.services import application_context
from career.services.database import Database


@pytest.fixture
def database(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    yield database
    database.close()


def test_profile_claim_is_exclusive_and_releasable(database):
    claim = application_context.claim_profile_application(
        database,
        profile_id="hermes-a",
        application_id="notion_515",
        source="notion",
    )

    assert claim["status"] == "active"
    assert claim["application_id"] == "notion_515"

    with pytest.raises(ValueError, match="profile_has_active_application"):
        application_context.claim_profile_application(
            database,
            profile_id="hermes-a",
            application_id="notion_516",
            source="notion",
        )

    release = application_context.release_profile_application(
        database,
        profile_id="hermes-a",
        application_id="notion_515",
    )

    assert release["status"] == "released"
    assert application_context.active_profile_application(database, "hermes-a") is None


def test_second_profile_cannot_claim_owned_application(database):
    application_context.claim_profile_application(
        database,
        profile_id="hermes-a",
        application_id="notion_515",
        source="notion",
    )

    with pytest.raises(ValueError, match="application_owned_by_another_profile"):
        application_context.claim_profile_application(
            database,
            profile_id="hermes-b",
            application_id="notion_515",
            source="notion",
        )


def test_profile_claim_is_idempotent_for_the_same_application(database):
    first = application_context.claim_profile_application(
        database,
        profile_id="hermes-a",
        application_id="notion_515",
        source="notion",
    )
    second = application_context.claim_profile_application(
        database,
        profile_id="hermes-a",
        application_id="notion_515",
        source="notion",
    )

    assert second == first
