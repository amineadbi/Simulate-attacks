from __future__ import annotations

from typing import Any, Dict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate

from ..models import ScenarioJob, ScenarioPlan, ScenarioStatus
from ..simulation_engine import SimulationPlatform, get_simulation_engine
from ..scenario_templates import get_available_scenarios, create_scenario_from_template
from ..state import AgentState, merged_context
from ..tools import ToolRegistry

PLAN_SCHEMA = {
    "title": "SimulationScenarioPlan",
    "description": "Plan for executing a cybersecurity simulation scenario",
    "type": "object",
    "properties": {
        "platform": {"type": "string", "enum": ["mock", "caldera", "metasploit", "atomic_red", "custom"]},
        "scenario_template": {"type": "string", "enum": get_available_scenarios()},
        "objective": {"type": "string"},
        "target_selector": {"type": "object"},
        "parameters": {"type": "object"},
    },
    "required": ["platform", "scenario_template", "objective"],
}

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are a cybersecurity simulation planner. Based on the user's request and network graph context,
            design an appropriate simulation scenario.

            Available scenario templates: {available_scenarios}
            Available platforms: mock (testing), caldera (MITRE), metasploit (framework), atomic_red (techniques), custom

            Consider the network topology to suggest realistic targets and parameters.
            Default to 'mock' platform for testing and demonstration purposes.

            Return ONLY valid JSON matching the schema.""",
        ),
        (
            "user",
            "Recent conversation:\n{transcript}\n\nGraph context: {graph_context}\n\nPlan the simulation:",
        ),
    ]
)


async def plan_scenario(state: AgentState, llm: BaseChatModel) -> Dict[str, Any]:
    """Plan a simulation scenario based on user request and graph context."""

    messages = state.get("messages", [])
    transcript = "\n".join(f"{m.type}: {m.content}" for m in messages[-6:])

    # Get graph context for better planning
    graph_context = "No graph loaded"
    context = state.get("context", {})
    if "graph_loaded" in context:
        graph_context = f"Graph with {context.get('node_count', 0)} nodes and {context.get('edge_count', 0)} edges"

    structured_llm = llm.with_structured_output(schema=PLAN_SCHEMA)
    raw_plan = await structured_llm.ainvoke(
        prompt.invoke({
            "transcript": transcript,
            "graph_context": graph_context,
            "available_scenarios": ", ".join(get_available_scenarios())
        }).to_messages()
    )

    # Create simulation scenario from template
    try:
        platform = SimulationPlatform(raw_plan["platform"])
        scenario_template = raw_plan["scenario_template"]

        scenario = create_scenario_from_template(
            scenario_template,
            platform=platform
        )

        # Override with user-specified parameters
        scenario.target_selector.update(raw_plan.get("target_selector", {}))
        scenario.parameters.update(raw_plan.get("parameters", {}))

        # Store the simulation scenario in a simplified plan format for compatibility
        plan = ScenarioPlan(
            platform=platform.value,
            scenario_id=scenario.scenario_id,
            objective=raw_plan["objective"],
            target_selector=scenario.target_selector,
            parameters=scenario.parameters,
        )

        message = AIMessage(
            content=(
                f"📋 Planned simulation: **{scenario.name}**\n"
                f"🎯 Platform: {platform.value}\n"
                f"🎪 Template: {scenario_template}\n"
                f"⏱️ Estimated time: {scenario.estimated_total_time}\n"
                f"📝 Objective: {raw_plan['objective']}\n\n"
                f"Ready to execute {len(scenario.steps)} simulation steps. Confirm to proceed."
            )
        )

        # Store the full scenario for execution
        ctx_update = merged_context(state,
            pending_simulation_scenario=scenario.model_dump(),
            simulation_ready=True
        )

        return {
            **ctx_update,
            "pending_plan": plan,
            "messages": [message]
        }

    except Exception as e:
        message = AIMessage(
            content=f"❌ Failed to plan simulation: {str(e)}\n"
                   f"Available templates: {', '.join(get_available_scenarios())}"
        )
        return {"messages": [message]}


async def execute_scenario(state: AgentState, tools: ToolRegistry) -> Dict[str, Any]:
    """Execute the planned simulation scenario using the simulation engine."""

    context = state.get("context", {})
    scenario_data = context.get("pending_simulation_scenario")

    if not scenario_data:
        message = AIMessage(content="❌ No simulation scenario ready for execution. Please plan a scenario first.")
        return {"messages": [message]}

    # Reconstruct scenario from stored data
    from ..simulation_engine import SimulationScenario
    scenario = SimulationScenario(**scenario_data)

    # Start simulation using the simulation engine
    engine = get_simulation_engine()

    if scenario.platform == SimulationPlatform.CALDERA and SimulationPlatform.CALDERA not in engine.platform_adapters:
        message = AIMessage(content="Caldera integration is not configured or unavailable.")
        return {"messages": [message]}

    try:
        simulation_job = await engine.start_simulation(scenario)

        # Create compatible ScenarioJob for existing workflow
        job = ScenarioJob(
            job_id=simulation_job.job_id,
            plan=ScenarioPlan(
                platform=scenario.platform.value,
                scenario_id=scenario.scenario_id,
                objective=scenario.description,
                target_selector=scenario.target_selector,
                parameters=scenario.parameters,
            ),
            status=ScenarioStatus.PENDING,
            findings=None
        )

        message = AIMessage(
            content=(
                f"🚀 **Simulation Started!**\n\n"
                f"📊 Job ID: `{simulation_job.job_id}`\n"
                f"🎯 Scenario: {scenario.name}\n"
                f"⚡ Platform: {scenario.platform.value}\n"
                f"📈 Steps: {len(scenario.steps)}\n"
                f"⏱️ Estimated time: {scenario.estimated_total_time}\n\n"
                f"Monitor progress with real-time updates. The simulation is now running..."
            )
        )

        ctx_update = merged_context(state,
            last_job_id=simulation_job.job_id,
            last_job_platform=scenario.platform.value,
            simulation_job_id=simulation_job.job_id,
            pending_simulation_scenario=None,
            simulation_ready=False
        )

        return {
            **ctx_update,
            "active_job": job,
            "pending_plan": None,
            "messages": [message],
        }

    except Exception as e:
        message = AIMessage(
            content=f"❌ **Simulation Failed to Start**\n\nError: {str(e)}\n\nPlease check the scenario configuration and try again."
        )
        return {"messages": [message]}


async def monitor_job(state: AgentState, tools: ToolRegistry) -> Dict[str, Any]:
    """Monitor simulation job progress using the simulation engine."""

    job = state.get("active_job")
    if not job:
        return {}

    context = state.get("context", {})
    simulation_job_id = context.get("simulation_job_id")

    if not simulation_job_id:
        # Fallback to legacy monitoring if no simulation job ID
        message = AIMessage(content=f"⚠️ Legacy job {job.job_id} - limited monitoring available.")
        return {"messages": [message]}

    # Get current simulation status
    engine = get_simulation_engine()
    simulation_job = await engine.get_job_status(simulation_job_id)

    if not simulation_job:
        message = AIMessage(content=f"❌ Simulation job {simulation_job_id} not found.")
        return {"messages": [message]}

    # Convert simulation status to scenario status
    status_mapping = {
        "pending": ScenarioStatus.PENDING,
        "initializing": ScenarioStatus.PENDING,
        "running": ScenarioStatus.RUNNING,
        "paused": ScenarioStatus.RUNNING,
        "completed": ScenarioStatus.SUCCEEDED,
        "failed": ScenarioStatus.FAILED,
        "cancelled": ScenarioStatus.CANCELLED,
    }

    status = status_mapping.get(simulation_job.status.value, ScenarioStatus.PENDING)
    updated_job = job.model_copy(update={"status": status})

    # Generate detailed status message
    recent_events = simulation_job.events[-3:] if simulation_job.events else []
    recent_activity = "\n".join([f"• {event.description}" for event in recent_events])

    if simulation_job.status.value == "running":
        current_step = simulation_job.current_step + 1
        total_steps = simulation_job.total_steps

        message_content = (
            f"🔄 **Simulation In Progress**\n\n"
            f"📊 Job: `{job.job_id}`\n"
            f"📈 Progress: {simulation_job.progress_percentage:.1f}% "
            f"(Step {current_step}/{total_steps})\n"
            f"✅ Completed: {simulation_job.steps_completed}\n"
            f"❌ Failed: {simulation_job.steps_failed}\n\n"
            f"**Recent Activity:**\n{recent_activity if recent_activity else 'No recent activity'}"
        )

    elif simulation_job.status.value == "completed":
        findings = simulation_job.findings
        success_rate = findings.get("summary", {}).get("success_rate", 0) * 100

        message_content = (
            f"✅ **Simulation Completed**\n\n"
            f"📊 Job: `{job.job_id}`\n"
            f"🎯 Success Rate: {success_rate:.1f}%\n"
            f"⏱️ Duration: {findings.get('summary', {}).get('execution_time_seconds', 0):.0f}s\n"
            f"✅ Steps Completed: {simulation_job.steps_completed}/{simulation_job.total_steps}\n\n"
            f"**Key Findings:**\n"
            + "\n".join([f"• {rec}" for rec in findings.get("recommendations", [])[:3]])
        )

        # Store findings in the job
        updated_job = updated_job.model_copy(update={"findings": findings})

    elif simulation_job.status.value == "failed":
        error_events = [e for e in simulation_job.events if e.severity in ["ERROR", "CRITICAL"]]
        last_error = error_events[-1].description if error_events else "Unknown error"

        message_content = (
            f"❌ **Simulation Failed**\n\n"
            f"📊 Job: `{job.job_id}`\n"
            f"🛑 Error: {last_error}\n"
            f"✅ Completed: {simulation_job.steps_completed}/{simulation_job.total_steps}\n\n"
            f"Check logs for detailed error information."
        )

    else:
        message_content = f"📊 Job {job.job_id} status: {simulation_job.status.value}"

    message = AIMessage(content=message_content)

    # Update context
    context_updates = {
        "last_job_id": job.job_id,
        "last_job_platform": job.plan.platform,
        "last_job_status": status.value,
        "simulation_progress": simulation_job.progress_percentage,
    }

    if status in {ScenarioStatus.SUCCEEDED, ScenarioStatus.FAILED, ScenarioStatus.CANCELLED}:
        context_updates["last_job_final_status"] = status.value
        context_updates["simulation_job_id"] = None  # Clear completed job

    ctx_update = merged_context(state, **context_updates)

    payload: Dict[str, Any] = {
        **ctx_update,
        "active_job": updated_job,
        "messages": [message],
    }

    # Clear active job when completed
    if status in {ScenarioStatus.SUCCEEDED, ScenarioStatus.FAILED, ScenarioStatus.CANCELLED}:
        payload["active_job"] = None

    return payload
