#!/usr/bin/env python3
"""
Structured logging for the agentic SDLC pipeline.

Usage:
    from pipeline_logger import get_logger
    log = get_logger("flow1")
    log.info("Phase 1 started")
    log.success("SC-001 passed")
    log.failure("SC-003 failed", detail="stderr output here")
"""
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

LOGS_DIR = Path(__file__).parent.parent / "logs"


class PipelineLogger:
    def __init__(self, name: str):
        LOGS_DIR.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = LOGS_DIR / f"{name}_{ts}.log"

        self._logger = logging.getLogger(name)
        self._logger.setLevel(logging.DEBUG)
        self._logger.handlers = []

        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")

        # Console
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(fmt)
        self._logger.addHandler(ch)

        # File
        fh = logging.FileHandler(log_file)
        fh.setFormatter(fmt)
        self._logger.addHandler(fh)

        self._log_file = log_file
        self._events: list[dict] = []

        self.info(f"Log file: {log_file}")

    # ── Convenience wrappers ──────────────────────────────────────────────────

    def info(self, msg: str):
        self._logger.info(msg)
        self._record("info", msg)

    def warning(self, msg: str):
        self._logger.warning(msg)
        self._record("warning", msg)

    def error(self, msg: str):
        self._logger.error(msg)
        self._record("error", msg)

    def success(self, sc_id: str, msg: str = ""):
        full = f"[{sc_id}] PASSED {msg}".strip()
        self._logger.info(full)
        self._record("success", full, sc_id=sc_id)

    def failure(self, sc_id: str, msg: str = "", detail: str = ""):
        full = f"[{sc_id}] FAILED {msg}".strip()
        self._logger.error(full)
        if detail:
            self._logger.debug(f"[{sc_id}] detail: {detail[:300]}")
        self._record("failure", full, sc_id=sc_id, detail=detail)

    def phase(self, name: str):
        self._logger.info("=" * 60)
        self._logger.info(f"  {name}")
        self._logger.info("=" * 60)
        self._record("phase", name)

    # ── Event store (for run_history) ─────────────────────────────────────────

    def _record(self, kind: str, msg: str, **kw):
        self._events.append({
            "ts": datetime.now().isoformat(),
            "kind": kind,
            "msg": msg,
            **kw,
        })

    def events(self) -> list[dict]:
        return self._events


def get_logger(name: str) -> PipelineLogger:
    return PipelineLogger(name)
