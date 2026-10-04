"""
Customer Simulator Module.

Simulates diverse customer personas and conversational behaviors on phone calls
using Google Gemini SDK. Detects natural conversation termination conditions.
"""

from __future__ import annotations

import json
import os
import time
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import APIError

from src.agent import NehaAgent

load_dotenv()


@dataclass
class CallTurn:
    """Represents a single turn in a phone conversation."""
    turn_index: int
    speaker: str  # 'agent' or 'customer'
    utterance: str


@dataclass
class ConversationRecord:
    """Full record of a completed simulated conversation."""
    scenario_id: str
    scenario_name: str
    prompt_version: str
    stop_reason: str
    total_customer_turns: int
    turns: List[CallTurn] = field(default_factory=list)


class CustomerSimulator:
    """Simulates a customer persona during an outbound sales call."""

    def __init__(
        self,
        scenario: Dict[str, Any],
        model_name: Optional[str] = None,
        temperature: float = 0.75,
        api_key: Optional[str] = None,
        mock_mode: bool = False,
    ) -> None:
        """Initialize the customer simulator.

        Args:
            scenario: Dictionary containing scenario details and persona.
            model_name: Gemini model name. Defaults to CUSTOMER_MODEL or gemini-2.5-flash.
            temperature: Higher temperature for natural human conversational variety.
            api_key: Optional Gemini API key.
            mock_mode: If True, uses deterministic replies without calling API.
        """
        self.scenario = scenario
        self.scenario_id = scenario.get("id", "UNKNOWN")
        self.model_name = (
            model_name
            or os.getenv("CUSTOMER_MODEL")
            or os.getenv("BOT_MODEL")
            or "gemini-3.8-flash"
        )
        self.temperature = temperature
        self.mock_mode = mock_mode or os.getenv("MOCK_LLM", "0") == "1"

        resolved_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.mock_mode and (not resolved_key or resolved_key == "your_gemini_api_key_here"):
            raise ValueError(
                "GEMINI_API_KEY not found in .env. Please configure your key."
            )

        if not self.mock_mode:
            self.client = genai.Client(api_key=resolved_key)
        else:
            self.client = None

        self.history: List[types.Content] = []
        self.refusal_count = 0
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """Build the system prompt for the customer persona."""
        profile = self.scenario.get("customer_profile", "")
        instructions = self.scenario.get("persona_instructions", "")
        lang_pref = self.scenario.get("language_preference", "hinglish")

        script_instruction = (
            "Reply strictly in Devanagari Hindi script."
            if lang_pref == "hindi_devanagari"
            else "Reply strictly in Roman script (Latin letters), natural spoken Hinglish or English."
        )

        return (
            f"You are roleplaying as a customer receiving an unexpected outbound phone call from a gym sales advisor.\n"
            f"CUSTOMER PROFILE: {profile}\n"
            f"BEHAVIOR INSTRUCTIONS: {instructions}\n\n"
            f"CONVERSATIONAL RULES:\n"
            f"1. Spoken voice-call realism: speak 1 to 2 short sentences per turn.\n"
            f"2. {script_instruction}\n"
            f"3. Do not break character. Do not be overly cooperative unless the scenario instructs you to.\n"
            f"4. TERMINATION SIGNALS:\n"
            f"   - If you agree to a free gym trial visit or schedule an advisor callback, end your utterance with [AGREED].\n"
            f"   - If you refuse firmly, hang up, or say goodbye/disconnect, end your utterance with [HANGUP].\n"
        )

    def generate_reply(
        self,
        agent_utterance: str,
        turn_index: int,
        max_retries: int = 3,
        backoff_seconds: float = 2.0,
    ) -> str:
        """Generate customer reply to agent's spoken statement."""
        if self.mock_mode:
            return self._generate_mock_reply(agent_utterance, turn_index)

        self.history.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=f"Agent: {agent_utterance}")],
            )
        )

        config = types.GenerateContentConfig(
            system_instruction=self.system_prompt,
            temperature=self.temperature,
            max_output_tokens=100,
        )

        attempt = 0
        last_error: Optional[Exception] = None

        while attempt < max_retries:
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=self.history,
                    config=config,
                )
                text = response.text.strip() if response.text else ""
                self.history.append(
                    types.Content(
                        role="model",
                        parts=[types.Part.from_text(text=text)],
                    )
                )
                return text
            except APIError as e:
                attempt += 1
                last_error = e
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    sleep_time = 25.0
                    print(f"[Rate Limit] Customer sim waiting {sleep_time}s for free-tier window...")
                else:
                    sleep_time = backoff_seconds * (2 ** (attempt - 1))
                time.sleep(sleep_time)
            except Exception as e:
                attempt += 1
                last_error = e
                time.sleep(backoff_seconds * (2 ** (attempt - 1)))

        raise RuntimeError(f"Customer simulator failed after {max_retries} attempts: {last_error}")

    def _generate_mock_reply(self, agent_utterance: str, turn_index: int) -> str:
        """Generate deterministic replies for test verification."""
        scen_id = self.scenario_id
        if scen_id == "SCENARIO_01":
            if turn_index == 1:
                return "Haan mujhe weight loss karna hai, around 5 kg. Kya workout options hain?"
            else:
                return "Theek hai, kal shaam ka free trial book kar dijiye. [AGREED]"
        elif scen_id == "SCENARIO_03":
            return "Main abhi meeting mein hoon, please mujhe shaam ko 7 baje call kijiye. [HANGUP]"
        elif scen_id == "SCENARIO_04":
            return "Nahi mujhe nahi chahiye, maine already doosra gym join kar liya hai. [HANGUP]"
        elif scen_id == "SCENARIO_11":
            if turn_index == 1:
                return "Aapke Indiranagar wale branch mein swimming pool hai kya?"
            else:
                return "Achha pool nahi hai toh mujhe nahi aana, thank you. [HANGUP]"
        else:
            if turn_index >= 2:
                return "Chalo theek hai, trial pass bhej do. [AGREED]"
            return "Haan theek hai, bataiye kya plans hain?"


def run_call_simulation(
    agent: NehaAgent,
    customer: CustomerSimulator,
    prompt_version: str = "v1",
    max_customer_turns: int = 8,
    hard_safety_limit: int = 12,
) -> ConversationRecord:
    """Execute a complete simulated phone call between NehaAgent and CustomerSimulator.

    Args:
        agent: The Neha sales agent instance.
        customer: The simulated customer instance.
        prompt_version: Label for the prompt variant tested (e.g. 'v1', 'v2', 'v3').
        max_customer_turns: Maximum allowed customer turns before stopping.
        hard_safety_limit: Absolute hard turn limit preventing runaway calls.

    Returns:
        ConversationRecord containing full transcript and stop reason.
    """
    agent.reset()
    turns: List[CallTurn] = []
    stop_reason = "in_progress"

    # Step 1: Agent opens with the outbound call greeting
    greeting = agent.get_initial_greeting()
    turns.append(CallTurn(turn_index=0, speaker="agent", utterance=greeting))

    customer_turn_count = 0
    refusal_count = 0
    last_agent_utterance = greeting

    while customer_turn_count < max_customer_turns:
        customer_turn_count += 1
        total_dialogue_turns = len(turns)

        # Check hard safety limit
        if total_dialogue_turns >= hard_safety_limit:
            stop_reason = "safety_limit_reached"
            break

        # Generate customer reply
        customer_reply = customer.generate_reply(
            agent_utterance=last_agent_utterance,
            turn_index=customer_turn_count,
        )

        clean_customer_reply = (
            customer_reply.replace("[AGREED]", "")
            .replace("[HANGUP]", "")
            .strip()
        )

        turns.append(
            CallTurn(
                turn_index=customer_turn_count,
                speaker="customer",
                utterance=clean_customer_reply,
            )
        )

        # Check refusal patterns
        lower_cust = clean_customer_reply.lower()
        if any(neg in lower_cust for neg in ["not interested", "nahi chahiye", "wrong number", "galat number", "disconnect"]):
            refusal_count += 1

        # Check explicit stop conditions from customer
        if "[AGREED]" in customer_reply:
            stop_reason = "agreed_visit_or_callback"
            # Final agent wrap-up acknowledgment
            final_agent_ack = agent.generate_reply(clean_customer_reply)
            turns.append(CallTurn(turn_index=customer_turn_count, speaker="agent", utterance=final_agent_ack))
            break

        if "[HANGUP]" in customer_reply:
            stop_reason = "customer_hangup"
            break

        if refusal_count >= 2:
            stop_reason = "refused_twice"
            break

        # Generate agent reply
        agent_reply = agent.generate_reply(clean_customer_reply)
        turns.append(
            CallTurn(
                turn_index=customer_turn_count,
                speaker="agent",
                utterance=agent_reply,
            )
        )
        last_agent_utterance = agent_reply

        # Check if agent gracefully said goodbye upon refusal
        lower_agent = agent_reply.lower()
        if any(bye in lower_agent for bye in ["have a great day", "have a wonderful day", "shubh din"]):
            if refusal_count > 0:
                stop_reason = "polite_agent_closure"
                break

    if stop_reason == "in_progress":
        stop_reason = "max_turn_cap_reached"

    return ConversationRecord(
        scenario_id=customer.scenario.get("id", "UNKNOWN"),
        scenario_name=customer.scenario.get("name", "Unknown Scenario"),
        prompt_version=prompt_version,
        stop_reason=stop_reason,
        total_customer_turns=customer_turn_count,
        turns=turns,
    )


if __name__ == "__main__":
    # Test 1 scenario end-to-end
    scenarios_path = Path("data/scenarios.json")
    with open(scenarios_path, encoding="utf-8") as f:
        scenarios = json.load(f)

    test_scenario = scenarios[0]
    print(f"Testing Scenario 1 End-to-End: {test_scenario['name']}")

    mock_flag = os.getenv("GEMINI_API_KEY") is None or os.getenv("GEMINI_API_KEY") == "your_gemini_api_key_here"
    agent = NehaAgent(prompt_path="prompts/v1.txt", mock_mode=mock_flag)
    customer = CustomerSimulator(scenario=test_scenario, mock_mode=mock_flag)

    record = run_call_simulation(agent, customer, prompt_version="v1")
    print(f"\nCall Ended. Stop Reason: {record.stop_reason} (Turns: {record.total_customer_turns})")
    print("\n--- TRANSCRIPT ---")
    for t in record.turns:
        print(f"[{t.speaker.upper()}]: {t.utterance}")
