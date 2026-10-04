"""
Evaluation Harness Runner for VaaniFlow.

Executes test scenarios across prompt versions, stores transcripts and evaluations
in SQLite, and computes comparative performance benchmarks using Pandas and SQL.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from dotenv import load_dotenv

from src.agent import NehaAgent
from src.customer_sim import CustomerSimulator, run_call_simulation
from src.db import (
    DEFAULT_DB_PATH,
    init_db,
    query_dataframe,
    save_conversation,
    save_eval_score,
)
from src.evaluator import LLMJudgeEvaluator

load_dotenv()


def run_benchmark(
    prompt_configs: List[Dict[str, str]],
    scenarios_path: Path = Path("data/scenarios.json"),
    max_scenarios: Optional[int] = None,
    db_path: Path = DEFAULT_DB_PATH,
    mock_mode: bool = False,
    max_workers: int = 1,
) -> pd.DataFrame:
    """Execute evaluation benchmark across multiple prompt versions.

    Args:
        prompt_configs: List of dicts with 'version' and 'path' keys.
        scenarios_path: Path to JSON file containing test scenarios.
        max_scenarios: Limit number of scenarios tested (for quick runs).
        db_path: SQLite database file path.
        mock_mode: If True, uses mock LLM calls.

    Returns:
        Pandas DataFrame summarizing comparative results.
    """
    init_db(db_path)

    with open(scenarios_path, encoding="utf-8") as f:
        all_scenarios = json.load(f)

    if max_scenarios:
        all_scenarios = all_scenarios[:max_scenarios]

    evaluator = LLMJudgeEvaluator(mock_mode=mock_mode)
    run_id = f"RUN_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    print("\n" + "=" * 80)
    print(f"STARTING VAANIFLOW BENCHMARK RUN: {run_id}")
    print(f"Scenarios: {len(all_scenarios)} | Prompts: {[p['version'] for p in prompt_configs]}")
    print(f"Database: {db_path} | Mock Mode: {mock_mode} | Parallel Workers: {max_workers}")
    print("FREE TIER SAFETY: Pacing enabled to strictly stay within free quotas (0 cost).")
    print("=" * 80 + "\n")

    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed

    db_lock = threading.Lock()

    def process_single_scenario(scenario_data: Dict[str, Any], prompt_ver: str, p_path: str):
        scen_id = scenario_data["id"]
        scen_name = scenario_data["name"]

        # Thread-local agent and customer instances
        agent_inst = NehaAgent(prompt_path=p_path, mock_mode=mock_mode)
        customer_inst = CustomerSimulator(scenario=scenario_data, mock_mode=mock_mode)

        record = run_call_simulation(
            agent=agent_inst,
            customer=customer_inst,
            prompt_version=prompt_ver,
            max_customer_turns=8,
            hard_safety_limit=12,
        )

        turn_dicts = [
            {"turn_index": t.turn_index, "speaker": t.speaker, "utterance": t.utterance}
            for t in record.turns
        ]

        scores = evaluator.evaluate_conversation(
            scenario=scenario_data,
            transcript_turns=turn_dicts,
        )

        # Thread-safe database commit
        with db_lock:
            conv_id = save_conversation(
                run_id=run_id,
                prompt_version=prompt_ver,
                scenario_id=scen_id,
                scenario_name=scen_name,
                category=scenario_data.get("category", "general"),
                stop_reason=record.stop_reason,
                total_customer_turns=record.total_customer_turns,
                turns=turn_dicts,
                db_path=db_path,
            )
            save_eval_score(
                conversation_id=conv_id,
                scores=scores,
                db_path=db_path,
            )

        overall_pct = int(scores.get("overall_pass_rate", 0) * 100)
        print(f"  [{prompt_ver}] {scen_id}: {scen_name} -> Pass Rate: {overall_pct}% | Stop: {record.stop_reason}")

        # Safe rate pacing for Gemini Free Tier (15 RPM)
        if not mock_mode:
            import time
            time.sleep(3.0)

        return scen_id, overall_pct

    for p_cfg in prompt_configs:
        version = p_cfg["version"]
        prompt_path = p_cfg["path"]
        print(f"\n>>> Running Evaluation for Prompt Version: {version} ({prompt_path})")

        if max_workers > 1:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [
                    executor.submit(process_single_scenario, sc, version, prompt_path)
                    for sc in all_scenarios
                ]
                for f in as_completed(futures):
                    f.result()
        else:
            for sc in all_scenarios:
                process_single_scenario(sc, version, prompt_path)

    print("\n" + "=" * 80)
    print("BENCHMARK COMPLETED. COMPUTING COMPARATIVE SQL METRICS...")
    print("=" * 80 + "\n")

    summary_query = f"""
    SELECT 
        c.prompt_version,
        COUNT(c.id) AS total_calls,
        ROUND(AVG(s.overall_pass_rate) * 100, 1) AS avg_pass_rate_pct,
        ROUND(AVG(s.stayed_in_character) * 100, 1) AS in_character_pct,
        ROUND(AVG(s.replies_short_spoken) * 100, 1) AS short_spoken_pct,
        ROUND(AVG(s.language_matched) * 100, 1) AS lang_matched_pct,
        ROUND(AVG(s.handled_objection) * 100, 1) AS handled_objection_pct,
        ROUND(AVG(s.achieved_goal) * 100, 1) AS achieved_goal_pct,
        ROUND(AVG(s.no_false_claims_or_pressure) * 100, 1) AS anti_hallucination_pct
    FROM conversations c
    JOIN eval_scores s ON c.id = s.conversation_id
    WHERE c.run_id = '{run_id}'
    GROUP BY c.prompt_version
    ORDER BY avg_pass_rate_pct DESC;
    """

    summary_df = query_dataframe(summary_query, db_path=db_path)
    print("PROMPT VERSION COMPARISON SUMMARY:")
    print(summary_df.to_string(index=False))

    return summary_df


def main() -> None:
    parser = argparse.ArgumentParser(description="VaaniFlow Evaluation Benchmark Runner.")
    parser.add_argument(
        "--prompts",
        nargs="+",
        default=["v1=prompts/v1.txt", "v2=prompts/v2.txt", "v3=prompts/v3.txt"],
        help="Prompt specs in format version=path (e.g. v1=prompts/v1.txt)",
    )
    parser.add_argument(
        "--scenarios",
        default="data/scenarios.json",
        help="Path to scenarios JSON file",
    )
    parser.add_argument(
        "--max-scenarios",
        type=int,
        default=None,
        help="Max scenarios to test (useful for fast verification)",
    )
    parser.add_argument(
        "--db",
        default="data/vaaniflow_evals.db",
        help="Path to SQLite database file",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run in mock/dry-run mode without external API calls",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=3,
        help="Number of parallel worker threads (1-5, default 3 for safe free-tier pacing)",
    )
    args = parser.parse_args()

    parsed_prompts = []
    for item in args.prompts:
        if "=" in item:
            v, p = item.split("=", 1)
            parsed_prompts.append({"version": v, "path": p})
        else:
            name = Path(item).stem
            parsed_prompts.append({"version": name, "path": item})

    # Auto-detect mock mode if API key is unconfigured
    api_key = os.getenv("GEMINI_API_KEY")
    mock_mode = args.mock or (not api_key or api_key == "your_gemini_api_key_here")

    run_benchmark(
        prompt_configs=parsed_prompts,
        scenarios_path=Path(args.scenarios),
        max_scenarios=args.max_scenarios,
        db_path=Path(args.db),
        mock_mode=mock_mode,
        max_workers=args.workers,
    )


if __name__ == "__main__":
    main()
