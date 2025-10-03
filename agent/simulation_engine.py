"""
Generic platform-agnostic simulation engine.
Provides mock simulation capabilities with pluggable platform adapters.
Focus: Agent workflow integration, not specific attack implementations.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Import WebSocket event system for real-time updates
try:
    from .backend.app.events import get_broker
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False


class SimulationStatus(str, Enum):
    """Generic simulation status."""
    PENDING = "pending"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SimulationPlatform(str, Enum):
    """Supported simulation platforms."""
    MOCK = "mock"           # Mock platform for testing
    CALDERA = "caldera"     # MITRE Caldera
    METASPLOIT = "metasploit"  # Metasploit Framework
    ATOMIC_RED = "atomic_red"  # Atomic Red Team
    CUSTOM = "custom"       # Custom platform adapter


class SimulationEvent(BaseModel):
    """Individual event in a simulation."""
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.now)
    event_type: str  # "step_started", "step_completed", "detection", "error"
    description: str
    severity: str = "INFO"  # INFO, WARNING, ERROR, CRITICAL
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SimulationStep(BaseModel):
    """Individual step in a simulation scenario."""
    step_id: str
    name: str
    description: str
    platform_command: str  # Platform-specific command/payload
    platform_metadata: Dict[str, Any] = Field(default_factory=dict)
    estimated_duration: timedelta = Field(default=timedelta(minutes=5))

    # Execution state
    status: SimulationStatus = SimulationStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class SimulationScenario(BaseModel):
    """Generic simulation scenario definition."""
    scenario_id: str
    name: str
    description: str
    platform: SimulationPlatform

    # Target configuration
    target_selector: Dict[str, Any] = Field(default_factory=dict)
    parameters: Dict[str, Any] = Field(default_factory=dict)

    # Execution steps
    steps: List[SimulationStep] = Field(default_factory=list)
    estimated_total_time: timedelta = Field(default=timedelta(minutes=30))
    platform_metadata: Dict[str, Any] = Field(default_factory=dict)


class SimulationJob(BaseModel):
    """Active simulation job with state tracking."""
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scenario: SimulationScenario

    # Execution state
    status: SimulationStatus = SimulationStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    current_step: int = 0

    # Results and events
    events: List[SimulationEvent] = Field(default_factory=list)
    progress_percentage: float = 0.0
    findings: Dict[str, Any] = Field(default_factory=dict)
    platform_context: Dict[str, Any] = Field(default_factory=dict)

    # Metrics
    steps_completed: int = 0
    steps_failed: int = 0
    total_steps: int = 0

    def add_event(self, event_type: str, description: str, severity: str = "INFO", **metadata):
        """Add an event to the simulation log."""
        event = SimulationEvent(
            event_type=event_type,
            description=description,
            severity=severity,
            metadata=metadata
        )
        self.events.append(event)

        # Emit WebSocket event for real-time updates
        if WEBSOCKET_AVAILABLE:
            asyncio.create_task(self._emit_websocket_event(event))

        return event

    async def _emit_websocket_event(self, event: SimulationEvent):
        """Emit simulation event via WebSocket for real-time frontend updates."""
        try:
            broker = get_broker()
            await broker.emit(
                event_type="simulation_event",
                payload={
                    "job_id": self.job_id,
                    "event": event.model_dump(),
                    "progress": self.progress_percentage,
                    "status": self.status.value,
                    "current_step": self.current_step,
                    "total_steps": self.total_steps,
                    "steps_completed": self.steps_completed,
                    "steps_failed": self.steps_failed
                },
                level=event.severity.lower(),
                source="simulation_engine"
            )
        except Exception as e:
            print(f"Failed to emit WebSocket event: {e}")

    def update_progress(self):
        """Update progress percentage based on completed steps."""
        if self.total_steps > 0:
            self.progress_percentage = (self.steps_completed / self.total_steps) * 100.0

        # Emit progress update via WebSocket
        if WEBSOCKET_AVAILABLE:
            asyncio.create_task(self._emit_progress_update())

    async def _emit_progress_update(self):
        """Emit progress update via WebSocket."""
        try:
            broker = get_broker()
            await broker.emit(
                event_type="simulation_progress",
                payload={
                    "job_id": self.job_id,
                    "progress": self.progress_percentage,
                    "status": self.status.value,
                    "current_step": self.current_step,
                    "total_steps": self.total_steps,
                    "steps_completed": self.steps_completed,
                    "steps_failed": self.steps_failed
                },
                level="info",
                source="simulation_engine"
            )
        except Exception as e:
            print(f"Failed to emit progress update: {e}")


class PlatformAdapter:
    """Base class for platform-specific simulation adapters."""

    def __init__(self, platform: SimulationPlatform, config: Dict[str, Any]):
        self.platform = platform
        self.config = config

    async def execute_step(self, step: SimulationStep, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a simulation step on the platform."""
        raise NotImplementedError("Subclasses must implement execute_step")

    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get current job status from the platform."""
        raise NotImplementedError("Subclasses must implement get_job_status")

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job on the platform."""
        raise NotImplementedError("Subclasses must implement cancel_job")


class MockPlatformAdapter(PlatformAdapter):
    """Mock platform adapter for testing and development."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(SimulationPlatform.MOCK, config)
        self._jobs: Dict[str, Dict[str, Any]] = {}

    async def execute_step(self, step: SimulationStep, context: Dict[str, Any]) -> Dict[str, Any]:
        """Mock step execution with realistic timing."""

        # Simulate execution time
        execution_time = min(5.0, step.estimated_duration.total_seconds())
        await asyncio.sleep(execution_time)

        # Mock success/failure based on step complexity
        import random
        success_rate = context.get("success_rate", 0.85)
        success = random.random() < success_rate

        if success:
            return {
                "status": "success",
                "output": f"Mock execution completed for: {step.name}",
                "artifacts": [f"mock_artifact_{step.step_id}.log"],
                "execution_time": execution_time
            }
        else:
            return {
                "status": "failed",
                "error": f"Mock execution failed for: {step.name}",
                "execution_time": execution_time
            }

    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Mock job status retrieval."""
        if job_id in self._jobs:
            return self._jobs[job_id]

        return {
            "job_id": job_id,
            "status": "not_found",
            "message": "Job not found in mock platform"
        }

    async def cancel_job(self, job_id: str) -> bool:
        """Mock job cancellation."""
        if job_id in self._jobs:
            self._jobs[job_id]["status"] = "cancelled"
            return True
        return False


class CalderaPlatformAdapter(PlatformAdapter):
    'Adapter that orchestrates MITRE Caldera operations.'

    def __init__(self, settings, logger=None):
        config = settings.model_dump() if hasattr(settings, 'model_dump') else {}
        super().__init__(SimulationPlatform.CALDERA, config)
        import logging as _logging
        self.logger = logger or _logging.getLogger(__name__)
        self.settings = settings
        self._client = None
        self._operations: Dict[str, Dict[str, Any]] = {}

    def _ensure_client(self):
        if self._client is None:
            from .caldera import CalderaClient
            self._client = CalderaClient(self.settings)
        return self._client

    async def execute_step(self, step: SimulationStep, context: Dict[str, Any]) -> Dict[str, Any]:
        caldera_meta = step.platform_metadata.get('caldera', {})
        action = caldera_meta.get('action', 'noop')
        job_id = context.get('job_id')

        if action == 'create_operation':
            return await self._create_operation(job_id, step, context, caldera_meta)
        if action == 'await_links':
            minimum = int(caldera_meta.get('minimum_links', 1))
            return await self._await_links(job_id, minimum)
        if action == 'await_completion':
            return await self._await_completion(job_id, caldera_meta)
        if action == 'collect_results':
            return await self._collect_results(job_id)

        return {'status': 'success', 'detail': 'No Caldera action defined'}

    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        ctx = self._operations.get(job_id)
        if not ctx:
            return {'job_id': job_id, 'status': 'not_started'}
        client = self._ensure_client()
        operation = await client.get_operation(ctx['operation_id'])
        return {'job_id': job_id, 'status': operation.get('state'), 'operation': operation}

    async def cancel_job(self, job_id: str) -> bool:
        ctx = self._operations.get(job_id)
        if not ctx:
            return False
        client = self._ensure_client()
        await client.update_operation_state(ctx['operation_id'], 'finished')
        self._operations.pop(job_id, None)
        return True

    async def _create_operation(self, job_id: str, step: SimulationStep, context: Dict[str, Any], caldera_meta: Dict[str, Any]) -> Dict[str, Any]:
        client = self._ensure_client()
        scenario_meta = context.get('scenario_metadata', {}).get('caldera', {})
        parameter_meta = context.get('parameters', {}).get('caldera', {})
        operation_cfg: Dict[str, Any] = {}
        operation_cfg.update(scenario_meta.get('operation', {}))
        operation_cfg.update(parameter_meta.get('operation', {}))

        import uuid as _uuid

        name = operation_cfg.get('name') or f"{context.get('scenario_name', 'simulation')}-{_uuid.uuid4().hex[:6]}"
        payload: Dict[str, Any] = {
            'index': 'operations',
            'name': name,
            'adversary_id': operation_cfg.get('adversary_id', ''),
            'group': operation_cfg.get('group', ''),
            'planner': operation_cfg.get('planner', 'atomic'),
            'source': operation_cfg.get('source', 'basic'),
            'jitter': operation_cfg.get('jitter', '2/8'),
            'autonomous': int(operation_cfg.get('autonomous', 1)),
            'auto_close': int(operation_cfg.get('auto_close', 0)),
            'visibility': operation_cfg.get('visibility', 50),
            'phases_enabled': int(operation_cfg.get('phases_enabled', 1)),
        }

        operation = await client.create_operation(payload=payload)
        operation_id = operation.get('id')

        if caldera_meta.get('auto_start', True):
            await client.update_operation_state(operation_id, 'running')

        ctx = {'operation_id': operation_id, 'links_seen': set()}
        self._operations[job_id] = ctx

        detail = {'operation_id': operation_id, 'operation_payload': payload}
        return {
            'status': 'success',
            'operation_id': operation_id,
            'job_context': {'caldera': detail},
            'operation': operation,
        }

    async def _await_links(self, job_id: str, minimum_links: int) -> Dict[str, Any]:
        ctx = self._operations.get(job_id)
        if not ctx:
            raise RuntimeError('Caldera operation not initialized')
        client = self._ensure_client()
        import time
        poll_interval = self.settings.operation_poll_interval_seconds
        deadline = time.monotonic() + self.settings.operation_poll_timeout_seconds
        seen = ctx.setdefault('links_seen', set())
        new_links = []
        while time.monotonic() < deadline:
            operation = await client.get_operation(ctx['operation_id'])
            chain = operation.get('chain', []) or []
            for link in chain:
                link_id = link.get('id')
                if link_id and link_id not in seen:
                    seen.add(link_id)
                    new_links.append(link)
            if len(seen) >= max(minimum_links, 0):
                return {'status': 'success', 'new_links': new_links, 'total_links': len(seen)}
            await asyncio.sleep(poll_interval)
        from .caldera import CalderaOperationTimeout
        raise CalderaOperationTimeout(f'Caldera operation produced only {len(seen)} links in allotted time')

    async def _await_completion(self, job_id: str, caldera_meta: Dict[str, Any]) -> Dict[str, Any]:
        ctx = self._operations.get(job_id)
        if not ctx:
            raise RuntimeError('Caldera operation not initialized')
        client = self._ensure_client()
        import time
        poll_interval = self.settings.operation_poll_interval_seconds
        deadline = time.monotonic() + self.settings.operation_poll_timeout_seconds
        terminal_states = caldera_meta.get('terminal_states', ['finished', 'cleanup'])
        while time.monotonic() < deadline:
            operation = await client.get_operation(ctx['operation_id'])
            state = operation.get('state')
            if state in terminal_states:
                ctx['final_operation'] = operation
                return {'status': 'success', 'state': state}
            await asyncio.sleep(poll_interval)
        from .caldera import CalderaOperationTimeout
        raise CalderaOperationTimeout('Timed out waiting for Caldera operation completion')

    async def _collect_results(self, job_id: str) -> Dict[str, Any]:
        ctx = self._operations.get(job_id)
        if not ctx:
            raise RuntimeError('Caldera operation not initialized')
        client = self._ensure_client()
        operation = ctx.get('final_operation') or await client.get_operation(ctx['operation_id'])
        links = await client.get_operation_links(ctx['operation_id'])
        artifacts = []
        for link in links:
            link_id = link.get('id')
            if link_id:
                try:
                    detail = await client.get_link_result(link_id)
                    artifacts.append(detail)
                except Exception as exc:  # noqa: BLE001
                    self.logger.debug('Failed to fetch link %s detail: %s', link_id, exc)
        report = {
            'operation': operation,
            'links': links,
            'artifacts': artifacts,
        }
        ctx['report'] = report
        return {
            'status': 'success',
            'report': report,
            'job_context': {'caldera_report': report},
        }


class SimulationEngine:
    """Generic simulation execution engine."""

    def __init__(self):
        self.active_jobs: Dict[str, SimulationJob] = {}
        self.platform_adapters: Dict[SimulationPlatform, PlatformAdapter] = {
            SimulationPlatform.MOCK: MockPlatformAdapter({})
        }

    def register_platform_adapter(self, platform: SimulationPlatform, adapter: PlatformAdapter):
        """Register a platform-specific adapter."""
        self.platform_adapters[platform] = adapter

    async def start_simulation(self, scenario: SimulationScenario) -> SimulationJob:
        """Start a new simulation job."""

        job = SimulationJob(
            scenario=scenario,
            status=SimulationStatus.INITIALIZING,
            total_steps=len(scenario.steps)
        )

        self.active_jobs[job.job_id] = job

        # Add initial event
        job.add_event(
            event_type="simulation_started",
            description=f"Started simulation: {scenario.name}",
            scenario_id=scenario.scenario_id,
            platform=scenario.platform.value
        )

        # Start execution in background
        asyncio.create_task(self._execute_simulation(job))

        return job

    async def _execute_simulation(self, job: SimulationJob):
        """Execute simulation steps sequentially."""

        adapter = self.platform_adapters.get(job.scenario.platform)
        if not adapter:
            job.status = SimulationStatus.FAILED
            job.add_event(
                event_type="simulation_failed",
                description=f"No adapter found for platform: {job.scenario.platform}",
                severity="ERROR"
            )
            return

        job.status = SimulationStatus.RUNNING
        job.start_time = datetime.now()

        try:
            for i, step in enumerate(job.scenario.steps):
                job.current_step = i

                # Update step status
                step.status = SimulationStatus.RUNNING
                step.start_time = datetime.now()

                job.add_event(
                    event_type="step_started",
                    description=f"Starting step: {step.name}",
                    step_id=step.step_id
                )

                # Execute step on platform
                context = {
                    "job_id": job.job_id,
                    "scenario_id": job.scenario.scenario_id,
                    "scenario_name": job.scenario.name,
                    "scenario_metadata": job.scenario.platform_metadata,
                    "target_selector": job.scenario.target_selector,
                    "parameters": job.scenario.parameters,
                    "platform_context": job.platform_context,
                    "step_metadata": step.platform_metadata
                }

                try:
                    result = await adapter.execute_step(step, context)
                    step.result = result
                    if isinstance(result, dict) and result.get('job_context'):
                        job.platform_context.update(result['job_context'])
                    step.end_time = datetime.now()

                    if result.get("status") == "success":
                        step.status = SimulationStatus.COMPLETED
                        job.steps_completed += 1

                        job.add_event(
                            event_type="step_completed",
                            description=f"Completed step: {step.name}",
                            step_id=step.step_id,
                            output=result.get("output", "")
                        )
                    else:
                        step.status = SimulationStatus.FAILED
                        step.error = result.get("error", "Unknown error")
                        job.steps_failed += 1

                        job.add_event(
                            event_type="step_failed",
                            description=f"Failed step: {step.name}",
                            severity="ERROR",
                            step_id=step.step_id,
                            error=step.error
                        )

                        # Continue execution for demonstration purposes
                        # In real scenarios, might want to abort on critical failures

                except Exception as e:
                    step.status = SimulationStatus.FAILED
                    step.error = str(e)
                    step.end_time = datetime.now()
                    job.steps_failed += 1

                    job.add_event(
                        event_type="step_error",
                        description=f"Error in step: {step.name}",
                        severity="ERROR",
                        step_id=step.step_id,
                        error=str(e)
                    )

                # Update progress
                job.update_progress()

                # Small delay between steps for realism
                await asyncio.sleep(1.0)

            # Simulation completed
            job.status = SimulationStatus.COMPLETED
            job.end_time = datetime.now()

            # Generate summary findings
            job.findings = self._generate_findings(job)

            job.add_event(
                event_type="simulation_completed",
                description=f"Simulation completed: {job.steps_completed}/{job.total_steps} steps successful",
                steps_completed=job.steps_completed,
                steps_failed=job.steps_failed,
                success_rate=job.steps_completed / max(1, job.total_steps)
            )

        except Exception as e:
            job.status = SimulationStatus.FAILED
            job.end_time = datetime.now()

            job.add_event(
                event_type="simulation_error",
                description=f"Simulation failed with error: {str(e)}",
                severity="CRITICAL",
                error=str(e)
            )

    def _generate_findings(self, job: SimulationJob) -> Dict[str, Any]:
        """Generate simulation findings summary."""

        total_time = (job.end_time - job.start_time).total_seconds() if job.end_time and job.start_time else 0
        success_rate = job.steps_completed / max(1, job.total_steps)

        return {
            "summary": {
                "scenario_name": job.scenario.name,
                "execution_time_seconds": total_time,
                "steps_completed": job.steps_completed,
                "steps_failed": job.steps_failed,
                "success_rate": success_rate,
                "overall_status": job.status.value
            },
            "metrics": {
                "time_per_step": total_time / max(1, job.total_steps),
                "error_rate": job.steps_failed / max(1, job.total_steps),
                "efficiency_score": success_rate * (1.0 if total_time < 300 else 0.5)  # Penalize long executions
            },
            "recommendations": self._generate_recommendations(job),
            "artifacts": [event.metadata.get("artifacts", []) for event in job.events if "artifacts" in event.metadata]
        }

    def _generate_recommendations(self, job: SimulationJob) -> List[str]:
        """Generate actionable recommendations based on simulation results."""

        recommendations = []
        success_rate = job.steps_completed / max(1, job.total_steps)

        if success_rate < 0.5:
            recommendations.append("High failure rate detected - review defensive controls")

        if job.steps_failed > 0:
            recommendations.append("Some simulation steps failed - investigate target environment")

        if success_rate > 0.8:
            recommendations.append("High success rate indicates potential security gaps")

        # Platform-specific recommendations
        if job.scenario.platform == SimulationPlatform.MOCK:
            recommendations.append("This was a mock simulation - integrate with real platforms for accurate results")

        return recommendations

    async def get_job_status(self, job_id: str) -> Optional[SimulationJob]:
        """Get current status of a simulation job."""
        return self.active_jobs.get(job_id)

    async def cancel_simulation(self, job_id: str) -> bool:
        """Cancel a running simulation."""
        job = self.active_jobs.get(job_id)
        if not job:
            return False

        if job.status in [SimulationStatus.RUNNING, SimulationStatus.PENDING]:
            job.status = SimulationStatus.CANCELLED
            job.end_time = datetime.now()

            job.add_event(
                event_type="simulation_cancelled",
                description="Simulation cancelled by user",
                severity="WARNING"
            )

            # Cancel on platform
            adapter = self.platform_adapters.get(job.scenario.platform)
            if adapter:
                await adapter.cancel_job(job_id)

            return True

        return False

    def list_active_jobs(self) -> List[SimulationJob]:
        """List all active simulation jobs."""
        return list(self.active_jobs.values())


def configure_caldera_adapter(settings) -> None:
    """Register the Caldera adapter with the global simulation engine."""
    if not getattr(settings, 'enabled', False):
        logger.info('Caldera integration disabled; skipping adapter registration')
        return

    try:
        from .caldera import CalderaUnavailableError
    except ImportError:
        logger.warning('Caldera package not available; adapter cannot be registered')
        return

    try:
        adapter = CalderaPlatformAdapter(settings)
    except CalderaUnavailableError as exc:
        logger.warning('Caldera unavailable: %s', exc)
        return

    engine = get_simulation_engine()
    engine.register_platform_adapter(SimulationPlatform.CALDERA, adapter)
    logger.info('Caldera adapter registered for simulation engine')


# Global simulation engine instance
_simulation_engine = SimulationEngine()

def get_simulation_engine() -> SimulationEngine:
    """Get the global simulation engine instance."""
    return _simulation_engine