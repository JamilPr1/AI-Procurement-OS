"""Base agent runtime with retry and JSON repair."""

from __future__ import annotations

import json
from typing import Any

from src.core.brain import AgentDefinition
from src.core.llm import LLMClient
from src.core.logger import PlatformLogger


class BaseAgent:
    def __init__(self, definition: AgentDefinition, llm: LLMClient, logger: PlatformLogger) -> None:
        self.definition = definition
        self.llm = llm
        self.logger = logger

    def run(self, user_input: str) -> dict[str, Any]:
        system_prompt = self.definition.prompt_text
        if not system_prompt:
            return {
                "status": "error",
                "agent_id": self.definition.id,
                "error": f"No prompt loaded for agent: {self.definition.id}",
            }

        last_error = ""
        for attempt in range(2):
            try:
                prompt = system_prompt
                message = user_input
                if attempt == 1:
                    message = (
                        user_input
                        + "\n\nIMPORTANT: Respond with a single valid JSON object only. "
                        "No markdown, no code fences, no explanation."
                    )
                output, duration_ms = self.llm.complete_json(prompt, message)
                self.logger.agent_run(
                    self.definition.id,
                    input_summary={"preview": user_input[:200]},
                    output_summary={"keys": list(output.keys()) if isinstance(output, dict) else []},
                    duration_ms=duration_ms,
                    model=self.llm.model,
                    status="success",
                )
                return {
                    "status": "success",
                    "agent_id": self.definition.id,
                    "agent_name": self.definition.name,
                    "output": output,
                    "duration_ms": duration_ms,
                }
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                last_error = f"JSON parse error: {e}"
            except Exception as e:
                last_error = str(e)

        self.logger.agent_run(
            self.definition.id,
            input_summary={"preview": user_input[:200]},
            status="error",
        )
        self.logger.error(f"Agent {self.definition.id} failed", error=last_error)
        return {
            "status": "error",
            "agent_id": self.definition.id,
            "error": last_error,
        }
