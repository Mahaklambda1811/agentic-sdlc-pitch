#!/usr/bin/env python3
"""
Stage 1 — KaneAI Verification.
Parses requirements/*.txt, builds acceptance criteria, runs kane-cli
to verify each criterion against the live site, writes analyzed_requirements.json.
Kane's --code-export output is captured and stored as kane_code per AC.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

TARGET_URL = os.environ.get("TARGET_URL", "https://ecommerce-playground.lambdatest.io/")
RUN_NUMBER = os.environ.get("GITHUB_RUN_NUMBER", "local")

# Pre-seeded demo results for DEMO_MODE — no live Kane calls needed
_DEMO_RESULTS = [
    {"id": "AC-001", "description": "User can add a product to the cart from the product detail page and see the cart count update immediately.", "kane_status": "passed", "kane_one_liner": "Add to cart updates counter instantly", "kane_steps": ["Navigate to product page", "Click Add to Cart", "Assert cart count increments"], "kane_summary": "Cart count updates on product add", "kane_code": ""},
    {"id": "AC-002", "description": "User can open the cart dropdown and see all added items with their names and prices.", "kane_status": "passed", "kane_one_liner": "Cart dropdown shows item names and prices", "kane_steps": ["Add product to cart", "Click cart icon", "Assert items listed with names and prices"], "kane_summary": "Cart dropdown renders item details", "kane_code": ""},
    {"id": "AC-003", "description": "User can remove an item from the cart and the cart total updates correctly.", "kane_status": "passed", "kane_one_liner": "Remove item recalculates cart total", "kane_steps": ["Add item to cart", "Open cart", "Click remove", "Assert total updates"], "kane_summary": "Item removal triggers total recalculation", "kane_code": ""},
    {"id": "AC-004", "description": "User can search for a product by name and see relevant results on the search results page.", "kane_status": "passed", "kane_one_liner": "Search returns relevant product results", "kane_steps": ["Type product name in search bar", "Press Enter", "Assert result tiles visible"], "kane_summary": "Search yields matching products", "kane_code": ""},
    {"id": "AC-005", "description": "User can browse the product catalog and see product tiles with names and prices.", "kane_status": "passed", "kane_one_liner": "Catalog displays product tiles with pricing", "kane_steps": ["Open category page", "Assert product tiles with names and prices visible"], "kane_summary": "Product catalog renders tiles", "kane_code": ""},
    {"id": "AC-006", "description": "User can click a product tile to open the product detail page showing name, image, and price.", "kane_status": "passed", "kane_one_liner": "Product tile opens detail page with name, image, price", "kane_steps": ["Click product tile", "Assert detail page shows name, image, price"], "kane_summary": "Product detail page renders fully", "kane_code": ""},
    {"id": "AC-007", "description": "User can apply a category filter to narrow down the displayed products.", "kane_status": "passed", "kane_one_liner": "Category filter narrows product list", "kane_steps": ["Open category", "Click filter", "Assert product count changes"], "kane_summary": "Filter narrows product listing", "kane_code": ""},
    {"id": "AC-008", "description": "User sees a success message after adding a product to the cart.", "kane_status": "passed", "kane_one_liner": "Success message appears on cart add", "kane_steps": ["Navigate to product page", "Click Add to Cart", "Assert success notification visible"], "kane_summary": "Cart add triggers success message", "kane_code": ""},
]


def extract_acceptance_criteria(text: str) -> list[str]:
    """Extract AC lines from a requirements text file."""
    criteria = []
    for line in text.splitlines():
        line = line.strip()
        if re.match(r"AC-\d+:", line):
            criteria.append(line)
    return criteria


def parse_all_requirements() -> list[dict]:
    """Parse all *.txt files in requirements/ and return structured AC list."""
    results = []
    req_files = sorted(Path("requirements").glob("*.txt"))
    for req_file in req_files:
        text = req_file.read_text(encoding="utf-8")
        for ac_line in extract_acceptance_criteria(text):
            m = re.match(r"(AC-\d+):\s*(.+)", ac_line)
            if m:
                results.append({"id": m.group(1), "description": m.group(2).strip()})
    return results


def _read_kane_export(session_dir: str) -> str:
    """Extract Playwright test body lines from Kane's code-export directory."""
    if not session_dir:
        return ""
    code_dir = Path(session_dir).expanduser() / "code-export"
    if not code_dir.exists():
        return ""
    py_files = sorted(code_dir.glob("*.py"))
    if not py_files:
        return ""
    try:
        code = py_files[0].read_text(encoding="utf-8")
    except Exception:
        return ""
    skip_prefixes = (
        "import ", "from ", "with sync_playwright", "playwright =",
        "browser =", "context =", "page =", "browser.close", "context.close",
        "async with", "asyncio.", "if __name__",
    )
    body_lines = []
    in_body = False
    for line in code.splitlines():
        stripped = line.strip()
        if stripped.startswith("def ") or stripped.startswith("async def "):
            in_body = True
            continue
        if not in_body or not stripped or stripped.startswith("#"):
            continue
        if any(stripped.startswith(p) for p in skip_prefixes):
            continue
        clean = stripped.replace("await ", "")
        if clean.startswith("page.") or clean.startswith("assert ") or clean.startswith("expect("):
            body_lines.append("    " + clean)
    return "\n".join(body_lines)


def run_kane_verification(ac: dict) -> dict:
    """Run kane-cli for one acceptance criterion and return result dict."""
    objective = (
        f"Go to {TARGET_URL}, verify: {ac['description']} "
        f"Assert the behaviour is observable. Pass if yes, fail if not."
    )
    print(f"  [kane] {ac['id']}: {objective[:80]}...")
    try:
        result = subprocess.run(
            ["kane-cli", "run", objective, "--agent", "--headless",
             "--timeout", "180", "--max-steps", "30", "--code-export"],
            capture_output=True, text=True, timeout=210
        )
        status = "failed"
        one_liner = ""
        steps = []
        session_dir = ""
        combined_output = result.stdout + result.stderr
        for line in combined_output.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                if event.get("type") == "run_end":
                    status = event.get("status", "failed")
                    one_liner = event.get("one_liner", event.get("summary", ""))[:80]
                    session_dir = event.get("session_dir", "")
                elif "step" in event and "remark" in event:
                    steps.append(event.get("remark", ""))
            except json.JSONDecodeError:
                pass
        if result.returncode == 0 and status == "failed":
            status = "passed"
        kane_code = _read_kane_export(session_dir)
        if kane_code:
            print(f"  [kane] {ac['id']} — code export captured ({len(kane_code)} chars)")
        return {**ac, "kane_status": status, "kane_one_liner": one_liner,
                "kane_steps": steps, "kane_summary": one_liner, "kane_code": kane_code}
    except subprocess.TimeoutExpired:
        print(f"  [kane] TIMEOUT for {ac['id']}")
        return {**ac, "kane_status": "failed", "kane_one_liner": "Timeout",
                "kane_steps": [], "kane_summary": "Timeout", "kane_code": ""}
    except FileNotFoundError:
        print(f"  [kane] kane-cli not found — marking {ac['id']} as failed")
        return {**ac, "kane_status": "failed", "kane_one_liner": "kane-cli not installed",
                "kane_steps": [], "kane_summary": "", "kane_code": ""}


def main() -> None:
    import concurrent.futures

    parser = argparse.ArgumentParser()
    parser.add_argument("--demo-mode", action="store_true", help="Use pre-seeded results")
    parser.add_argument("--requirements", default="requirements", help="Requirements directory")
    args = parser.parse_args()

    Path("requirements").mkdir(exist_ok=True)
    out_path = Path("requirements/analyzed_requirements.json")

    if args.demo_mode:
        print("[analyze] DEMO MODE — writing pre-seeded Kane results")
        out_path.write_text(json.dumps(_DEMO_RESULTS, indent=2), encoding="utf-8")
        print(f"[analyze] wrote {len(_DEMO_RESULTS)} requirements")
        return

    all_acs = parse_all_requirements()
    if not all_acs:
        print("ERROR: no acceptance criteria found in requirements/*.txt", file=sys.stderr)
        sys.exit(1)

    print(f"[analyze] {len(all_acs)} ACs found — running KaneAI verification in parallel")
    results_map: dict[str, dict] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(run_kane_verification, ac): ac["id"] for ac in all_acs}
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results_map[result["id"]] = result
            print(f"  {result['id']} → {result['kane_status']}")

    results = [results_map[ac["id"]] for ac in all_acs]
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    passed = sum(1 for r in results if r["kane_status"] == "passed")
    print(f"\n[analyze] complete: {passed}/{len(results)} passed → {out_path}")


if __name__ == "__main__":
    main()
