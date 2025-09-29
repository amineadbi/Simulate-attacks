"""
Attack scenario definitions and simulation engine.
Based on MITRE ATT&CK framework with graph-aware attack path analysis.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class StealthLevel(str, Enum):
    """Attack stealth sophistication levels."""
    LOW = "low"           # Noisy, easily detected
    MEDIUM = "medium"     # Moderate operational security
    HIGH = "high"         # Advanced persistent threat level


class ComplexityLevel(str, Enum):
    """Attack complexity levels."""
    SIMPLE = "simple"         # Single-step attacks
    INTERMEDIATE = "intermediate"  # Multi-step coordinated attacks
    ADVANCED = "advanced"     # Complex multi-stage campaigns


class AccessLevel(str, Enum):
    """System access privilege levels."""
    NONE = "none"
    USER = "user"
    ADMIN = "admin"
    SYSTEM = "system"
    DOMAIN_ADMIN = "domain_admin"


class ExecutionStatus(str, Enum):
    """Attack execution status."""
    PLANNING = "planning"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DETECTED = "detected"
    CANCELLED = "cancelled"


class AttackStep(BaseModel):
    """Individual step in an attack scenario."""
    step_id: str
    name: str
    technique_id: str  # MITRE ATT&CK technique ID
    description: str

    # Prerequisites
    required_access: AccessLevel
    required_tools: List[str] = Field(default_factory=list)
    required_conditions: List[str] = Field(default_factory=list)

    # Execution parameters
    commands: List[str] = Field(default_factory=list)
    success_probability: float = Field(ge=0.0, le=1.0, default=0.8)
    detection_probability: float = Field(ge=0.0, le=1.0, default=0.3)
    estimated_time: timedelta = Field(default=timedelta(minutes=5))

    # Outcomes
    gained_access: Optional[AccessLevel] = None
    persistence_gained: bool = False
    data_accessed: List[str] = Field(default_factory=list)


class AttackScenario(BaseModel):
    """Complete attack scenario definition."""
    scenario_id: str
    name: str
    description: str

    # MITRE ATT&CK mapping
    tactics: List[str] = Field(default_factory=list)  # TA0001, TA0002, etc.
    techniques: List[str] = Field(default_factory=list)  # T1078, T1021, etc.

    # Graph requirements
    requirements: List[str] = Field(default_factory=list)
    target_types: List[str] = Field(default_factory=list)

    # Execution parameters
    stealth_level: StealthLevel = StealthLevel.MEDIUM
    complexity: ComplexityLevel = ComplexityLevel.INTERMEDIATE
    estimated_duration: timedelta = Field(default=timedelta(hours=1))

    # Attack progression
    steps: List[AttackStep] = Field(default_factory=list)


class Detection(BaseModel):
    """Security detection event."""
    detection_id: str
    timestamp: datetime
    step_id: str
    technique_id: str
    severity: str
    description: str
    source: str  # EDR, SIEM, SOC, etc.


class StepExecution(BaseModel):
    """Execution result for a single attack step."""
    step: AttackStep
    start_time: datetime
    end_time: Optional[datetime] = None
    status: ExecutionStatus
    success: bool = False
    detected: bool = False
    output: str = ""
    errors: List[str] = Field(default_factory=list)


class AttackExecution(BaseModel):
    """Complete attack execution state and results."""
    execution_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scenario: AttackScenario
    target_host: Optional[str] = None
    objective_host: Optional[str] = None

    # Execution state
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    current_step: int = 0
    status: ExecutionStatus = ExecutionStatus.PLANNING

    # Results
    completed_steps: List[StepExecution] = Field(default_factory=list)
    compromised_hosts: List[str] = Field(default_factory=list)
    accessed_data: List[str] = Field(default_factory=list)
    detected_activities: List[Detection] = Field(default_factory=list)

    # Metrics
    success_rate: float = 0.0
    stealth_score: float = 0.0
    impact_score: float = 0.0

    def calculate_metrics(self) -> None:
        """Calculate execution success and stealth metrics."""
        if not self.completed_steps:
            return

        successful_steps = sum(1 for step in self.completed_steps if step.success)
        self.success_rate = successful_steps / len(self.completed_steps)

        detected_steps = sum(1 for step in self.completed_steps if step.detected)
        self.stealth_score = 1.0 - (detected_steps / len(self.completed_steps))

        # Impact based on compromised critical systems
        critical_hosts = [h for h in self.compromised_hosts if "critical" in h.lower() or "dc-" in h]
        self.impact_score = min(1.0, len(critical_hosts) / 3.0 + len(self.accessed_data) / 10.0)


# Predefined attack scenarios based on MITRE ATT&CK
ATTACK_SCENARIOS: Dict[str, AttackScenario] = {
    "lateral_movement_smb": AttackScenario(
        scenario_id="lateral_movement_smb",
        name="Lateral Movement via SMB Shares",
        description="Simulate lateral movement through Windows SMB shares to reach high-value targets",
        tactics=["TA0008"],  # Lateral Movement
        techniques=["T1021.002", "T1135"],  # SMB/Windows Admin Shares, Network Share Discovery
        requirements=["domain_joined", "smb_enabled"],
        target_types=["windows_host", "fileserver"],
        stealth_level=StealthLevel.MEDIUM,
        complexity=ComplexityLevel.INTERMEDIATE,
        estimated_duration=timedelta(minutes=30),
        steps=[
            AttackStep(
                step_id="discover_shares",
                name="Network Share Discovery",
                technique_id="T1135",
                description="Enumerate available network shares",
                required_access=AccessLevel.USER,
                commands=["net view", "dir \\\\target\\c$"],
                success_probability=0.9,
                detection_probability=0.2,
                estimated_time=timedelta(minutes=5)
            ),
            AttackStep(
                step_id="access_admin_share",
                name="Access Administrative Share",
                technique_id="T1021.002",
                description="Connect to administrative shares",
                required_access=AccessLevel.USER,
                commands=["net use \\\\target\\admin$", "copy payload.exe \\\\target\\admin$"],
                success_probability=0.7,
                detection_probability=0.4,
                estimated_time=timedelta(minutes=10),
                gained_access=AccessLevel.ADMIN
            ),
            AttackStep(
                step_id="execute_payload",
                name="Remote Code Execution",
                technique_id="T1569.002",
                description="Execute payload on target system",
                required_access=AccessLevel.ADMIN,
                commands=["sc create malware binPath= C:\\admin$\\payload.exe", "sc start malware"],
                success_probability=0.8,
                detection_probability=0.6,
                estimated_time=timedelta(minutes=5),
                persistence_gained=True
            )
        ]
    ),

    "domain_controller_attack": AttackScenario(
        scenario_id="domain_controller_attack",
        name="Domain Controller Compromise",
        description="Full domain takeover via domain controller compromise",
        tactics=["TA0004", "TA0006"],  # Privilege Escalation, Credential Access
        techniques=["T1003.001", "T1078.002"],  # LSASS Memory, Domain Accounts
        requirements=["domain_environment", "initial_access"],
        target_types=["domain_controller"],
        stealth_level=StealthLevel.HIGH,
        complexity=ComplexityLevel.ADVANCED,
        estimated_duration=timedelta(hours=2),
        steps=[
            AttackStep(
                step_id="credential_dumping",
                name="Credential Dumping via LSASS",
                technique_id="T1003.001",
                description="Extract credentials from LSASS memory",
                required_access=AccessLevel.ADMIN,
                commands=["mimikatz.exe sekurlsa::logonpasswords"],
                success_probability=0.9,
                detection_probability=0.7,
                estimated_time=timedelta(minutes=10)
            ),
            AttackStep(
                step_id="dc_authentication",
                name="Domain Controller Authentication",
                technique_id="T1078.002",
                description="Authenticate to domain controller with stolen credentials",
                required_access=AccessLevel.USER,
                commands=["net use \\\\dc-1\\sysvol", "psexec \\\\dc-1 cmd"],
                success_probability=0.8,
                detection_probability=0.5,
                estimated_time=timedelta(minutes=15),
                gained_access=AccessLevel.DOMAIN_ADMIN
            ),
            AttackStep(
                step_id="domain_persistence",
                name="Domain Persistence via Golden Ticket",
                technique_id="T1558.001",
                description="Create golden ticket for persistent domain access",
                required_access=AccessLevel.DOMAIN_ADMIN,
                commands=["mimikatz.exe kerberos::golden"],
                success_probability=0.95,
                detection_probability=0.3,
                estimated_time=timedelta(minutes=20),
                persistence_gained=True,
                data_accessed=["domain_database", "all_user_credentials"]
            )
        ]
    ),

    "ransomware_simulation": AttackScenario(
        scenario_id="ransomware_simulation",
        name="Ransomware Deployment Simulation",
        description="Simulate ransomware spread across network infrastructure",
        tactics=["TA0001", "TA0008", "TA0040"],  # Initial Access, Lateral Movement, Impact
        techniques=["T1566.001", "T1021.002", "T1486"],  # Spearphishing, SMB, Data Encrypted
        requirements=["email_access", "network_connectivity"],
        target_types=["fileserver", "database", "backup_system"],
        stealth_level=StealthLevel.LOW,
        complexity=ComplexityLevel.ADVANCED,
        estimated_duration=timedelta(hours=4),
        steps=[
            AttackStep(
                step_id="initial_infection",
                name="Spearphishing Email Infection",
                technique_id="T1566.001",
                description="Initial compromise via malicious email attachment",
                required_access=AccessLevel.NONE,
                commands=["outlook.exe malicious_attachment.docx"],
                success_probability=0.6,
                detection_probability=0.4,
                estimated_time=timedelta(minutes=30),
                gained_access=AccessLevel.USER
            ),
            AttackStep(
                step_id="network_discovery",
                name="Network and System Discovery",
                technique_id="T1018",
                description="Enumerate network for high-value targets",
                required_access=AccessLevel.USER,
                commands=["ping -t 10.1.1.1-254", "nslookup -type=any"],
                success_probability=0.95,
                detection_probability=0.3,
                estimated_time=timedelta(minutes=45)
            ),
            AttackStep(
                step_id="lateral_spread",
                name="Lateral Movement to File Servers",
                technique_id="T1021.002",
                description="Spread to file servers for maximum impact",
                required_access=AccessLevel.USER,
                commands=["wmic /node:fileserver process call create ransomware.exe"],
                success_probability=0.7,
                detection_probability=0.6,
                estimated_time=timedelta(hours=1)
            ),
            AttackStep(
                step_id="data_encryption",
                name="Data Encryption for Impact",
                technique_id="T1486",
                description="Encrypt critical business data",
                required_access=AccessLevel.USER,
                commands=["ransomware.exe --encrypt --targets=*.doc,*.xls,*.pdf"],
                success_probability=0.9,
                detection_probability=0.8,
                estimated_time=timedelta(hours=2),
                data_accessed=["customer_database", "financial_records", "backup_files"]
            )
        ]
    )
}


def get_scenario(scenario_id: str) -> Optional[AttackScenario]:
    """Get attack scenario by ID."""
    return ATTACK_SCENARIOS.get(scenario_id)


def list_scenarios() -> List[AttackScenario]:
    """List all available attack scenarios."""
    return list(ATTACK_SCENARIOS.values())


def get_scenarios_by_complexity(complexity: ComplexityLevel) -> List[AttackScenario]:
    """Get scenarios filtered by complexity level."""
    return [s for s in ATTACK_SCENARIOS.values() if s.complexity == complexity]


def get_scenarios_by_target(target_type: str) -> List[AttackScenario]:
    """Get scenarios that target specific system types."""
    return [s for s in ATTACK_SCENARIOS.values() if target_type in s.target_types]