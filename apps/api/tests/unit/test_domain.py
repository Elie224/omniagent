"""Tests du domain layer (Vague B : focus Emploi).

Les tests finance/marketing ont ete retires avec leurs modules.
"""
from datetime import date, timedelta


def test_candidate_matches_offer():
    from omniagent.domain.employment.entities import Candidate, JobOffer, ContractType
    c = Candidate(skills=["Python", "FastAPI", "SQL"])
    o = JobOffer(contract=ContractType.CDI, required_skills=["Python", "FastAPI", "AWS"])
    score = c.matches(o)
    assert 0.5 < score < 1.0  # 2/3 match


def test_employment_should_apply():
    from omniagent.domain.employment.entities import Candidate, JobOffer, ContractType
    c = Candidate(skills=["Python"], formation="M2")
    o = JobOffer(contract=ContractType.CDI, required_skills=["Python"])
    assert c.matches(o) > 0
    from omniagent.domain.employment.entities import EmploymentDomain
    assert EmploymentDomain.should_apply(c, o) is True