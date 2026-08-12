from __future__ import annotations

from career.services.agent_contracts import AgentContracts


def test_get_contract():
    contracts = AgentContracts()
    contract = contracts.get_contract("fit-map")
    assert contract is not None
    assert "fit_map.draft.json" in contract["outputs"]


def test_list_contracts():
    contracts = AgentContracts()
    all_contracts = contracts.list_contracts()
    assert len(all_contracts) == 8
    for name in ("fit-map", "cv", "cover-letter", "feras", "habilidades", "notion-update", "email-draft", "linkedin"):
        assert name in all_contracts


def test_get_nonexistent():
    contracts = AgentContracts()
    assert contracts.get_contract("nonexistent") is None
