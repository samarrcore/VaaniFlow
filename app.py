"""
VaaniFlow - Voice AI Sales Agent & Prompt Evaluation Studio.
Built with Streamlit following the 'streamlit-ui-craft' design skill principles:
- Industrial / Terminal Telemetry theme
- Distinctive typography (Space Grotesk + JetBrains Mono)
- Canvas-based animated voice waveform signature hero
- Controlled escape hatches (theme, injected CSS, components.html)
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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
from src.evaluator import LLMJudgeEvaluator, check_rule_based_constraints

load_dotenv()
init_db(DEFAULT_DB_PATH)

# Page configuration
st.set_page_config(
    page_title="VaaniFlow // Voice AI Studio",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_custom_styles():
    """Inject distinctive typography, terminal-themed styling, and widget overrides."""
    st.markdown(
        """
        <style>
        /* Typography Imports: Space Grotesk (Display) + JetBrains Mono (Code/Accents) + Plus Jakarta Sans (Body) */
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');

        /* Global App Root Typography */
        html, body, [data-testid="stAppViewContainer"] {
            font-family: 'Plus Jakarta Sans', sans-serif;
            color: #E6EDF3;
            background-color: #0A0D10;
        }

        /* Monospace / Code Accents */
        code, pre, .mono-text {
            font-family: 'JetBrains Mono', monospace !important;
        }

        /* Headings carry Space Grotesk */
        h1, h2, h3, h4, h5, h6 {
            font-family: 'Space Grotesk', sans-serif !important;
            letter-spacing: -0.02em;
            color: #FFFFFF;
        }

        /* Sidebar Styling */
        [data-testid="stSidebar"] {
            background-color: #0F1318 !important;
            border-right: 1px solid rgba(255, 255, 255, 0.08);
        }

        /* Custom Metric Cards */
        .telemetry-card {
            background: #13171E;
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 8px;
            padding: 18px 22px;
            margin-bottom: 16px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
            transition: border-color 0.2s ease;
        }
        .telemetry-card:hover {
            border-color: rgba(0, 242, 152, 0.35);
        }
        .telemetry-label {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            color: #8B949E;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 6px;
        }
        .telemetry-value {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 1.85rem;
            font-weight: 700;
            color: #00F298;
        }

        /* Dialogue Speech Bubbles */
        .bubble-container {
            display: flex;
            flex-direction: column;
            gap: 12px;
            margin: 16px 0;
        }
        .speech-bubble {
            padding: 14px 18px;
            border-radius: 8px;
            max-width: 82%;
            font-size: 0.95rem;
            line-height: 1.5;
            position: relative;
        }
        .bubble-agent {
            background: rgba(0, 242, 152, 0.06);
            border: 1px solid rgba(0, 242, 152, 0.3);
            border-left: 4px solid #00F298;
            align-self: flex-start;
        }
        .bubble-customer {
            background: rgba(88, 166, 255, 0.06);
            border: 1px solid rgba(88, 166, 255, 0.3);
            border-left: 4px solid #58A6FF;
            align-self: flex-end;
        }
        .speaker-badge {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.72rem;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            font-weight: 600;
            margin-bottom: 4px;
            display: block;
        }
        .badge-agent { color: #00F298; }
        .badge-customer { color: #58A6FF; }

        /* Restyle Native Buttons for Industrial Precision */
        .stButton > button {
            border-radius: 6px !important;
            border: 1px solid #00F298 !important;
            background: rgba(0, 242, 152, 0.08) !important;
            color: #00F298 !important;
            font-family: 'JetBrains Mono', monospace !important;
            font-weight: 600 !important;
            letter-spacing: 0.04em !important;
            padding: 8px 20px !important;
            transition: all 0.2s ease !important;
        }
        .stButton > button:hover {
            background: #00F298 !important;
            color: #0A0D10 !important;
            box-shadow: 0 0 16px rgba(0, 242, 152, 0.45) !important;
        }

        /* Pill status chips */
        .pill-pass {
            display: inline-block;
            background: rgba(0, 242, 152, 0.15);
            color: #00F298;
            border: 1px solid rgba(0, 242, 152, 0.4);
            padding: 3px 10px;
            border-radius: 12px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .pill-fail {
            display: inline-block;
            background: rgba(255, 92, 92, 0.15);
            color: #FF5C5C;
            border: 1px solid rgba(255, 92, 92, 0.4);
            padding: 3px 10px;
            border-radius: 12px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            font-weight: 600;
        }

        /* Tab styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 12px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            margin-bottom: 24px;
        }
        .stTabs [data-baseweb="tab"] {
            font-family: 'Space Grotesk', sans-serif !important;
            font-size: 0.95rem;
            color: #8B949E;
            padding: 10px 18px;
        }
        .stTabs [aria-selected="true"] {
            color: #00F298 !important;
            border-bottom: 2px solid #00F298 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_signature_hero():
    """Render the signature hero banner with animated audio waveform using components.html()."""
    components.html(
        """
        <!DOCTYPE html>
        <html>
        <head>
          <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500;700&family=Space+Grotesk:wght@700&display=swap" rel="stylesheet">
          <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
              background: #0D1117;
              color: #E6EDF3;
              font-family: 'JetBrains Mono', monospace;
              overflow: hidden;
            }
            .hero-container {
              display: flex;
              align-items: center;
              justify-content: space-between;
              padding: 16px 24px;
              border: 1px solid rgba(0, 242, 152, 0.25);
              border-radius: 10px;
              background: linear-gradient(90deg, rgba(13,17,23,0.95) 0%, rgba(20,28,38,0.95) 100%);
              box-shadow: 0 4px 20px rgba(0, 242, 152, 0.08);
            }
            .brand-col {
              display: flex;
              flex-direction: column;
              gap: 4px;
            }
            .brand-title {
              font-family: 'Space Grotesk', sans-serif;
              font-size: 1.5rem;
              font-weight: 700;
              letter-spacing: -0.03em;
              color: #FFFFFF;
              display: flex;
              align-items: center;
              gap: 10px;
            }
            .brand-badge {
              font-size: 0.65rem;
              background: rgba(0, 242, 152, 0.15);
              border: 1px solid #00F298;
              color: #00F298;
              padding: 2px 8px;
              border-radius: 4px;
              letter-spacing: 0.08em;
            }
            .brand-sub {
              font-size: 0.8rem;
              color: #8B949E;
            }
            .telemetry-row {
              display: flex;
              align-items: center;
              gap: 20px;
            }
            .status-indicator {
              display: flex;
              align-items: center;
              gap: 8px;
              font-size: 0.75rem;
              color: #00F298;
            }
            .pulse-dot {
              width: 8px;
              height: 8px;
              background: #00F298;
              border-radius: 50%;
              box-shadow: 0 0 10px #00F298;
              animation: pulse 1.5s infinite;
            }
            @keyframes pulse {
              0% { transform: scale(0.9); opacity: 0.7; }
              50% { transform: scale(1.3); opacity: 1; box-shadow: 0 0 14px #00F298; }
              100% { transform: scale(0.9); opacity: 0.7; }
            }
            canvas {
              width: 140px;
              height: 38px;
            }
          </style>
        </head>
        <body>
          <div class="hero-container">
            <div class="brand-col">
              <div class="brand-title">
                VAANIFLOW
                <span class="brand-badge">VOICE TELEMETRY</span>
              </div>
              <div class="brand-sub">FitPulse Gym Outbound Sales Calling & Prompt Evaluation Studio</div>
            </div>
            <div class="telemetry-row">
              <canvas id="waveform"></canvas>
              <div class="status-indicator">
                <div class="pulse-dot"></div>
                NEHA RUNTIME // READY
              </div>
            </div>
          </div>

          <script>
            const canvas = document.getElementById('waveform');
            const ctx = canvas.getContext('2d');
            canvas.width = 140;
            canvas.height = 38;

            let step = 0;
            function drawWave() {
              ctx.clearRect(0, 0, canvas.width, canvas.height);
              ctx.strokeStyle = '#00F298';
              ctx.lineWidth = 1.8;
              ctx.beginPath();
              
              for (let x = 0; x < canvas.width; x++) {
                const y = canvas.height / 2 + Math.sin((x + step) * 0.15) * 8 * Math.sin(x * 0.05);
                if (x === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
              }
              ctx.stroke();
              step += 2;
              requestAnimationFrame(drawWave);
            }
            drawWave();
          </script>
        </body>
        </html>
        """,
        height=85,
        scrolling=False,
    )


# Apply styles and hero
inject_custom_styles()
render_signature_hero()

# Load Scenarios and Facts
@st.cache_data
def load_scenarios():
    with open("data/scenarios.json", encoding="utf-8") as f:
        return json.load(f)

@st.cache_data
def load_facts():
    with open("data/facts.json", encoding="utf-8") as f:
        return json.load(f)

scenarios_list = load_scenarios()
facts_data = load_facts()

# ==============================================================================
# SIDEBAR CONTROLS
# ==============================================================================
with st.sidebar:
    st.markdown("### 🎙️ Call Engine Settings")

    prompt_version = st.selectbox(
        "Agent Prompt Version",
        ["v4", "v3", "v2", "v1"],
        index=0,
        help="v4 includes anti-hallucination guardrails and strict 2-sentence voice ceiling.",
    )

    prompt_descriptions = {
        "v1": "Zero-Shot Baseline (Instructions only)",
        "v2": "Few-Shot (4 Hinglish conversational examples)",
        "v3": "Persona & Playbook (Objection scripts)",
        "v4": "Production-Hardened (Anti-hallucination + 2-sentence ceiling)",
    }
    st.caption(f"**Strategy**: {prompt_descriptions[prompt_version]}")

    st.markdown("---")
    st.markdown("### ⚙️ Model Infrastructure")
    st.code(f"AGENT: {os.getenv('BOT_MODEL', 'gemini-3.5-flash-lite')}\nJUDGE: {os.getenv('JUDGE_MODEL', 'gemini-3.5-flash')}\nTIER : Free Tier Protected (0 Cost)", language="yaml")

    st.markdown("---")
    with st.expander("📖 Ground Truth Facts"):
        st.json(facts_data)

    if st.button("🔄 Reset Session State"):
        st.session_state.clear()
        st.rerun()

# ==============================================================================
# MAIN TABS
# ==============================================================================
tab_sim, tab_chat, tab_bench, tab_sql = st.tabs([
    "📞 Call Simulator & Live Evaluation",
    "💬 Live Interactive Chat",
    "📊 Benchmark Analytics",
    "🔍 SQL Telemetry Explorer"
])

# ------------------------------------------------------------------------------
# TAB 1: CALL SIMULATOR & LIVE EVALUATION
# ------------------------------------------------------------------------------
with tab_sim:
    st.markdown("#### Autonomous Sales Call Simulation")
    st.caption("Select a simulated customer scenario. Neha and the customer will converse autonomously, followed by an immediate hybrid evaluation.")

    col_select, col_meta = st.columns([2, 1])

    with col_select:
        scenario_options = {s["id"]: f"{s['id']} - {s['name']}" for s in scenarios_list}
        selected_scen_id = st.selectbox(
            "Select Scenario to Test",
            list(scenario_options.keys()),
            format_func=lambda x: scenario_options[x],
        )
        selected_scenario = next(s for s in scenarios_list if s["id"] == selected_scen_id)

    with col_meta:
        st.markdown(
            f"""
            <div class="telemetry-card" style="margin-top:24px;">
                <div class="telemetry-label">Category / Expected Outcome</div>
                <div style="font-family:'JetBrains Mono'; font-size:0.85rem; color:#00F298;">
                    {selected_scenario.get('category').upper()}<br>
                    <span style="color:#8B949E;">Target: {selected_scenario.get('expected_outcome')}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if st.button("🚀 Run Call Simulation & Score", key="btn_run_sim"):
        with st.spinner("Connecting outbound call... simulating multi-turn dialogue with Gemini..."):
            prompt_file = f"prompts/{prompt_version}.txt"
            agent = NehaAgent(prompt_path=prompt_file)
            customer = CustomerSimulator(scenario=selected_scenario)

            record = run_call_simulation(
                agent=agent,
                customer=customer,
                prompt_version=prompt_version,
            )

            # Convert turns
            turn_dicts = [
                {"turn_index": t.turn_index, "speaker": t.speaker, "utterance": t.utterance}
                for t in record.turns
            ]

            # Evaluate with judge
            evaluator = LLMJudgeEvaluator()
            scores = evaluator.evaluate_conversation(
                scenario=selected_scenario,
                transcript_turns=turn_dicts,
            )

            # Persist to SQLite
            conv_id = save_conversation(
                run_id="UI_RUN",
                prompt_version=prompt_version,
                scenario_id=selected_scenario["id"],
                scenario_name=selected_scenario["name"],
                category=selected_scenario.get("category", "general"),
                stop_reason=record.stop_reason,
                total_customer_turns=record.total_customer_turns,
                turns=turn_dicts,
            )
            save_eval_score(conversation_id=conv_id, scores=scores)

            st.session_state["last_sim_record"] = record
            st.session_state["last_sim_scores"] = scores

    # Display results if available
    if "last_sim_record" in st.session_state:
        rec = st.session_state["last_sim_record"]
        eval_res = st.session_state["last_sim_scores"]

        col_transcript, col_scorecard = st.columns([3, 2])

        with col_transcript:
            st.markdown("##### 📜 Call Audio Transcript")
            st.markdown(f"<span class='mono-text' style='color:#8B949E;'>Stop Reason: </span><span style='color:#00F298;' class='mono-text'>{rec.stop_reason}</span> | <span class='mono-text' style='color:#8B949E;'>Turns: {rec.total_customer_turns}</span>", unsafe_allow_html=True)

            st.markdown('<div class="bubble-container">', unsafe_allow_html=True)
            for t in rec.turns:
                is_agent = t.speaker == "agent"
                bubble_class = "bubble-agent" if is_agent else "bubble-customer"
                badge_class = "badge-agent" if is_agent else "badge-customer"
                speaker_name = "NEHA (FITPULSE ADVISOR)" if is_agent else "CUSTOMER"

                st.markdown(
                    f"""
                    <div class="speech-bubble {bubble_class}">
                        <span class="speaker-badge {badge_class}">{speaker_name}</span>
                        {t.utterance}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            st.markdown('</div>', unsafe_allow_html=True)

        with col_scorecard:
            st.markdown("##### 🏆 Evaluation Scorecard")
            overall_pct = int(eval_res.get("overall_pass_rate", 0) * 100)

            st.markdown(
                f"""
                <div class="telemetry-card">
                    <div class="telemetry-label">Overall Pass Rate</div>
                    <div class="telemetry-value">{overall_pct}%</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            criteria = [
                ("Stayed in Character", eval_res.get("stayed_in_character")),
                ("Max 2 Sentences & Spoken Style", eval_res.get("replies_short_spoken")),
                ("Language Matched Customer", eval_res.get("language_matched")),
                ("Handled Objection Properly", eval_res.get("handled_objection")),
                ("Goal Achieved", eval_res.get("achieved_goal")),
                ("No False Claims (Anti-Hallucination)", eval_res.get("no_false_claims_or_pressure")),
            ]

            for label, val in criteria:
                pass_chip = '<span class="pill-pass">PASS (1.0)</span>' if val == 1 else '<span class="pill-fail">FAIL (0.0)</span>'
                st.markdown(f"**{label}**: {pass_chip}", unsafe_allow_html=True)

            if eval_res.get("rule_violations"):
                st.error(f"Rule Violations: {eval_res['rule_violations']}")

            st.markdown("---")
            st.markdown("**LLM Judge Rationale:**")
            st.caption(eval_res.get("judge_reasoning", "No reasoning provided."))


# ------------------------------------------------------------------------------
# TAB 2: LIVE INTERACTIVE CHAT
# ------------------------------------------------------------------------------
with tab_chat:
    st.markdown("#### Live Human-to-Agent Testing Studio")
    st.caption("Roleplay as a gym customer directly with Neha in real time.")

    if "chat_history" not in st.session_state:
        agent_init = NehaAgent(prompt_path=f"prompts/{prompt_version}.txt")
        greeting = agent_init.get_initial_greeting()
        st.session_state.chat_history = [{"role": "agent", "content": greeting}]
        st.session_state.agent_instance = agent_init

    # Render chat messages
    for msg in st.session_state.chat_history:
        is_neha = msg["role"] == "agent"
        avatar = "🎙️" if is_neha else "👤"
        with st.chat_message(msg["role"], avatar=avatar):
            st.write(msg["content"])

    # Chat input
    user_speech = st.chat_input("Speak or type in Hindi, Hinglish, or English...")
    if user_speech:
        st.session_state.chat_history.append({"role": "user", "content": user_speech})
        with st.chat_message("user", avatar="👤"):
            st.write(user_speech)

        with st.chat_message("agent", avatar="🎙️"):
            with st.spinner("Neha is speaking..."):
                reply = st.session_state.agent_instance.generate_reply(user_speech)
                st.write(reply)
                st.session_state.chat_history.append({"role": "agent", "content": reply})

                # Instant rule check badge
                rule_chk = check_rule_based_constraints([reply])
                if rule_chk.passed:
                    st.caption("✅ Rule check: 2 sentences max, spoken style, Roman script.")
                else:
                    st.caption(f"⚠️ Rule violation: {' | '.join(rule_chk.violations)}")


# ------------------------------------------------------------------------------
# TAB 3: BENCHMARK ANALYTICS
# ------------------------------------------------------------------------------
with tab_bench:
    st.markdown("#### Prompt Performance Benchmarks (SQLite Store)")

    summary_query = """
    SELECT 
        c.prompt_version,
        COUNT(c.id) AS total_calls,
        ROUND(AVG(s.overall_pass_rate) * 100, 1) AS overall_pass_pct,
        ROUND(AVG(s.stayed_in_character) * 100, 1) AS in_character_pct,
        ROUND(AVG(s.replies_short_spoken) * 100, 1) AS short_spoken_pct,
        ROUND(AVG(s.language_matched) * 100, 1) AS lang_matched_pct,
        ROUND(AVG(s.handled_objection) * 100, 1) AS objection_pct,
        ROUND(AVG(s.achieved_goal) * 100, 1) AS goal_pct,
        ROUND(AVG(s.no_false_claims_or_pressure) * 100, 1) AS anti_hallucination_pct
    FROM conversations c
    JOIN eval_scores s ON c.id = s.conversation_id
    GROUP BY c.prompt_version
    ORDER BY overall_pass_pct DESC;
    """

    df_summary = query_dataframe(summary_query)

    if not df_summary.empty:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(
                f"""
                <div class="telemetry-card">
                    <div class="telemetry-label">Total Calls Evaluated</div>
                    <div class="telemetry-value">{df_summary['total_calls'].sum()}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col2:
            st.markdown(
                f"""
                <div class="telemetry-card">
                    <div class="telemetry-label">Avg Pass Rate</div>
                    <div class="telemetry-value">{df_summary['overall_pass_pct'].mean():.1f}%</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col3:
            st.markdown(
                f"""
                <div class="telemetry-card">
                    <div class="telemetry-label">Anti-Hallucination Rate</div>
                    <div class="telemetry-value">{df_summary['anti_hallucination_pct'].mean():.1f}%</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col4:
            st.markdown(
                f"""
                <div class="telemetry-card">
                    <div class="telemetry-label">Objection Handling</div>
                    <div class="telemetry-value">{df_summary['objection_pct'].mean():.1f}%</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.dataframe(df_summary, use_container_width=True)
    else:
        st.info("No conversations recorded in the database yet. Run a simulation in Tab 1!")


# ------------------------------------------------------------------------------
# TAB 4: SQL EXPLORER
# ------------------------------------------------------------------------------
with tab_sql:
    st.markdown("#### SQL Telemetry Explorer")
    st.caption("Query the SQLite evaluation store directly using standard SQL.")

    default_query = """SELECT c.id, c.prompt_version, c.scenario_id, c.stop_reason, s.overall_pass_rate, s.judge_reasoning 
FROM conversations c 
JOIN eval_scores s ON c.id = s.conversation_id 
ORDER BY c.id DESC LIMIT 10;"""

    user_sql = st.text_area("SQL Query", default_query, height=120)

    if st.button("Execute SQL", key="btn_exec_sql"):
        try:
            query_res = query_dataframe(user_sql)
            st.dataframe(query_res, use_container_width=True)
            st.success(f"Returned {len(query_res)} rows.")
        except Exception as err:
            st.error(f"SQL Error: {err}")
