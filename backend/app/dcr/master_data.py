"""Context used to enrich what an e-mail says.

- Parties: e-mail domain -> known partner (resources/master_data/parties.json).
- Projects: learned from the tracker itself — the latest row per project gives customer, supplier,
  office and pharma flag.
"""

import json
from functools import lru_cache

from pydantic import BaseModel

from app.dcr.schema import DCR
from app.resources import resource_path


class Party(BaseModel):
    name: str
    type: str
    domains: list[str]


class Project(BaseModel):
    project: str
    customer: str | None = None
    supplier: str | None = None
    office: str | None = None
    pharma: str | None = None


class MasterData(BaseModel):
    parties: list[Party]
    projects: dict[str, Project]

    def party_for_domain(self, domain: str | None) -> Party | None:
        if not domain:
            return None
        for party in self.parties:
            if any(domain == d or domain.endswith("." + d) for d in party.domains):
                return party
        return None

    def project(self, number: str | None) -> Project | None:
        if not number:
            return None
        return self.projects.get(number) or self.projects.get(number.split("-")[0])


@lru_cache
def load_parties() -> tuple[Party, ...]:
    path = resource_path("master_data", "parties.json")
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return tuple(Party(**p) for p in data.get("parties", []))


def build_master_data(records: list[DCR]) -> MasterData:
    def usable(v: str | None) -> str | None:
        return v if v and v != "N/A" else None

    projects: dict[str, Project] = {}
    for r in sorted((r for r in records if usable(r.project)), key=lambda r: r.occurred_on or ""):
        for key in {r.project, r.project.split("-")[0]}:
            prev = projects.get(key)
            projects[key] = Project(
                project=key,
                customer=usable(r.customer) or (prev.customer if prev else None),
                supplier=usable(r.supplier) or (prev.supplier if prev else None),
                office=r.amex_office or (prev.office if prev else None),
                pharma=r.pharma if r.pharma in ("Y", "N") else (prev.pharma if prev else None),
            )
    return MasterData(parties=list(load_parties()), projects=projects)
