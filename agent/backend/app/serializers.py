from __future__ import annotations

from typing import Any, Dict

from agent.models import ScenarioJob


def serialize_job(job: ScenarioJob) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "jobId": job.job_id,
        "status": job.status.value,
        "platform": job.plan.platform,
        "scenarioId": job.plan.scenario_id,
        "objective": job.plan.objective,
        "targetSelector": job.plan.target_selector,
    }
    if job.plan.parameters:
        payload["params"] = job.plan.parameters
    if job.findings is not None:
        payload["findings"] = job.findings
    return payload
