"""
SQLite Database Layer for Conversation Storage and Evaluation Metrics.

Provides structured persistence for:
- Simulated phone conversations and turn-by-turn utterances
- Prompt versions and scenario metadata
- Granular rule-based and LLM-as-judge evaluation scores
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd


DEFAULT_DB_PATH = Path("data/vaaniflow_evals.db")


def get_db_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Create and return a SQLite database connection with row factory."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Initialize database tables if they do not exist."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.executescript(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            prompt_version TEXT NOT NULL,
            scenario_id TEXT NOT NULL,
            scenario_name TEXT NOT NULL,
            category TEXT NOT NULL,
            stop_reason TEXT NOT NULL,
            total_customer_turns INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS conversation_turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            turn_index INTEGER NOT NULL,
            speaker TEXT NOT NULL,
            utterance TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS eval_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            stayed_in_character INTEGER NOT NULL,
            replies_short_spoken INTEGER NOT NULL,
            language_matched INTEGER NOT NULL,
            handled_objection INTEGER NOT NULL,
            achieved_goal INTEGER NOT NULL,
            no_false_claims_or_pressure INTEGER NOT NULL,
            overall_pass_rate REAL NOT NULL,
            rule_violations TEXT,
            judge_reasoning TEXT,
            evaluator_model TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_conv_prompt ON conversations(prompt_version);
        CREATE INDEX IF NOT EXISTS idx_conv_scenario ON conversations(scenario_id);
        CREATE INDEX IF NOT EXISTS idx_scores_conv ON eval_scores(conversation_id);
        """
    )
    conn.commit()
    conn.close()


def save_conversation(
    run_id: str,
    prompt_version: str,
    scenario_id: str,
    scenario_name: str,
    category: str,
    stop_reason: str,
    total_customer_turns: int,
    turns: List[Dict[str, Any]],
    db_path: Path = DEFAULT_DB_PATH,
) -> int:
    """Save a conversation and its turns to the database.

    Returns:
        The inserted conversation ID.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO conversations (
            run_id, prompt_version, scenario_id, scenario_name, category, stop_reason, total_customer_turns
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            prompt_version,
            scenario_id,
            scenario_name,
            category,
            stop_reason,
            total_customer_turns,
        ),
    )
    conv_id = cursor.lastrowid

    turn_rows = [
        (conv_id, t["turn_index"], t["speaker"], t["utterance"])
        for t in turns
    ]
    cursor.executemany(
        """
        INSERT INTO conversation_turns (conversation_id, turn_index, speaker, utterance)
        VALUES (?, ?, ?, ?)
        """,
        turn_rows,
    )

    conn.commit()
    conn.close()
    return conv_id


def save_eval_score(
    conversation_id: int,
    scores: Dict[str, Any],
    db_path: Path = DEFAULT_DB_PATH,
) -> int:
    """Save evaluation scores for a conversation.

    Returns:
        The inserted eval score ID.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO eval_scores (
            conversation_id,
            stayed_in_character,
            replies_short_spoken,
            language_matched,
            handled_objection,
            achieved_goal,
            no_false_claims_or_pressure,
            overall_pass_rate,
            rule_violations,
            judge_reasoning,
            evaluator_model
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            conversation_id,
            int(scores["stayed_in_character"]),
            int(scores["replies_short_spoken"]),
            int(scores["language_matched"]),
            int(scores["handled_objection"]),
            int(scores["achieved_goal"]),
            int(scores["no_false_claims_or_pressure"]),
            float(scores["overall_pass_rate"]),
            scores.get("rule_violations", ""),
            scores.get("judge_reasoning", ""),
            scores.get("evaluator_model", "gemini-2.5-pro"),
        ),
    )
    score_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return score_id


def query_dataframe(query: str, db_path: Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    """Execute an arbitrary SQL query and return results as a Pandas DataFrame."""
    conn = get_db_connection(db_path)
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df
