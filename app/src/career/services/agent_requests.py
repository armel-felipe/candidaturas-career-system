from __future__ import annotations

from typing import Any

from career.services.agent_contracts import CONTRACTS
from career.services.database import Database


class AgentRequestBuilder:
    def __init__(self, database: Database):
        self._db = database

    def build(self, contract_name: str, application_id: str) -> dict[str, Any] | None:
        contract = CONTRACTS.get(contract_name)
        if contract is None:
            return None

        app = self._db.fetch_one(
            "SELECT company, role FROM applications WHERE id = ?",
            (application_id,),
        )

        return {
            "contract": contract,
            "contract_name": contract_name,
            "application_id": application_id,
            "company": app["company"] if app else None,
            "role": app["role"] if app else None,
            "inputs": list(contract["inputs"]),
            "outputs": list(contract["outputs"]),
            "rules": list(contract["rules"]),
        }
