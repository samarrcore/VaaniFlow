"""
Neha Voice Sales Agent Module.

Implements the multi-turn conversational agent for FitPulse Gym using Google Gemini SDK.
Designed specifically for voice-first interactions: short responses, Romanized Hinglish,
and strict guardrails against false claims.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import APIError

# Load environment variables from .env file
load_dotenv()


class NehaAgent:
    """Conversational sales agent representing Neha from FitPulse Gym."""

    def __init__(
        self,
        prompt_path: str = "prompts/v1.txt",
        model_name: Optional[str] = None,
        temperature: float = 0.35,
        api_key: Optional[str] = None,
        mock_mode: bool = False,
    ) -> None:
        """Initialize the NehaAgent.

        Args:
            prompt_path: Path to the prompt template file (v1, v2, v3, etc.).
            model_name: Gemini model name. Defaults to BOT_MODEL env var or gemini-2.5-flash.
            temperature: Sampling temperature for voice persona consistency (0.3 - 0.5).
            api_key: Optional explicit API key. Defaults to GEMINI_API_KEY env var.
        """
        self.prompt_path = Path(prompt_path)
        if not self.prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found at: {self.prompt_path}")

        self.system_prompt = self.prompt_path.read_text(encoding="utf-8").strip()
        self.model_name = (
            model_name
            or os.getenv("BOT_MODEL")
            or "gemini-3.8-flash"
        )
        self.temperature = temperature

        self.mock_mode = (
            mock_mode
            or os.getenv("MOCK_LLM", "0") == "1"
        )

        # Resolve API key
        resolved_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.mock_mode and (not resolved_key or resolved_key == "your_gemini_api_key_here"):
            raise ValueError(
                "GEMINI_API_KEY not found or unset in .env file. Please paste your valid Gemini API key into .env"
            )

        if not self.mock_mode:
            self.client = genai.Client(api_key=resolved_key)
        else:
            self.client = None
        self.history: List[types.Content] = []

    def reset(self) -> None:
        """Reset conversation history for a new call."""
        self.history = []

    def get_initial_greeting(self) -> str:
        """Generate or return the opening sales call greeting."""
        # Standard voice AI outbound opening line (strictly 2 sentences)
        return (
            "Hello, main Neha baat kar rahi hoon FitPulse Gym se. "
            "Aapne humare membership ke liye enquire kiya tha, toh socha jaan loon aapka kya fitness goal hai?"
        )

    def generate_reply(
        self,
        customer_utterance: str,
        max_retries: int = 3,
        backoff_seconds: float = 2.0,
    ) -> str:
        """Generate next agent reply given the customer's input utterance.

        Args:
            customer_utterance: The customer's latest spoken message.
            max_retries: Max retry attempts on API errors/rate limits.
            backoff_seconds: Base delay for exponential backoff.

        Returns:
            The agent's spoken reply string.
        """
        # Append user turn to conversation history
        self.history.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=customer_utterance)],
            )
        )

        # Handle mock mode for dry-run testing
        if self.mock_mode:
            lower = customer_utterance.lower()
            if "hello" in lower or "who" in lower or "kaun" in lower:
                reply = "Hello! Main Neha baat kar rahi hoon FitPulse Gym se. Kya main aapka fitness goal jaan sakti hoon?"
            elif "swimming" in lower or "pool" in lower:
                reply = "Nahi sir, hamare paas swimming pool nahi hai, par steam room aur complete gym setup available hai."
            elif "not interested" in lower or "nahi chahiye" in lower:
                reply = "Bilkul koi baat nahi! Thank you so much for your time, have a great day."
            elif "price" in lower or "fees" in lower or "kitna" in lower:
                reply = "Hamara monthly plan 2,500 rupees se start hota hai. Kya aap pehle ek din ka free trial workout try karna chahenge?"
            elif "english" in lower:
                reply = "Sure! We offer personalized fitness training and a free one-day trial workout at our branches."
            else:
                reply = "Bahut badhiya! Iske liye hamare paas certified trainers hain. Kya aap kal hamara free 1-day pass try karna chahenge?"

            self.history.append(
                types.Content(
                    role="model",
                    parts=[types.Part.from_text(text=reply)],
                )
            )
            return reply

        config = types.GenerateContentConfig(
            system_instruction=self.system_prompt,
            temperature=self.temperature,
            max_output_tokens=150,  # Strict cap to prevent long run-on sentences in voice
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

                reply_text = response.text.strip() if response.text else ""
                # Clean up any potential markdown headers or asterisks
                cleaned_reply = reply_text.replace("**", "").replace("##", "").strip()

                # Append agent turn to history
                self.history.append(
                    types.Content(
                        role="model",
                        parts=[types.Part.from_text(text=cleaned_reply)],
                    )
                )
                return cleaned_reply

            except APIError as e:
                attempt += 1
                last_error = e
                # Check for 429 rate limit and wait appropriately
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    sleep_time = 25.0
                    print(f"[Rate Limit] Free-tier 15 RPM limit reached. Waiting {sleep_time}s for quota window to reset...")
                else:
                    sleep_time = backoff_seconds * (2 ** (attempt - 1))
                    print(f"[Warning] Gemini API error (attempt {attempt}/{max_retries}): {e}. Retrying in {sleep_time}s...")
                time.sleep(sleep_time)
            except Exception as e:
                attempt += 1
                last_error = e
                sleep_time = backoff_seconds * (2 ** (attempt - 1))
                print(f"[Warning] Unexpected error (attempt {attempt}/{max_retries}): {e}. Retrying in {sleep_time}s...")
                time.sleep(sleep_time)

        raise RuntimeError(
            f"Failed to generate reply after {max_retries} attempts: {last_error}"
        )


def main() -> None:
    """Run an interactive CLI session with NehaAgent."""
    import argparse

    parser = argparse.ArgumentParser(description="Interactive CLI test for NehaAgent.")
    parser.add_argument(
        "--prompt",
        default="prompts/v1.txt",
        help="Path to prompt file (e.g. prompts/v1.txt, prompts/v2.txt, prompts/v3.txt)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run in mock/dry-run mode without requiring Gemini API key",
    )
    args = parser.parse_args()

    print("=" * 60)
    print(f"FitPulse Gym - Neha Voice Agent CLI Test")
    print(f"Using prompt: {args.prompt} (Mock mode: {args.mock})")
    print("Type 'exit' or 'quit' to end the call.")
    print("=" * 60)

    try:
        agent = NehaAgent(prompt_path=args.prompt, mock_mode=args.mock)
    except Exception as err:
        print(f"\n[Initialization Error]: {err}")
        sys.exit(1)

    greeting = agent.get_initial_greeting()
    print(f"\nNeha: {greeting}\n")

    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit"]:
                print("\nCall ended.")
                break

            reply = agent.generate_reply(user_input)
            print(f"\nNeha: {reply}\n")
        except (KeyboardInterrupt, EOFError):
            print("\nCall disconnected.")
            break


if __name__ == "__main__":
    main()
