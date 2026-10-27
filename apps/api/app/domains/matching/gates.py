from app.domains.documents.schemas import ExtractedDocumentData
from app.domains.jobs.model import Job
from app.domains.matching.schemas import HardGateResult


def evaluate_hard_gate(*, job: Job, profile: ExtractedDocumentData) -> HardGateResult:
    """Check eligibility rules that must pass before any weighted score is shown.

    Unknown fields are never treated as failures: they are surfaced as `unknowns`
    so the caller can decide whether to ask the user for the missing fact.
    """

    checks: dict[str, bool] = {}
    reasons: list[str] = []
    unknowns: list[str] = []
    desired_cities = {city.strip().lower() for city in profile.desired_cities}
    checks["city"] = not desired_cities or not job.city or job.city.lower() in desired_cities
    if not checks["city"]:
        reasons.append(f"职位城市 {job.city} 不在简历期望城市中")
    if job.city and not desired_cities:
        unknowns.append("简历未填写期望城市")
    checks["days_per_week"] = (
        job.internship_days_per_week is None
        or profile.available_days_per_week is None
        or profile.available_days_per_week >= job.internship_days_per_week
    )
    if not checks["days_per_week"]:
        reasons.append("每周可到岗天数低于职位要求")
    if job.internship_days_per_week and profile.available_days_per_week is None:
        unknowns.append("简历未填写每周可到岗天数")
    checks["months"] = (
        job.internship_months is None
        or profile.available_months is None
        or profile.available_months >= job.internship_months
    )
    if not checks["months"]:
        reasons.append("可实习月数短于职位要求")
    if job.internship_months and profile.available_months is None:
        unknowns.append("简历未填写可实习月数")
    return HardGateResult(
        passed=all(checks.values()), checks=checks, reasons=reasons, unknowns=unknowns
    )
