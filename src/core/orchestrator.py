"""Workflow orchestrator — runs agents through pipeline stages."""

from __future__ import annotations

import time
from typing import Any

from src.agents.base import BaseAgent
from src.agents.fallbacks import run_fallback
from src.core.brain import Brain, WorkflowStage
from src.core.llm import LLMClient
from src.core.logger import PlatformLogger
from src.core.storage import Storage


class Orchestrator:
    def __init__(
        self,
        brain: Brain,
        llm: LLMClient,
        storage: Storage,
        logger: PlatformLogger,
    ) -> None:
        self.brain = brain
        self.llm = llm
        self.storage = storage
        self.logger = logger
        self.tenant_id = brain.config.get("agency", {}).get("tenant_id", "agency_primary")

    def list_pipeline(self, workflow_name: str = "buyer_to_delivery") -> list[dict[str, Any]]:
        wf = self.brain.get_workflow(workflow_name)
        return [
            {
                "stage": s.id,
                "agent": s.agent,
                "human_gate": s.human_gate,
                "next": s.next,
            }
            for s in wf.stages
        ]

    def run_agent(self, agent_id: str, user_input: str, *, entity_type: str | None = None, entity_id: str | None = None) -> dict[str, Any]:
        pipeline_cfg = self.brain.config.get("pipeline", {})
        fast_mode = pipeline_cfg.get("fast_mode", True)
        use_llm_for: list[str] = pipeline_cfg.get("use_llm_for", [])
        use_llm = (not fast_mode) or (agent_id in use_llm_for)

        result: dict[str, Any] | None = None
        if use_llm:
            agent_def = self.brain.get_agent(agent_id)
            agent = BaseAgent(agent_def, self.llm, self.logger)
            result = agent.run(user_input)
            if result.get("status") == "success":
                self._log_run(agent_id, user_input, result, entity_type, entity_id)
                return result

        start = time.perf_counter()
        output = run_fallback(agent_id, user_input)
        duration_ms = int((time.perf_counter() - start) * 1000)
        fallback_result: dict[str, Any] = {
            "status": "success",
            "agent_id": agent_id,
            "agent_name": self.brain.get_agent(agent_id).name,
            "output": output,
            "duration_ms": duration_ms,
            "source": output.get("source", "rule_based_fallback"),
            "model": "fallback",
        }
        if use_llm:
            fallback_result["llm_fallback"] = True
        self._log_run(agent_id, user_input, fallback_result, entity_type, entity_id)
        return fallback_result

    def _log_run(
        self,
        agent_id: str,
        user_input: str,
        result: dict[str, Any],
        entity_type: str | None,
        entity_id: str | None,
    ) -> None:
        self.storage.log_agent_run(
            agent_id,
            tenant_id=self.tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            input_data={"user_input": user_input[:500]},
            output_data=result.get("output"),
            status=result.get("status", "success"),
            duration_ms=result.get("duration_ms"),
            model=result.get("model") or self.llm.model,
        )

    def check_human_gate(self, gate_name: str) -> dict[str, Any]:
        gates = self.brain.policies.get("human_gate", {}).get("gates", {})
        gate = gates.get(gate_name)
        if not gate:
            return {"required": False, "gate": gate_name}
        return {
            "required": True,
            "gate": gate_name,
            "description": gate.get("description"),
            "required_role": gate.get("required_role"),
        }
