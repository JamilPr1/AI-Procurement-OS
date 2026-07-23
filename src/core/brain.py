"""Brain loader — single source of truth for config, agents, workflows, policies."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class AgentDefinition:
    id: str
    name: str
    stage: int
    description: str
    raw: dict[str, Any] = field(default_factory=dict)
    prompt_text: str = ""

    @property
    def prompt_path(self) -> str | None:
        return self.raw.get("prompt")


@dataclass
class WorkflowStage:
    id: str
    agent: str
    input: str | None
    output: str
    next: str | None
    human_gate: str | None = None
    trigger: str | None = None
    parallel: bool = False


@dataclass
class Workflow:
    name: str
    version: str
    description: str
    stages: list[WorkflowStage]


class Brain:
    """Loads and exposes all project intelligence from brain/."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.brain_dir = project_root / "brain"
        self.config: dict[str, Any] = {}
        self.agents: dict[str, AgentDefinition] = {}
        self.workflows: dict[str, Workflow] = {}
        self.policies: dict[str, Any] = {}

    def load(self) -> None:
        self.config = self._load_yaml(self.brain_dir / "config.yaml")
        self._load_agents()
        self._load_workflows()
        self._load_policies()

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"Brain file missing: {path}")
        with path.open(encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _load_agents(self) -> None:
        agents_dir = self.brain_dir / "agents"
        for path in sorted(agents_dir.glob("*.yaml")):
            raw = self._load_yaml(path)
            agent_id = raw.get("id", path.stem)
            prompt_text = ""
            prompt_ref = raw.get("prompt")
            if prompt_ref:
                prompt_path = self.brain_dir / prompt_ref
                if prompt_path.exists():
                    prompt_text = prompt_path.read_text(encoding="utf-8")

            self.agents[agent_id] = AgentDefinition(
                id=agent_id,
                name=raw.get("name", agent_id),
                stage=raw.get("stage", 0),
                description=raw.get("description", ""),
                raw=raw,
                prompt_text=prompt_text,
            )

    def _load_workflows(self) -> None:
        workflows_dir = self.brain_dir / "workflows"
        for path in sorted(workflows_dir.glob("*.yaml")):
            raw = self._load_yaml(path)
            stages = [
                WorkflowStage(
                    id=s["id"],
                    agent=s["agent"],
                    input=s.get("input"),
                    output=s.get("output", ""),
                    next=s.get("next"),
                    human_gate=s.get("human_gate"),
                    trigger=s.get("trigger"),
                    parallel=s.get("parallel", False),
                )
                for s in raw.get("stages", [])
            ]
            wf = Workflow(
                name=raw.get("name", path.stem),
                version=raw.get("version", "1.0"),
                description=raw.get("description", ""),
                stages=stages,
            )
            self.workflows[wf.name] = wf

    def _load_policies(self) -> None:
        policies_dir = self.brain_dir / "policies"
        for path in sorted(policies_dir.glob("*.yaml")):
            self.policies[path.stem] = self._load_yaml(path)

    def get_agent(self, agent_id: str) -> AgentDefinition:
        if agent_id not in self.agents:
            raise KeyError(f"Unknown agent: {agent_id}")
        return self.agents[agent_id]

    def get_workflow(self, name: str) -> Workflow:
        if name not in self.workflows:
            raise KeyError(f"Unknown workflow: {name}")
        return self.workflows[name]

    def requires_human_gate(self, gate_name: str) -> bool:
        gates = self.policies.get("human_gate", {}).get("gates", {})
        return gate_name in gates

    def data_dir(self) -> Path:
        rel = self.config.get("paths", {}).get("data", "data")
        path = self.project_root / rel
        path.mkdir(parents=True, exist_ok=True)
        return path

    def db_path(self) -> Path:
        rel = self.config.get("paths", {}).get("database", "data/platform.db")
        path = self.project_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def summary(self) -> dict[str, Any]:
        return {
            "project": self.config.get("project", {}),
            "vertical": self.config.get("vertical", {}).get("display_name"),
            "agents_loaded": len(self.agents),
            "workflows_loaded": len(self.workflows),
            "policies_loaded": len(self.policies),
            "llm": {
                "provider": self.config.get("llm", {}).get("provider"),
                "model": self.config.get("llm", {}).get("model"),
            },
            "agency": self.config.get("agency", {}).get("name"),
            "saas_enabled": self.config.get("saas", {}).get("enabled", False),
        }
