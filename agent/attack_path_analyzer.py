"""
Graph-based attack path analysis using Neo4j.
Finds viable attack paths and assesses vulnerability exposure.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel

from .attack_scenarios import AttackScenario, AccessLevel
from .mcp_integration import Neo4jMCPClient, MCPGraphOperations


class AttackPath(BaseModel):
    """Represents a potential attack path through the network."""
    path_id: str
    source_host: str
    target_host: str
    intermediate_hosts: List[str]
    path_length: int
    estimated_time: float  # hours
    stealth_score: float   # 0.0 - 1.0
    success_probability: float  # 0.0 - 1.0
    required_access: AccessLevel
    vulnerabilities: List[str]


class VulnerabilityAssessment(BaseModel):
    """Assessment of vulnerabilities along an attack path."""
    path: AttackPath
    network_exposures: List[Dict[str, Any]]
    service_vulnerabilities: List[Dict[str, Any]]
    credential_requirements: List[str]
    detection_points: List[Dict[str, Any]]
    risk_score: float  # 0.0 - 10.0


class AttackPathAnalyzer:
    """Analyzes graph topology to find realistic attack paths."""

    def __init__(self, mcp_client: Neo4jMCPClient):
        self.mcp_client = mcp_client
        self.mcp_ops = MCPGraphOperations(mcp_client)

    async def find_attack_paths(
        self,
        source: str,
        target: str,
        scenario: AttackScenario,
        max_hops: int = 5
    ) -> List[AttackPath]:
        """Find all viable attack paths from source to target."""

        # Query for all paths between source and target
        query = """
        MATCH path = (source:Host {id: $source_id})-[*1..$max_hops]-(target:Host {id: $target_id})
        WHERE source <> target
        AND ALL(r IN relationships(path) WHERE
            r.type IN ['allowed_tcp', 'allowed_udp', 'admin_access', 'domain_trust', 'kerberos', 'replication']
        )
        RETURN path,
               length(path) as hops,
               [n IN nodes(path) | n.id] as node_ids,
               [r IN relationships(path) | {type: r.type, port: r.port}] as relationships
        ORDER BY hops ASC
        LIMIT 20
        """

        result = await self.mcp_ops.run_cypher(query, {
            "source_id": source,
            "target_id": target,
            "max_hops": max_hops
        })

        paths = []
        for record in result.get("records", []):
            path_data = record
            node_ids = path_data.get("node_ids", [])
            hops = path_data.get("hops", 0)

            if len(node_ids) >= 2:
                attack_path = await self._create_attack_path(
                    source=node_ids[0],
                    target=node_ids[-1],
                    intermediate=node_ids[1:-1],
                    hops=hops,
                    scenario=scenario
                )
                paths.append(attack_path)

        return paths

    async def _create_attack_path(
        self,
        source: str,
        target: str,
        intermediate: List[str],
        hops: int,
        scenario: AttackScenario
    ) -> AttackPath:
        """Create AttackPath object with calculated metrics."""

        # Calculate estimated time (base time + complexity factor)
        base_time = 0.5  # 30 minutes base
        complexity_factor = hops * 0.3  # 18 minutes per hop
        estimated_time = base_time + complexity_factor

        # Calculate stealth score (decreases with path length)
        stealth_score = max(0.1, 1.0 - (hops * 0.15))

        # Calculate success probability (decreases with complexity)
        success_probability = max(0.2, 0.9 - (hops * 0.1))

        # Determine required access level
        required_access = AccessLevel.USER
        if "domain-controller" in target or "critical" in target.lower():
            required_access = AccessLevel.ADMIN

        return AttackPath(
            path_id=f"{source}_{target}_{hops}",
            source_host=source,
            target_host=target,
            intermediate_hosts=intermediate,
            path_length=hops,
            estimated_time=estimated_time,
            stealth_score=stealth_score,
            success_probability=success_probability,
            required_access=required_access,
            vulnerabilities=[]
        )

    async def analyze_vulnerabilities(self, path: AttackPath) -> VulnerabilityAssessment:
        """Assess vulnerabilities and exposures along an attack path."""

        # Analyze network exposures
        network_exposures = await self._analyze_network_exposures(path)

        # Find service vulnerabilities
        service_vulnerabilities = await self._analyze_service_vulnerabilities(path)

        # Determine credential requirements
        credential_requirements = await self._analyze_credential_requirements(path)

        # Identify detection points
        detection_points = await self._analyze_detection_points(path)

        # Calculate overall risk score
        risk_score = self._calculate_risk_score(
            network_exposures, service_vulnerabilities, detection_points
        )

        return VulnerabilityAssessment(
            path=path,
            network_exposures=network_exposures,
            service_vulnerabilities=service_vulnerabilities,
            credential_requirements=credential_requirements,
            detection_points=detection_points,
            risk_score=risk_score
        )

    async def _analyze_network_exposures(self, path: AttackPath) -> List[Dict[str, Any]]:
        """Analyze network connectivity and exposed services."""

        all_hosts = [path.source_host] + path.intermediate_hosts + [path.target_host]
        exposures = []

        for i in range(len(all_hosts) - 1):
            source_host = all_hosts[i]
            target_host = all_hosts[i + 1]

            # Query for network connections between consecutive hosts
            query = """
            MATCH (source:Host {id: $source_id})-[r:allowed_tcp|allowed_udp]-(target:Host {id: $target_id})
            RETURN r.type as connection_type,
                   r.port as port,
                   r.proto as protocol,
                   source.ip as source_ip,
                   target.ip as target_ip
            """

            result = await self.mcp_ops.run_cypher(query, {
                "source_id": source_host,
                "target_id": target_host
            })

            for record in result.get("records", []):
                exposures.append({
                    "source": source_host,
                    "target": target_host,
                    "type": "network_exposure",
                    "port": record.get("port"),
                    "protocol": record.get("protocol"),
                    "source_ip": record.get("source_ip"),
                    "target_ip": record.get("target_ip"),
                    "risk_level": self._assess_port_risk(record.get("port"))
                })

        return exposures

    async def _analyze_service_vulnerabilities(self, path: AttackPath) -> List[Dict[str, Any]]:
        """Analyze service-specific vulnerabilities."""

        vulnerabilities = []
        all_hosts = [path.source_host] + path.intermediate_hosts + [path.target_host]

        for host in all_hosts:
            # Get host information
            query = """
            MATCH (h:Host {id: $host_id})
            RETURN h.role as role,
                   h.labels as labels,
                   h.ip as ip,
                   h.attrs as attributes
            """

            result = await self.mcp_ops.run_cypher(query, {"host_id": host})

            for record in result.get("records", []):
                role = record.get("role", "")
                labels = record.get("labels", [])

                # Common Windows vulnerabilities
                if "Windows" in labels:
                    vulnerabilities.append({
                        "host": host,
                        "type": "os_vulnerability",
                        "description": "Windows SMB vulnerabilities (EternalBlue family)",
                        "severity": "HIGH",
                        "cve": ["CVE-2017-0144", "CVE-2017-0145"],
                        "exploitable_services": ["SMB", "NetBIOS"]
                    })

                # Domain controller specific vulnerabilities
                if role == "domain-controller":
                    vulnerabilities.append({
                        "host": host,
                        "type": "service_vulnerability",
                        "description": "Active Directory privilege escalation",
                        "severity": "CRITICAL",
                        "attack_vector": "Kerberoasting, DCSync",
                        "impact": "Domain compromise"
                    })

                # File server vulnerabilities
                if role == "fileserver":
                    vulnerabilities.append({
                        "host": host,
                        "type": "data_exposure",
                        "description": "Sensitive file access via SMB shares",
                        "severity": "MEDIUM",
                        "attack_vector": "Share enumeration, credential access",
                        "impact": "Data exfiltration"
                    })

        return vulnerabilities

    async def _analyze_credential_requirements(self, path: AttackPath) -> List[str]:
        """Determine credential requirements for the attack path."""

        requirements = []
        all_hosts = [path.source_host] + path.intermediate_hosts + [path.target_host]

        for host in all_hosts:
            query = """
            MATCH (h:Host {id: $host_id})
            RETURN h.role as role, h.labels as labels
            """

            result = await self.mcp_ops.run_cypher(query, {"host_id": host})

            for record in result.get("records", []):
                role = record.get("role", "")
                labels = record.get("labels", [])

                if "Windows" in labels:
                    requirements.append(f"Domain credentials for {host}")

                if role == "domain-controller":
                    requirements.append(f"Administrative privileges for {host}")
                    requirements.append(f"Domain admin credentials")

                if "Critical" in labels:
                    requirements.append(f"Elevated access for critical system {host}")

        return list(set(requirements))  # Remove duplicates

    async def _analyze_detection_points(self, path: AttackPath) -> List[Dict[str, Any]]:
        """Identify potential detection points along the attack path."""

        detection_points = []
        all_hosts = [path.source_host] + path.intermediate_hosts + [path.target_host]

        for host in all_hosts:
            # High-value targets are more likely to be monitored
            query = """
            MATCH (h:Host {id: $host_id})
            RETURN h.role as role, h.labels as labels
            """

            result = await self.mcp_ops.run_cypher(query, {"host_id": host})

            for record in result.get("records", []):
                role = record.get("role", "")
                labels = record.get("labels", [])

                detection_likelihood = 0.3  # Base detection probability

                if "Critical" in labels:
                    detection_likelihood += 0.4

                if role in ["domain-controller", "fileserver"]:
                    detection_likelihood += 0.3

                if "Windows" in labels:
                    detection_likelihood += 0.1  # Windows logging

                detection_points.append({
                    "host": host,
                    "detection_type": "endpoint_monitoring",
                    "likelihood": min(1.0, detection_likelihood),
                    "monitoring_tools": ["Windows Event Log", "EDR", "SIEM"],
                    "indicators": ["Process creation", "Network connections", "File access"]
                })

        return detection_points

    def _assess_port_risk(self, port: Optional[int]) -> str:
        """Assess risk level based on exposed port."""
        if not port:
            return "LOW"

        high_risk_ports = {445, 139, 3389, 22, 23, 21, 80, 443}
        medium_risk_ports = {135, 1433, 3306, 5432, 6379}

        if port in high_risk_ports:
            return "HIGH"
        elif port in medium_risk_ports:
            return "MEDIUM"
        else:
            return "LOW"

    def _calculate_risk_score(
        self,
        network_exposures: List[Dict[str, Any]],
        service_vulnerabilities: List[Dict[str, Any]],
        detection_points: List[Dict[str, Any]]
    ) -> float:
        """Calculate overall risk score for the attack path."""

        # Base score
        risk_score = 0.0

        # Network exposure contribution (0-3 points)
        high_risk_exposures = sum(1 for exp in network_exposures if exp.get("risk_level") == "HIGH")
        risk_score += min(3.0, high_risk_exposures * 0.5)

        # Service vulnerability contribution (0-5 points)
        critical_vulns = sum(1 for vuln in service_vulnerabilities if vuln.get("severity") == "CRITICAL")
        high_vulns = sum(1 for vuln in service_vulnerabilities if vuln.get("severity") == "HIGH")
        risk_score += min(5.0, critical_vulns * 2.0 + high_vulns * 1.0)

        # Detection likelihood factor (0-2 points reduction)
        avg_detection = sum(dp.get("likelihood", 0) for dp in detection_points) / max(1, len(detection_points))
        risk_score += max(0, 2.0 - avg_detection * 2.0)

        return min(10.0, risk_score)

    async def get_high_value_targets(self) -> List[Dict[str, Any]]:
        """Identify high-value targets in the network."""

        query = """
        MATCH (h:Host)
        WHERE h.role IN ['domain-controller', 'fileserver', 'database', 'backup']
           OR 'Critical' IN h.labels
        RETURN h.id as host_id,
               h.role as role,
               h.labels as labels,
               h.name as name,
               h.ip as ip
        ORDER BY
            CASE h.role
                WHEN 'domain-controller' THEN 1
                WHEN 'database' THEN 2
                WHEN 'fileserver' THEN 3
                ELSE 4
            END
        """

        result = await self.mcp_ops.run_cypher(query)
        return result.get("records", [])

    async def get_potential_entry_points(self) -> List[Dict[str, Any]]:
        """Identify potential initial access points."""

        query = """
        MATCH (h:Host)
        WHERE h.role IN ['workstation', 'laptop', 'jump-server']
           OR h.ip LIKE '192.168.%'  // Assume internal network
           OR h.ip LIKE '10.%'
        OPTIONAL MATCH (h)-[r:allowed_tcp|allowed_udp]-()
        WHERE r.port IN [22, 23, 80, 443, 3389]  // Common entry points
        RETURN h.id as host_id,
               h.role as role,
               h.ip as ip,
               h.name as name,
               collect(DISTINCT r.port) as exposed_ports
        ORDER BY size(exposed_ports) DESC
        """

        result = await self.mcp_ops.run_cypher(query)
        return result.get("records", [])