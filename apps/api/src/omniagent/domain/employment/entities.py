"""Entites metier du domaine Emploi.

Ces entites sont des dataclasses pures, sans dependance vers les agents,
L''API, ou la DB. Elles representent le vocabulaire metier.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from uuid import uuid4


class ContractType(str, Enum):
    STAGE = "stage"
    ALTERNANCE = "alternance"
    CDD = "cdd"
    CDI = "cdi"
    FREELANCE = "freelance"


class ApplicationStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    VIEWED = "viewed"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


@dataclass
class Candidate:
    candidate_id: str = field(default_factory=lambda: str(uuid4()))
    full_name: str = ""
    email: str = ""
    phone: str = ""
    formation: str = ""
    skills: list[str] = field(default_factory=list)
    experiences: list[dict] = field(default_factory=list)
    cv_url: str = ""

    def matches(self, offer: "JobOffer") -> float:
        """Score 0..1 de compatibilite candidat/offre."""
        score = 0.0
        # Match contrat
        if offer.contract in self.desired_contracts():
            score += 0.2
        # Match localisation (simplifie)
        if offer.location.lower() in ["france", "paris", "remote"]:
            score += 0.1
        # Match skills
        if self.skills and offer.required_skills:
            overlap = set(s.lower() for s in self.skills) & set(s.lower() for s in offer.required_skills)
            if overlap:
                score += 0.7 * len(overlap) / len(set(s.lower() for s in offer.required_skills))
        return min(1.0, score)

    def desired_contracts(self) -> list[ContractType]:
        return [ContractType.STAGE, ContractType.ALTERNANCE, ContractType.CDI]


@dataclass
class JobOffer:
    offer_id: str = field(default_factory=lambda: str(uuid4()))
    external_id: str = ""
    source: str = ""  # linkedin | indeed | hellowork
    title: str = ""
    company: str = ""
    location: str = ""
    contract: ContractType = ContractType.CDI
    description: str = ""
    url: str = ""
    posted_at: date | None = None
    required_skills: list[str] = field(default_factory=list)
    salary_range: tuple[int, int] | None = None
    raw: dict = field(default_factory=dict)


@dataclass
class Application:
    application_id: str = field(default_factory=lambda: str(uuid4()))
    candidate_id: str = ""
    offer_id: str = ""
    status: ApplicationStatus = ApplicationStatus.DRAFT
    cv_id: str = ""
    lettre_id: str = ""
    sent_at: datetime | None = None
    response_received_at: datetime | None = None
    notes: str = ""


class EmploymentDomain:
    """Service de domaine : regles metier pures, independantes des agents."""

    @staticmethod
    def is_offer_recent(offer: JobOffer, max_days: int = 30) -> bool:
        if offer.posted_at is None:
            return True
        return (date.today() - offer.posted_at).days <= max_days

    @staticmethod
    def should_apply(candidate: Candidate, offer: JobOffer, min_score: float = 0.4) -> bool:
        return offer.contract in candidate.desired_contracts() and candidate.matches(offer) >= min_score

    @staticmethod
    def can_send(application: Application) -> tuple[bool, str]:
        if application.status != ApplicationStatus.DRAFT:
            return False, f"Deja envoyee (status={application.status.value})"
        if not application.cv_id:
            return False, "CV manquant"
        if not application.lettre_id:
            return False, "Lettre manquante"
        return True, "OK"