#!/usr/bin/env python3
"""
HyperExecute pre-script: generates test_scenarios.py from scenarios.json.
Runs on each HE VM before test discovery.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from agent import generate_tests, _validate_syntax

sc_path = Path("scenarios/scenarios.json")
if not sc_path.exists():
    print(f"ERROR: {sc_path} not found", file=sys.stderr)
    sys.exit(1)

scenarios = json.loads(sc_path.read_text(encoding="utf-8"))
print(f"[he-pre] Loaded {len(scenarios)} scenarios from {sc_path}")

generate_tests(scenarios)
print("[he-pre] test_scenarios.py generated")

if not _validate_syntax("tests/playwright/test_scenarios.py"):
    print("ERROR: test_scenarios.py syntax invalid", file=sys.stderr)
    sys.exit(1)

print("[he-pre] Ready for test discovery")
