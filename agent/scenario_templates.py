"""
Generic scenario templates for platform-agnostic simulations.
These are abstract scenarios that can be adapted to any simulation platform.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Dict, List

try:
    from .simulation_engine import SimulationScenario, SimulationStep, SimulationPlatform
except ImportError:
    from simulation_engine import SimulationScenario, SimulationStep, SimulationPlatform


def create_lateral_movement_scenario(platform: SimulationPlatform = SimulationPlatform.MOCK) -> SimulationScenario:
    """Generic lateral movement simulation scenario."""

    return SimulationScenario(
        scenario_id="lateral_movement_generic",
        name="Network Lateral Movement Simulation",
        description="Simulate lateral movement across network segments",
        platform=platform,
        target_selector={
            "initial_host": "workstation-1",
            "target_host": "server-1",
            "network_segment": "corporate"
        },
        parameters={
            "stealth_level": "medium",
            "technique_category": "network_discovery"
        },
        steps=[
            SimulationStep(
                step_id="initial_reconnaissance",
                name="Initial Network Reconnaissance",
                description="Discover network topology and identify targets",
                platform_command="PLATFORM_DISCOVERY_COMMAND",  # Platform will replace this
                estimated_duration=timedelta(minutes=5)
            ),
            SimulationStep(
                step_id="credential_discovery",
                name="Credential Discovery",
                description="Attempt to discover cached credentials",
                platform_command="PLATFORM_CREDENTIAL_COMMAND",
                estimated_duration=timedelta(minutes=10)
            ),
            SimulationStep(
                step_id="lateral_movement",
                name="Lateral Movement Execution",
                description="Move to target system using discovered credentials",
                platform_command="PLATFORM_LATERAL_COMMAND",
                estimated_duration=timedelta(minutes=15)
            ),
            SimulationStep(
                step_id="persistence",
                name="Establish Persistence",
                description="Create persistence mechanism on target",
                platform_command="PLATFORM_PERSISTENCE_COMMAND",
                estimated_duration=timedelta(minutes=8)
            )
        ],
        estimated_total_time=timedelta(minutes=38)
    )


def create_privilege_escalation_scenario(platform: SimulationPlatform = SimulationPlatform.MOCK) -> SimulationScenario:
    """Generic privilege escalation simulation scenario."""

    return SimulationScenario(
        scenario_id="privilege_escalation_generic",
        name="Privilege Escalation Simulation",
        description="Simulate privilege escalation to administrative access",
        platform=platform,
        target_selector={
            "target_host": "server-1",
            "current_user": "standard_user",
            "target_privilege": "administrator"
        },
        parameters={
            "escalation_method": "credential_abuse",
            "detection_evasion": True
        },
        steps=[
            SimulationStep(
                step_id="system_enumeration",
                name="System Enumeration",
                description="Enumerate system configuration and running services",
                platform_command="PLATFORM_ENUM_COMMAND",
                estimated_duration=timedelta(minutes=7)
            ),
            SimulationStep(
                step_id="vulnerability_identification",
                name="Vulnerability Identification",
                description="Identify potential privilege escalation vectors",
                platform_command="PLATFORM_VULN_SCAN_COMMAND",
                estimated_duration=timedelta(minutes=12)
            ),
            SimulationStep(
                step_id="exploit_execution",
                name="Privilege Escalation Exploit",
                description="Execute privilege escalation technique",
                platform_command="PLATFORM_ESCALATE_COMMAND",
                estimated_duration=timedelta(minutes=10)
            ),
            SimulationStep(
                step_id="verification",
                name="Privilege Verification",
                description="Verify administrative access was obtained",
                platform_command="PLATFORM_VERIFY_COMMAND",
                estimated_duration=timedelta(minutes=3)
            )
        ],
        estimated_total_time=timedelta(minutes=32)
    )


def create_data_exfiltration_scenario(platform: SimulationPlatform = SimulationPlatform.MOCK) -> SimulationScenario:
    """Generic data exfiltration simulation scenario."""

    return SimulationScenario(
        scenario_id="data_exfiltration_generic",
        name="Data Exfiltration Simulation",
        description="Simulate sensitive data discovery and exfiltration",
        platform=platform,
        target_selector={
            "data_sources": ["fileserver", "database"],
            "data_types": ["financial", "customer_data", "intellectual_property"]
        },
        parameters={
            "exfiltration_method": "network_transfer",
            "encryption": True,
            "staging_location": "/tmp/staging"
        },
        steps=[
            SimulationStep(
                step_id="data_discovery",
                name="Sensitive Data Discovery",
                description="Search for and identify sensitive data repositories",
                platform_command="PLATFORM_DATA_DISCOVERY_COMMAND",
                estimated_duration=timedelta(minutes=15)
            ),
            SimulationStep(
                step_id="data_staging",
                name="Data Staging",
                description="Copy sensitive data to staging location",
                platform_command="PLATFORM_DATA_COPY_COMMAND",
                estimated_duration=timedelta(minutes=20)
            ),
            SimulationStep(
                step_id="data_compression",
                name="Data Compression and Encryption",
                description="Compress and encrypt data for exfiltration",
                platform_command="PLATFORM_DATA_ENCRYPT_COMMAND",
                estimated_duration=timedelta(minutes=10)
            ),
            SimulationStep(
                step_id="exfiltration",
                name="Data Exfiltration",
                description="Transfer data to external location",
                platform_command="PLATFORM_EXFIL_COMMAND",
                estimated_duration=timedelta(minutes=25)
            )
        ],
        estimated_total_time=timedelta(hours=1, minutes=10)
    )


def create_persistence_scenario(platform: SimulationPlatform = SimulationPlatform.MOCK) -> SimulationScenario:
    """Generic persistence establishment scenario."""

    return SimulationScenario(
        scenario_id="persistence_generic",
        name="Persistence Establishment Simulation",
        description="Simulate establishing persistent access to compromised systems",
        platform=platform,
        target_selector={
            "target_hosts": ["workstation-1", "server-1"],
            "persistence_methods": ["scheduled_task", "service", "registry"]
        },
        parameters={
            "stealth_level": "high",
            "backup_methods": 2
        },
        steps=[
            SimulationStep(
                step_id="persistence_planning",
                name="Persistence Method Selection",
                description="Analyze system and select appropriate persistence methods",
                platform_command="PLATFORM_PERSISTENCE_ANALYSIS_COMMAND",
                estimated_duration=timedelta(minutes=8)
            ),
            SimulationStep(
                step_id="primary_persistence",
                name="Primary Persistence Mechanism",
                description="Establish primary persistence mechanism",
                platform_command="PLATFORM_PRIMARY_PERSISTENCE_COMMAND",
                estimated_duration=timedelta(minutes=12)
            ),
            SimulationStep(
                step_id="backup_persistence",
                name="Backup Persistence Mechanism",
                description="Establish secondary persistence for redundancy",
                platform_command="PLATFORM_BACKUP_PERSISTENCE_COMMAND",
                estimated_duration=timedelta(minutes=10)
            ),
            SimulationStep(
                step_id="persistence_testing",
                name="Persistence Verification",
                description="Verify persistence mechanisms survive reboot",
                platform_command="PLATFORM_PERSISTENCE_TEST_COMMAND",
                estimated_duration=timedelta(minutes=15)
            )
        ],
        estimated_total_time=timedelta(minutes=45)
    )


def create_custom_scenario(
    scenario_id: str,
    name: str,
    description: str,
    steps: List[Dict[str, str]],
    platform: SimulationPlatform = SimulationPlatform.MOCK,
    target_selector: Dict = None,
    parameters: Dict = None
) -> SimulationScenario:
    """Create a custom simulation scenario from user input."""

    simulation_steps = []
    total_time = timedelta(0)

    for i, step_data in enumerate(steps):
        duration = timedelta(minutes=step_data.get("duration_minutes", 5))
        total_time += duration

        step = SimulationStep(
            step_id=f"custom_step_{i+1}",
            name=step_data.get("name", f"Custom Step {i+1}"),
            description=step_data.get("description", "User-defined simulation step"),
            platform_command=step_data.get("command", "PLATFORM_CUSTOM_COMMAND"),
            estimated_duration=duration
        )
        simulation_steps.append(step)

    return SimulationScenario(
        scenario_id=scenario_id,
        name=name,
        description=description,
        platform=platform,
        target_selector=target_selector or {},
        parameters=parameters or {},
        steps=simulation_steps,
        estimated_total_time=total_time
    )


# Scenario registry for easy access
SCENARIO_TEMPLATES: Dict[str, callable] = {
    "lateral_movement": create_lateral_movement_scenario,
    "privilege_escalation": create_privilege_escalation_scenario,
    "data_exfiltration": create_data_exfiltration_scenario,
    "persistence": create_persistence_scenario,
}


def get_available_scenarios() -> List[str]:
    """Get list of available scenario template names."""
    return list(SCENARIO_TEMPLATES.keys())


def create_scenario_from_template(
    template_name: str,
    platform: SimulationPlatform = SimulationPlatform.MOCK,
    **kwargs
) -> SimulationScenario:
    """Create a scenario instance from a template."""

    if template_name not in SCENARIO_TEMPLATES:
        raise ValueError(f"Unknown scenario template: {template_name}")

    template_func = SCENARIO_TEMPLATES[template_name]
    return template_func(platform=platform, **kwargs)


def get_scenario_for_graph_topology(graph_data: Dict) -> SimulationScenario:
    """Suggest an appropriate scenario based on graph topology."""

    # Analyze graph to suggest appropriate scenario
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])

    # Count different node types
    node_roles = [node.get("attrs", {}).get("role", "") for node in nodes]
    has_dc = any("domain-controller" in role for role in node_roles)
    has_servers = any("server" in role for role in node_roles)
    has_workstations = any("workstation" in role for role in node_roles)

    # Choose scenario based on topology
    if has_dc and has_workstations:
        return create_lateral_movement_scenario()
    elif has_servers:
        return create_privilege_escalation_scenario()
    else:
        return create_persistence_scenario()