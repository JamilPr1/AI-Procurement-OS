"""Structured logging with change audit trail."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": _utc_now(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra_data") and record.extra_data:
            payload["data"] = record.extra_data
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class PlatformLogger:
    """Central logger: console + JSON files under logs/."""

    def __init__(self, project_root: Path, config: dict[str, Any]) -> None:
        self.project_root = project_root
        self.config = config.get("logging", {})
        self.logs_dir = project_root / config.get("paths", {}).get("logs", "logs")
        self.level = getattr(logging, self.config.get("level", "INFO"))

        self.logs_dir.mkdir(parents=True, exist_ok=True)
        (self.logs_dir / "changes").mkdir(exist_ok=True)
        (self.logs_dir / "agents").mkdir(exist_ok=True)
        (self.logs_dir / "system").mkdir(exist_ok=True)

        self._system_logger = self._build_logger("system", self.logs_dir / "system" / "platform.log")
        self._agent_logger = self._build_logger("agents", self.logs_dir / "agents" / "agents.log")
        self._change_logger = self._build_logger("changes", self.logs_dir / "changes" / "changes.log")

    def _build_logger(self, name: str, log_file: Path) -> logging.Logger:
        logger = logging.getLogger(f"platform.{name}")
        logger.setLevel(self.level)
        logger.handlers.clear()
        logger.propagate = False

        if self.config.get("json_files", True):
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setFormatter(JsonLineFormatter())
            logger.addHandler(fh)

        if self.config.get("console", True) and name == "system":
            ch = logging.StreamHandler(sys.stdout)
            ch.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
            )
            logger.addHandler(ch)

        return logger

    def _log(self, logger: logging.Logger, level: int, message: str, data: dict | None = None) -> None:
        record = logger.makeRecord(logger.name, level, "", 0, message, (), None)
        record.extra_data = data or {}
        logger.handle(record)

    def info(self, message: str, **data: Any) -> None:
        self._log(self._system_logger, logging.INFO, message, data)

    def warning(self, message: str, **data: Any) -> None:
        self._log(self._system_logger, logging.WARNING, message, data)

    def error(self, message: str, **data: Any) -> None:
        self._log(self._system_logger, logging.ERROR, message, data)

    def agent_run(
        self,
        agent_id: str,
        *,
        input_summary: dict | None = None,
        output_summary: dict | None = None,
        duration_ms: int | None = None,
        model: str | None = None,
        status: str = "success",
    ) -> None:
        self._log(
            self._agent_logger,
            logging.INFO,
            f"Agent run: {agent_id}",
            {
                "agent_id": agent_id,
                "status": status,
                "input_summary": input_summary,
                "output_summary": output_summary,
                "duration_ms": duration_ms,
                "model": model,
            },
        )

    def change(
        self,
        entity_type: str,
        entity_id: str,
        action: str,
        *,
        before: dict | None = None,
        after: dict | None = None,
        actor: str = "system",
        reason: str | None = None,
    ) -> None:
        """Record entity changes for audit and future debugging."""
        self._log(
            self._change_logger,
            logging.INFO,
            f"{action} {entity_type}:{entity_id}",
            {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "action": action,
                "before": before,
                "after": after,
                "actor": actor,
                "reason": reason,
            },
        )
