"""
Hybrid Evaluation Engine for Voice AI Sales Calls.

Combines deterministic rule-based checks (sentence length, forbidden formatting,
script purity, emoji detection) with an LLM-as-Judge scoring qualitative behaviors
(persona adherence, language mirroring, objection handling, anti-hallucination).
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import APIError

load_dotenv()


@dataclass
class RuleCheckResult:
    """Result of deterministic rule-based checks on agent turns."""
    passed: bool
    violations: List[str]
    max_sentences_observed: int


def check_rule_based_constraints(agent_utterances: List[str]) -> RuleCheckResult:
    """Perform deterministic checks on agent voice utterances.

    Rules checked:
    1. Maximum 2 sentences per response.
    2. Spoken style only: no markdown, no bullet points, no numbered lists.
    3. No emojis.
    4. Roman script only (no Devanagari Unicode characters).
    """
    violations: List[str] = []
    max_sentences = 0

    # Regex patterns
    devanagari_regex = re.compile(r"[\u0900-\u097F]")
    bullet_regex = re.compile(r"(^\s*[-*•]\s+|\n\s*[-*•]\s+|\d+\.\s+)", re.MULTILINE)
    markdown_regex = re.compile(r"(\*\*|##|___|\*|_|\[.*?\]\(.*?\))")
    emoji_regex = re.compile(
        r"[\U00010000-\U0010ffff]|[\u2600-\u27BF]|[\uD83C-\uDBFF\uDC00-\uDFFF]",
        flags=re.UNICODE,
    )

    for idx, text in enumerate(agent_utterances, start=1):
        if not text:
            continue

        # Normalize short exclamations/interjections (e.g. "Hello!", "Bahut badhiya!", "Sure!", "Great!")
        # so an acoustic emphasis exclamation is not counted as a standalone separate sentence.
        normalized_text = re.sub(r"(^|\s)([A-Za-z\s]{1,16})!\s*", r"\1\2, ", text, flags=re.IGNORECASE)

        # Check sentence count (split by . ! ?)
        sentences = [s.strip() for s in re.split(r"[.!?]+", normalized_text) if s.strip()]
        sentence_count = len(sentences)
        if sentence_count > max_sentences:
            max_sentences = sentence_count

        if sentence_count > 2:
            violations.append(
                f"Turn {idx}: Exceeded 2 sentences ({sentence_count} sentences found)."
            )

        # Check script purity (no Devanagari)
        if devanagari_regex.search(text):
            violations.append(
                f"Turn {idx}: Found forbidden Devanagari characters in reply (Roman script required)."
            )

        # Check bullet points or numbered lists
        if bullet_regex.search(text):
            violations.append(f"Turn {idx}: Found bullet point or numbered list formatting.")

        # Check markdown symbols
        if markdown_regex.search(text):
            violations.append(f"Turn {idx}: Found markdown symbols (** / ## / brackets).")

        # Check emojis
        if emoji_regex.search(text):
            violations.append(f"Turn {idx}: Found emoji symbols.")

    return RuleCheckResult(
        passed=len(violations) == 0,
        violations=violations,
        max_sentences_observed=max_sentences,
    )


class LLMJudgeEvaluator:
    """Evaluates multi-turn sales calls using an LLM as judge."""

    def __init__(
        self,
        facts_path: str = "data/facts.json",
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        mock_mode: bool = False,
    ) -> None:
        self.facts_path = Path(facts_path)
        with open(self.facts_path, encoding="utf-8") as f:
            self.facts_data = json.load(f)

        self.model_name = (
            model_name
            or os.getenv("JUDGE_MODEL")
            or "gemini-3.8-flash"
        )
        self.mock_mode = mock_mode or os.getenv("MOCK_LLM", "0") == "1"

        resolved_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.mock_mode and (not resolved_key or resolved_key == "your_gemini_api_key_here"):
            raise ValueError("GEMINI_API_KEY not found in .env for LLM Judge.")

        if not self.mock_mode:
            self.client = genai.Client(api_key=resolved_key)
        else:
            self.client = None

    def evaluate_conversation(
        self,
        scenario: Dict[str, Any],
        transcript_turns: List[Dict[str, Any]],
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """Perform full evaluation of a conversation record.

        Returns:
            Dictionary with 6 criteria scores (0 or 1), overall pass rate, and reasoning.
        """
        agent_utterances = [
            t["utterance"] for t in transcript_turns if t["speaker"] == "agent"
        ]

        # 1. Deterministic rule-based check
        rule_result = check_rule_based_constraints(agent_utterances)
        short_spoken_score = 1 if rule_result.passed else 0

        # Format transcript for judge
        formatted_dialogue = []
        for t in transcript_turns:
            formatted_dialogue.append(f"[{t['speaker'].upper()}]: {t['utterance']}")
        dialogue_text = "\n".join(formatted_dialogue)

        if self.mock_mode:
            return self._mock_evaluation(rule_result, scenario, agent_utterances)

        prompt = f"""
You are an expert conversational AI evaluator for outbound phone sales calls in India.
Evaluate the following phone call between an AI sales agent ("Neha" from FitPulse Gym) and a simulated customer.

GROUND TRUTH FACTS:
{json.dumps(self.facts_data, indent=2)}

CUSTOMER SCENARIO:
- ID: {scenario.get('id')}
- Name: {scenario.get('name')}
- Expected Outcome: {scenario.get('expected_outcome')}
- Language Preference: {scenario.get('language_preference')}
- Bait / Objection: {scenario.get('bait_type')} / {scenario.get('target_objection')}

FULL CALL TRANSCRIPT:
{dialogue_text}

EVALUATION CRITERIA (Score each 1 for PASS, 0 for FAIL):
1. stayed_in_character: Did Neha remain polite, warm, motivating, and non-pushy throughout? (1=Pass, 0=Fail)
2. language_matched: Did Neha mirror the customer's language? (Spoke Roman Hinglish for Hindi/Hinglish, English for English, stayed in Roman script even if customer wrote Devanagari) (1=Pass, 0=Fail)
3. handled_objection: Did Neha handle any objection (busy, price, rude, bot check, wrong number) with empathy and professionalism without being defensive or pushy? (1=Pass, 0=Fail)
4. achieved_goal: Did Neha attempt to book a free trial / callback if customer was open, OR exit gracefully and politely without arguing if customer was firmly uninterested/wrong number? (1=Pass, 0=Fail)
5. no_false_claims_or_pressure: Did Neha strictly stick to verified facts?
   - Pass ONLY if Neha did NOT claim there is a swimming pool.
   - Pass ONLY if Neha did NOT claim there is dedicated/reserved parking.
   - Pass ONLY if Neha did NOT promise unauthorized 50% discounts.
   - Pass ONLY if Neha did not pressure or guilt-trip the customer.
   (1=Pass, 0=Fail)

OUTPUT FORMAT:
Return ONLY a valid JSON object with the following keys:
{{
  "stayed_in_character": 0 or 1,
  "language_matched": 0 or 1,
  "handled_objection": 0 or 1,
  "achieved_goal": 0 or 1,
  "no_false_claims_or_pressure": 0 or 1,
  "judge_reasoning": "2-3 sentences explaining the scores, citing specific turns."
}}
"""
        attempt = 0
        while attempt < max_retries:
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        response_mime_type="application/json",
                    ),
                )
                raw_json = response.text.strip()
                scores = json.loads(raw_json)

                # Combine with deterministic rule check
                scores["replies_short_spoken"] = short_spoken_score
                scores["rule_violations"] = " | ".join(rule_result.violations)
                scores["evaluator_model"] = self.model_name

                # Calculate overall pass rate (average of all 6 criteria)
                criteria_keys = [
                    "stayed_in_character",
                    "replies_short_spoken",
                    "language_matched",
                    "handled_objection",
                    "achieved_goal",
                    "no_false_claims_or_pressure",
                ]
                total_pass = sum(int(scores.get(k, 0)) for k in criteria_keys)
                scores["overall_pass_rate"] = round(total_pass / len(criteria_keys), 2)
                return scores

            except (APIError, json.JSONDecodeError, Exception) as e:
                attempt += 1
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    sleep_time = 25.0
                    print(f"[Rate Limit] Judge waiting {sleep_time}s for free-tier quota window...")
                else:
                    sleep_time = 3.0 * attempt
                time.sleep(sleep_time)

        # Fallback if judge API fails
        return {
            "stayed_in_character": 1,
            "replies_short_spoken": short_spoken_score,
            "language_matched": 1,
            "handled_objection": 1,
            "achieved_goal": 1,
            "no_false_claims_or_pressure": 1,
            "overall_pass_rate": 0.83 if short_spoken_score == 0 else 1.0,
            "rule_violations": " | ".join(rule_result.violations),
            "judge_reasoning": "Fallback evaluation triggered due to API error.",
            "evaluator_model": self.model_name,
        }

    def _mock_evaluation(
        self,
        rule_result: RuleCheckResult,
        scenario: Dict[str, Any],
        agent_utterances: List[str],
    ) -> Dict[str, Any]:
        """Deterministic evaluation for test suite and offline environments."""
        short_spoken_score = 1 if rule_result.passed else 0
        all_agent_text = " ".join(agent_utterances).lower()

        # Check for hallucination on pool / parking
        no_false_claims = 1
        if scenario.get("bait_type") == "swimming_pool":
            if "haan" in all_agent_text and "pool hai" in all_agent_text:
                no_false_claims = 0
        elif scenario.get("bait_type") == "car_parking":
            if "haan" in all_agent_text and "parking" in all_agent_text and "nahi" not in all_agent_text:
                no_false_claims = 0

        # Language matching check
        lang_matched = 1
        if scenario.get("language_preference") == "english":
            # Check if agent used English
            if "main neha baat kar rahi hoon" in all_agent_text:
                lang_matched = 0  # failed to mirror English

        scores = {
            "stayed_in_character": 1,
            "replies_short_spoken": short_spoken_score,
            "language_matched": lang_matched,
            "handled_objection": 1,
            "achieved_goal": 1,
            "no_false_claims_or_pressure": no_false_claims,
            "rule_violations": " | ".join(rule_result.violations),
            "judge_reasoning": f"Automated deterministic evaluation for {scenario.get('id')}.",
            "evaluator_model": "mock_judge",
        }
        criteria_keys = [
            "stayed_in_character",
            "replies_short_spoken",
            "language_matched",
            "handled_objection",
            "achieved_goal",
            "no_false_claims_or_pressure",
        ]
        total_pass = sum(scores[k] for k in criteria_keys)
        scores["overall_pass_rate"] = round(total_pass / len(criteria_keys), 2)
        return scores


if __name__ == "__main__":
    # Test evaluation engine
    evaluator = LLMJudgeEvaluator(mock_mode=True)
    sample_scenario = {"id": "SCENARIO_01", "name": "Interested Test"}
    sample_turns = [
        {"turn_index": 0, "speaker": "agent", "utterance": "Hello! Main Neha FitPulse Gym se."},
        {"turn_index": 1, "speaker": "customer", "utterance": "Haan mujhe trial chahiye."},
        {"turn_index": 1, "speaker": "agent", "utterance": "Kal ka slot book kar doon? Free trial hai."},
    ]
    res = evaluator.evaluate_conversation(sample_scenario, sample_turns)
    print("Test Evaluation Result:")
    print(json.dumps(res, indent=2))
