from __future__ import annotations

from uuid import uuid4

from features.services.types import (
    EvidenceGraphEdge,
    EvidenceGraphNode,
    EvidenceGraphSnapshot,
    IncidentAnalysis,
    utc_now_iso,
)


class IncidentEvidenceGraphService:
    def build(self, incident: IncidentAnalysis) -> EvidenceGraphSnapshot:
        nodes: list[EvidenceGraphNode] = []
        edges: list[EvidenceGraphEdge] = []
        incident_node_id = f"incident:{incident.incident_id}"
        nodes.append(
            EvidenceGraphNode(
                node_id=incident_node_id,
                node_type="incident",
                label=incident.incident_id,
                payload={
                    "incident_type": incident.incident_type,
                    "evidence_score": incident.case_report.checklist.score,
                    "status": incident.case_report.checklist.status.value,
                },
            )
        )
        self._add_actor(nodes, edges, incident, incident_node_id, "employee", incident.employee_code)
        self._add_actor(nodes, edges, incident, incident_node_id, "role", incident.role_code)
        self._add_actor(nodes, edges, incident, incident_node_id, "team", incident.team_code)
        self._add_actor(nodes, edges, incident, incident_node_id, "station", incident.station_code)
        self._add_root_cause(nodes, edges, incident, incident_node_id)
        self._add_evidence(nodes, edges, incident, incident_node_id)
        self._add_issues_and_skills(nodes, edges, incident, incident_node_id)
        return EvidenceGraphSnapshot(
            incident_id=incident.incident_id,
            created_at=utc_now_iso(),
            nodes=nodes,
            edges=edges,
        )

    def _add_actor(
        self,
        nodes: list[EvidenceGraphNode],
        edges: list[EvidenceGraphEdge],
        incident: IncidentAnalysis,
        incident_node_id: str,
        actor_type: str,
        actor_code: str | None,
    ) -> None:
        if not actor_code:
            return
        node_id = f"{actor_type}:{actor_code}"
        nodes.append(EvidenceGraphNode(node_id=node_id, node_type=actor_type, label=actor_code))
        edges.append(self._edge(incident.incident_id, node_id, incident_node_id, "involved_in"))

    def _add_root_cause(
        self,
        nodes: list[EvidenceGraphNode],
        edges: list[EvidenceGraphEdge],
        incident: IncidentAnalysis,
        incident_node_id: str,
    ) -> None:
        root_cause = incident.case_report.document.root_cause
        node_id = f"root_cause:{incident.incident_id}"
        nodes.append(
            EvidenceGraphNode(
                node_id=node_id,
                node_type="root_cause",
                label=root_cause or "root_cause_missing",
                payload={"present": bool(root_cause)},
            )
        )
        edges.append(self._edge(incident.incident_id, incident_node_id, node_id, "has_root_cause_signal"))

    def _add_evidence(
        self,
        nodes: list[EvidenceGraphNode],
        edges: list[EvidenceGraphEdge],
        incident: IncidentAnalysis,
        incident_node_id: str,
    ) -> None:
        for finding in incident.case_report.vision:
            node_id = f"evidence:{incident.incident_id}:{finding.filename}:{finding.evidence_role}"
            nodes.append(
                EvidenceGraphNode(
                    node_id=node_id,
                    node_type="evidence",
                    label=finding.filename,
                    payload={
                        "evidence_role": finding.evidence_role,
                        "confidence": finding.confidence,
                        "missing_items": finding.missing_items,
                        "observed_items": finding.observed_items,
                    },
                )
            )
            edges.append(self._edge(incident.incident_id, incident_node_id, node_id, "has_evidence"))

    def _add_issues_and_skills(
        self,
        nodes: list[EvidenceGraphNode],
        edges: list[EvidenceGraphEdge],
        incident: IncidentAnalysis,
        incident_node_id: str,
    ) -> None:
        skill_by_issue = {gap.source_issue_code: gap for gap in incident.skill_gaps}
        for issue in incident.case_report.checklist.issues:
            issue_node_id = f"issue:{incident.incident_id}:{issue.code}"
            nodes.append(
                EvidenceGraphNode(
                    node_id=issue_node_id,
                    node_type="issue",
                    label=issue.code,
                    payload={
                        "severity": issue.severity,
                        "title": issue.title,
                        "detail": issue.detail,
                    },
                )
            )
            edges.append(self._edge(incident.incident_id, incident_node_id, issue_node_id, "has_issue"))
            gap = skill_by_issue.get(issue.code)
            if gap:
                skill_node_id = f"skill:{gap.skill_id}"
                if not any(node.node_id == skill_node_id for node in nodes):
                    nodes.append(
                        EvidenceGraphNode(
                            node_id=skill_node_id,
                            node_type="skill",
                            label=gap.title,
                            payload={"skill_id": gap.skill_id, "severity": gap.severity},
                        )
                    )
                edges.append(self._edge(incident.incident_id, issue_node_id, skill_node_id, "maps_to_skill"))

    def _edge(
        self,
        incident_id: str,
        source_node_id: str,
        target_node_id: str,
        relation_type: str,
    ) -> EvidenceGraphEdge:
        return EvidenceGraphEdge(
            edge_id=f"edge_{uuid4().hex[:12]}",
            incident_id=incident_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            relation_type=relation_type,
        )
