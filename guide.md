# Tazama Rule Agent — Complete Build Guide

A fully agentic Python application that installs Tazama rules autonomously.
You provide: **rule number + description**. The agent handles everything else.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                   Streamlit UI                       │
│  (Rule input → Live agent log → Status dashboard)   │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│                 Agent Orchestrator                   │
│         (agent.py — controls stage pipeline)         │
└──┬──────────┬──────────┬──────────┬─────────────────┘
   │          │          │          │
┌──▼──┐  ┌───▼──┐  ┌────▼──┐  ┌───▼──────────────────┐
│Stage│  │Stage │  │Stage  │  │Stage 4               │
│  1  │  │  2   │  │  3    │  │DB Writer + Script     │
│     │  │      │  │       │  │Runner                 │
│Rule │  │Band  │  │Weight │  │                       │
│Info │  │Gen   │  │Gen    │  │                       │
└──┬──┘  └───┬──┘  └────┬──┘  └───┬──────────────────┘
   │          │          │          │
┌──▼──────────▼──────────▼──────────▼──────────────────┐
│              OpenAI Client (gpt-4o-mini)              │
│          One small focused call per stage             │
└───────────────────────────────────────────────────────┘
```

---

## Project Structure

```
tazama-rule-agent/
├── config.py              # Central config (all settings here)
├── agent.py               # Orchestrator — runs all stages in order
├── stages/
│   ├── __init__.py
│   ├── stage1_rule_info.py    # Classify rule, confirm exit conditions
│   ├── stage2_bands.py        # Generate band configuration
│   ├── stage3_weights.py      # Generate typology weights
│   └── stage4_executor.py     # Run install-rule.sh non-interactively
├── ui/
│   └── app.py             # Streamlit UI
├── utils/
│   ├── logger.py          # Structured debug logger
│   ├── openai_client.py   # Thin OpenAI wrapper with retries
│   └── shell.py           # Shell command runner with timeout
├── install-rule.sh        # Your existing script (modified — see below)
├── .env                   # Secrets (never commit)
├── requirements.txt
└── logs/                  # Auto-created, one file per run
```

---

## Step 1 — Prerequisites

```bash
# Python 3.11+
python3 --version

# Install dependencies
pip install streamlit openai python-dotenv rich pexpect

# Confirm kubectl and docker available on same host
kubectl version --client
docker info
```

---

## Step 2 — `.env` file

```env
# OpenAI
OPENAI_API_KEY=sk-...

# Kubernetes
NAMESPACE=tazama
TYPOLOGY_ID=typology-processor@1.0.0
PG_DEPLOY=postgres
PG_DB=configuration
PG_USER=postgres
TENANT_ID=DEFAULT
CONFIGMAP=tazama-rule-common-config
IMAGE_ORG=tazamaorg

# Script
INSTALL_SCRIPT_PATH=/home/tom/install-rule.sh

# Agent behavior
MAX_RETRIES=3
LOG_LEVEL=DEBUG     # DEBUG | INFO | ERROR
```

---

## Step 3 — `config.py`

```python
# config.py
# ─────────────────────────────────────────────
# Central configuration — all tunables live here.
# ─────────────────────────────────────────────
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # OpenAI
    OPENAI_API_KEY: str   = os.getenv("OPENAI_API_KEY", "")
    # Use gpt-4o-mini for all stages — fast, cheap, accurate for structured tasks
    OPENAI_MODEL: str     = "gpt-4o-mini"
    OPENAI_TEMPERATURE: float = 0.1      # Low = deterministic outputs
    MAX_RETRIES: int      = int(os.getenv("MAX_RETRIES", 3))

    # Kubernetes / infra
    NAMESPACE: str        = os.getenv("NAMESPACE", "tazama")
    TYPOLOGY_ID: str      = os.getenv("TYPOLOGY_ID", "typology-processor@1.0.0")
    PG_DEPLOY: str        = os.getenv("PG_DEPLOY", "postgres")
    PG_DB: str            = os.getenv("PG_DB", "configuration")
    PG_USER: str          = os.getenv("PG_USER", "postgres")
    TENANT_ID: str        = os.getenv("TENANT_ID", "DEFAULT")
    CONFIGMAP: str        = os.getenv("CONFIGMAP", "tazama-rule-common-config")
    IMAGE_ORG: str        = os.getenv("IMAGE_ORG", "tazamaorg")
    IMAGE_TAG: str        = "3.0.0"      # Docker image tag to use

    # Script
    INSTALL_SCRIPT_PATH: str = os.getenv("INSTALL_SCRIPT_PATH", "./install-rule.sh")
    SCRIPT_TIMEOUT: int   = 300          # Max seconds for script to run

    # Logging
    LOG_LEVEL: str        = os.getenv("LOG_LEVEL", "DEBUG")
    LOG_DIR: str          = "./logs"

cfg = Config()
```

---

## Step 4 — `utils/logger.py`

```python
# utils/logger.py
import logging
import os
from datetime import datetime
from rich.logging import RichHandler
from config import cfg

os.makedirs(cfg.LOG_DIR, exist_ok=True)

def get_logger(name: str) -> logging.Logger:
    log_file = os.path.join(
        cfg.LOG_DIR,
        f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, cfg.LOG_LEVEL, logging.DEBUG))

    if not logger.handlers:
        # Console — rich colored output
        console = RichHandler(rich_tracebacks=True, markup=True)
        console.setLevel(getattr(logging, cfg.LOG_LEVEL))
        logger.addHandler(console)

        # File — plain text, always DEBUG
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))
        logger.addHandler(file_handler)

    return logger
```

---

## Step 5 — `utils/openai_client.py`

```python
# utils/openai_client.py
# Thin wrapper: one call per stage, with retry + structured JSON output.
import json
import time
from openai import OpenAI
from config import cfg
from utils.logger import get_logger

log = get_logger("openai_client")
client = OpenAI(api_key=cfg.OPENAI_API_KEY)


def ask(system_prompt: str, user_prompt: str, label: str = "") -> dict:
    """
    Single OpenAI call. Always returns parsed JSON dict.
    Retries up to cfg.MAX_RETRIES on failure.
    """
    for attempt in range(1, cfg.MAX_RETRIES + 1):
        log.debug(f"[{label}] Attempt {attempt} — sending to {cfg.OPENAI_MODEL}")
        log.debug(f"[{label}] USER PROMPT:\n{user_prompt}")
        try:
            response = client.chat.completions.create(
                model=cfg.OPENAI_MODEL,
                temperature=cfg.OPENAI_TEMPERATURE,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ]
            )
            raw = response.choices[0].message.content
            log.debug(f"[{label}] RAW RESPONSE:\n{raw}")
            parsed = json.loads(raw)
            log.info(f"[{label}] ✓ Parsed successfully")
            return parsed

        except Exception as e:
            log.warning(f"[{label}] Attempt {attempt} failed: {e}")
            if attempt < cfg.MAX_RETRIES:
                time.sleep(2 ** attempt)
            else:
                raise RuntimeError(f"[{label}] All {cfg.MAX_RETRIES} attempts failed: {e}")
```

---

## Step 6 — Stage 1: Rule Info

```python
# stages/stage1_rule_info.py
# Task: Given rule number + description, determine:
#   - maxQueryRange
#   - number of exit conditions and their refs/reasons
# Small, focused task.
from utils.openai_client import ask
from utils.logger import get_logger

log = get_logger("stage1")

SYSTEM = """
You are a financial crime detection system expert for Tazama.
You output ONLY valid JSON. No prose. No markdown.

Given a rule number and description, determine:
- maxQueryRange: integer milliseconds (86400000 = 1 day, 604800000 = 7 days)
- exit_conditions: list of {reason, subRuleRef} objects
  Always include .x00 for "Incoming transaction is unsuccessful" if relevant.
  Use .x01, .x02 for additional exits if the rule logic requires them.

Base decisions on the rule's description and financial crime detection patterns.
"""

def run(rule_num: str, description: str) -> dict:
    log.info(f"Stage 1 — Determining rule metadata for rule-{rule_num}")

    result = ask(
        system_prompt=SYSTEM,
        user_prompt=f"""
Rule number: {rule_num}
Description: {description}

Return JSON:
{{
  "maxQueryRange": <integer>,
  "exit_conditions": [
    {{"reason": "...", "subRuleRef": ".x00"}},
    ...
  ]
}}
""",
        label="stage1"
    )

    log.info(f"Stage 1 result: {result}")
    return result
```

---

## Step 7 — Stage 2: Band Generation

```python
# stages/stage2_bands.py
# Task: Generate band configuration only.
# Small, focused task.
from utils.openai_client import ask
from utils.logger import get_logger

log = get_logger("stage2")

SYSTEM = """
You are a financial crime detection system expert for Tazama.
You output ONLY valid JSON. No prose. No markdown.

Generate band configuration for a rule processor.
Bands define ranges of a measured value (count, amount, days, etc.)
and map to subRuleRef outputs (.01, .02, .03, etc.)

Rules:
- First band: no lowerLimit field, has upperLimit
- Middle bands: have both lowerLimit and upperLimit  
- Last band: has lowerLimit, no upperLimit field
- Higher risk behavior = lower numbered band (.01 = most suspicious)
- Typical: 2-4 bands
"""

def run(rule_num: str, description: str, exit_conditions: list) -> dict:
    log.info(f"Stage 2 — Generating bands for rule-{rule_num}")

    result = ask(
        system_prompt=SYSTEM,
        user_prompt=f"""
Rule number: {rule_num}
Description: {description}
Exit conditions already defined: {exit_conditions}

Generate appropriate bands. Return JSON:
{{
  "bands": [
    {{"reason": "...", "subRuleRef": ".01", "upperLimit": <int>}},
    {{"reason": "...", "subRuleRef": ".02", "lowerLimit": <int>, "upperLimit": <int>}},
    {{"reason": "...", "subRuleRef": ".03", "lowerLimit": <int>}}
  ],
  "measured_value_explanation": "brief note on what value is being measured"
}}
""",
        label="stage2"
    )

    log.info(f"Stage 2 result: {result}")
    return result
```

---

## Step 8 — Stage 3: Weight Generation

```python
# stages/stage3_weights.py
# Task: Generate typology weights for each subRuleRef.
# Small, focused task.
from utils.openai_client import ask
from utils.logger import get_logger

log = get_logger("stage3")

SYSTEM = """
You are a financial crime detection system expert for Tazama.
You output ONLY valid JSON. No prose. No markdown.

Generate typology weights for a rule.
Rules:
- Every possible subRuleRef the rule can return MUST have a weight entry
- Always include: .err, all exit condition refs, all band refs
- Higher risk subRuleRef = higher weight
- .err and exit conditions (.x00, .x01 etc) are always weight 0
- Band weights: most suspicious band (.01) gets highest weight
- Typical weight values: 0, 100, 200, 300, 400
- All weights are strings (e.g. "400" not 400)
"""

def run(rule_num: str, description: str, bands: list, exit_conditions: list) -> dict:
    log.info(f"Stage 3 — Generating weights for rule-{rule_num}")

    band_refs = [b["subRuleRef"] for b in bands]
    exit_refs = [e["subRuleRef"] for e in exit_conditions]

    result = ask(
        system_prompt=SYSTEM,
        user_prompt=f"""
Rule number: {rule_num}
Description: {description}
Band subRuleRefs (in order, .01 = most suspicious): {band_refs}
Exit condition refs: {exit_refs}

Return JSON:
{{
  "weights": [
    {{"ref": ".err",  "wght": "0"}},
    {{"ref": ".x00",  "wght": "0"}},
    {{"ref": ".01",   "wght": "400"}},
    ...
  ]
}}
""",
        label="stage3"
    )

    log.info(f"Stage 3 result: {result}")
    return result
```

---

## Step 9 — Stage 4: Script Executor

```python
# stages/stage4_executor.py
# Task: Feed all generated config into install-rule.sh non-interactively.
import pexpect
import sys
from config import cfg
from utils.logger import get_logger

log = get_logger("stage4")


def build_answers(rule_num: str, image_tag: str, description: str,
                  bands: list, exit_conditions: list, weights: list) -> list:
    """
    Returns ordered list of answers to match every script prompt exactly.
    """
    answers = [
        rule_num,                        # Rule number
        image_tag,                       # Image tag
        description,                     # Description
        str(len(bands)),                 # Number of bands
    ]

    for i, band in enumerate(bands):
        answers.append(band["subRuleRef"])
        answers.append(band["reason"])
        if i < len(bands) - 1:
            answers.append(str(band["upperLimit"]))

    answers.append(str(len(exit_conditions)))   # Exit condition count
    for ec in exit_conditions:
        answers.append(ec["subRuleRef"])
        answers.append(ec["reason"])

    answers.append(str(len(weights)))            # Weight count
    for w in weights:
        answers.append(w["ref"])
        answers.append(str(w["wght"]))

    answers.append("y")                          # Confirm proceed

    log.debug(f"Prepared {len(answers)} answers for script prompts")
    return answers


def run(rule_num: str, image_tag: str, description: str,
        bands: list, exit_conditions: list, weights: list,
        stream_callback=None) -> bool:
    """
    Runs install-rule.sh using pexpect to answer prompts automatically.
    stream_callback(line: str) is called for each output line (for UI streaming).
    Returns True on success.
    """
    answers = build_answers(rule_num, image_tag, description,
                            bands, exit_conditions, weights)
    answer_index = [0]  # mutable for closure

    log.info(f"Stage 4 — Running install-rule.sh for rule-{rule_num}")

    try:
        child = pexpect.spawn(
            f"sudo bash {cfg.INSTALL_SCRIPT_PATH}",
            timeout=cfg.SCRIPT_TIMEOUT,
            encoding="utf-8"
        )
        child.logfile_read = open(
            f"{cfg.LOG_DIR}/script_run_{rule_num}.log", "w"
        )

        while True:
            try:
                # Wait for any prompt ending in "> " or known patterns
                idx = child.expect([
                    r">\s*$",           # Script prompt
                    pexpect.EOF,
                    pexpect.TIMEOUT,
                ], timeout=120)

                # Stream output so far to UI
                output = child.before or ""
                for line in output.splitlines():
                    line = line.strip()
                    if line:
                        log.debug(f"[script] {line}")
                        if stream_callback:
                            stream_callback(line)

                if idx == 0:
                    if answer_index[0] < len(answers):
                        ans = answers[answer_index[0]]
                        log.debug(f"  → Answering prompt [{answer_index[0]}]: {ans!r}")
                        child.sendline(ans)
                        answer_index[0] += 1
                    else:
                        log.warning("More prompts than expected answers — sending empty")
                        child.sendline("")

                elif idx == 1:   # EOF — script finished
                    remaining = child.before or ""
                    for line in remaining.splitlines():
                        line = line.strip()
                        if line:
                            log.debug(f"[script] {line}")
                            if stream_callback:
                                stream_callback(line)
                    break

                elif idx == 2:   # TIMEOUT
                    log.error("Script timed out waiting for prompt")
                    if stream_callback:
                        stream_callback("[ERROR] Script timed out")
                    return False

            except pexpect.EOF:
                break

        exit_status = child.wait()
        log.info(f"Script exited with status: {exit_status}")
        return exit_status == 0

    except Exception as e:
        log.error(f"Stage 4 failed: {e}", exc_info=True)
        if stream_callback:
            stream_callback(f"[ERROR] {e}")
        return False
```

---

## Step 10 — `agent.py` (Orchestrator)

```python
# agent.py
# Runs all 4 stages in sequence with full error handling.
from config import cfg
from utils.logger import get_logger
from stages import stage1_rule_info, stage2_bands, stage3_weights, stage4_executor

log = get_logger("agent")


def run_pipeline(rule_num: str, description: str,
                 stream_callback=None) -> dict:
    """
    Full pipeline: Stage1 → Stage2 → Stage3 → Stage4
    stream_callback(msg: str) used to push progress to UI.
    Returns result dict with success flag and all stage outputs.
    """

    def emit(msg: str):
        log.info(msg)
        if stream_callback:
            stream_callback(msg)

    result = {
        "rule_num": rule_num,
        "description": description,
        "success": False,
        "stage1": None,
        "stage2": None,
        "stage3": None,
        "stage4": None,
        "error": None,
    }

    try:
        # ── Stage 1 ──────────────────────────────────────────────
        emit("▶ Stage 1 — Determining rule metadata...")
        s1 = stage1_rule_info.run(rule_num, description)
        result["stage1"] = s1
        emit(f"  ✓ maxQueryRange: {s1['maxQueryRange']}ms")
        emit(f"  ✓ Exit conditions: {len(s1['exit_conditions'])}")

        # ── Stage 2 ──────────────────────────────────────────────
        emit("▶ Stage 2 — Generating band configuration...")
        s2 = stage2_bands.run(rule_num, description, s1["exit_conditions"])
        result["stage2"] = s2
        emit(f"  ✓ {len(s2['bands'])} bands generated")
        for b in s2["bands"]:
            emit(f"    {b['subRuleRef']}: {b['reason']}")

        # ── Stage 3 ──────────────────────────────────────────────
        emit("▶ Stage 3 — Generating typology weights...")
        s3 = stage3_weights.run(
            rule_num, description,
            s2["bands"], s1["exit_conditions"]
        )
        result["stage3"] = s3
        emit(f"  ✓ {len(s3['weights'])} weight entries")
        for w in s3["weights"]:
            emit(f"    {w['ref']} → {w['wght']}")

        # ── Stage 4 ──────────────────────────────────────────────
        emit("▶ Stage 4 — Running install script...")
        success = stage4_executor.run(
            rule_num=rule_num,
            image_tag=cfg.IMAGE_TAG,
            description=description,
            bands=s2["bands"],
            exit_conditions=s1["exit_conditions"],
            weights=s3["weights"],
            stream_callback=stream_callback,
        )

        result["stage4"] = {"success": success}
        result["success"] = success

        if success:
            emit(f"✅ Rule {rule_num} installed successfully.")
        else:
            emit(f"❌ Script execution failed for rule {rule_num}.")

    except Exception as e:
        result["error"] = str(e)
        log.error(f"Pipeline error: {e}", exc_info=True)
        emit(f"❌ Pipeline error: {e}")

    return result
```

---

## Step 11 — `ui/app.py` (Streamlit UI)

```python
# ui/app.py
import streamlit as st
import threading
import queue
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent import run_pipeline
from config import cfg

st.set_page_config(
    page_title="Tazama Rule Agent",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ──────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Syne:wght@700;800&display=swap');

  html, body, [class*="css"] { font-family: 'JetBrains Mono', monospace; }
  h1, h2, h3 { font-family: 'Syne', sans-serif; letter-spacing: -0.03em; }

  .stApp { background: #0a0e1a; color: #e2e8f0; }

  .rule-card {
    background: #111827;
    border: 1px solid #1e2d45;
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1rem;
  }

  .stage-badge {
    display: inline-block;
    background: #1e3a5f;
    color: #60a5fa;
    font-size: 0.7rem;
    font-weight: 700;
    padding: 2px 10px;
    border-radius: 20px;
    margin-bottom: 0.5rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }

  .log-box {
    background: #070b14;
    border: 1px solid #1a2744;
    border-radius: 8px;
    padding: 1rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    color: #94a3b8;
    height: 380px;
    overflow-y: auto;
    line-height: 1.7;
  }

  .success { color: #34d399; }
  .error   { color: #f87171; }
  .info    { color: #60a5fa; }
  .warn    { color: #fbbf24; }

  div[data-testid="stSidebar"] {
    background: #080c18;
    border-right: 1px solid #1a2744;
  }
</style>
""", unsafe_allow_html=True)


# ── Sidebar: Config ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Configuration")
    st.markdown("---")
    st.markdown(f"**Model:** `{cfg.OPENAI_MODEL}`")
    st.markdown(f"**Namespace:** `{cfg.NAMESPACE}`")
    st.markdown(f"**Image tag:** `{cfg.IMAGE_TAG}`")
    st.markdown(f"**Typology:** `{cfg.TYPOLOGY_ID}`")
    st.markdown(f"**Log level:** `{cfg.LOG_LEVEL}`")
    st.markdown("---")

    st.markdown("### 📋 Installed Rules")
    if "installed_rules" not in st.session_state:
        st.session_state.installed_rules = []
    if st.session_state.installed_rules:
        for r in st.session_state.installed_rules:
            icon = "✅" if r["success"] else "❌"
            st.markdown(f"{icon} `rule-{r['rule_num']}`")
    else:
        st.caption("No rules installed this session.")

    st.markdown("---")
    log_dir = cfg.LOG_DIR
    if os.path.isdir(log_dir):
        logs = sorted(os.listdir(log_dir), reverse=True)[:5]
        if logs:
            st.markdown("### 🗂️ Recent Logs")
            for l in logs:
                st.caption(l)


# ── Main UI ─────────────────────────────────────────────────────────
st.markdown("# 🛡️ Tazama Rule Agent")
st.markdown("Autonomous rule installation — powered by GPT-4o-mini")
st.markdown("---")

col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.markdown("### Install a Rule")

    with st.form("rule_form", clear_on_submit=False):
        rule_num = st.text_input(
            "Rule Number",
            placeholder="e.g. 030",
            help="3-digit rule number"
        )
        description = st.text_area(
            "Rule Description",
            placeholder="e.g. Transfer to unfamiliar creditor account - debtor",
            height=100,
            help="Human-readable description of what this rule detects"
        )
        submitted = st.form_submit_button(
            "🚀 Install Rule",
            use_container_width=True,
            type="primary"
        )

    # Stage preview cards (populated after run)
    if "last_result" in st.session_state and st.session_state.last_result:
        res = st.session_state.last_result
        st.markdown("### 📊 Stage Outputs")

        if res.get("stage1"):
            with st.expander("Stage 1 — Rule Metadata", expanded=False):
                st.json(res["stage1"])

        if res.get("stage2"):
            with st.expander("Stage 2 — Bands", expanded=False):
                st.json(res["stage2"])

        if res.get("stage3"):
            with st.expander("Stage 3 — Weights", expanded=False):
                st.json(res["stage3"])

with col2:
    st.markdown("### 📡 Live Agent Log")
    log_placeholder = st.empty()
    status_placeholder = st.empty()

    if "log_lines" not in st.session_state:
        st.session_state.log_lines = []

    def render_log():
        lines_html = ""
        for line in st.session_state.log_lines[-120:]:
            if "[ERROR]" in line or "❌" in line:
                cls = "error"
            elif "✅" in line or "✓" in line:
                cls = "success"
            elif "▶" in line or "Stage" in line:
                cls = "info"
            elif "[WARN]" in line:
                cls = "warn"
            else:
                cls = ""
            safe = line.replace("<", "&lt;").replace(">", "&gt;")
            lines_html += f'<div class="{cls}">{safe}</div>'
        log_placeholder.markdown(
            f'<div class="log-box">{lines_html}</div>',
            unsafe_allow_html=True
        )

    render_log()


# ── Run pipeline on submit ───────────────────────────────────────────
if submitted:
    if not rule_num.strip() or not description.strip():
        st.error("Both rule number and description are required.")
    else:
        st.session_state.log_lines = []
        st.session_state.last_result = None

        msg_queue = queue.Queue()

        def callback(msg: str):
            msg_queue.put(msg)

        def run_agent():
            result = run_pipeline(
                rule_num=rule_num.strip(),
                description=description.strip(),
                stream_callback=callback,
            )
            msg_queue.put(("__DONE__", result))

        thread = threading.Thread(target=run_agent, daemon=True)
        thread.start()

        with st.spinner("Agent running..."):
            while True:
                try:
                    item = msg_queue.get(timeout=0.3)
                except queue.Empty:
                    if not thread.is_alive():
                        break
                    render_log()
                    continue

                if isinstance(item, tuple) and item[0] == "__DONE__":
                    result = item[1]
                    st.session_state.last_result = result
                    st.session_state.installed_rules.append(result)
                    break

                st.session_state.log_lines.append(item)
                render_log()

        # Final status
        result = st.session_state.last_result
        if result and result["success"]:
            status_placeholder.success(
                f"✅ Rule {rule_num} installed and registered successfully."
            )
        elif result:
            status_placeholder.error(
                f"❌ Installation failed. Check logs in `{cfg.LOG_DIR}/`."
            )
            if result.get("error"):
                st.code(result["error"])

        st.rerun()
```

---

## Step 12 — Modify `install-rule.sh` for Non-Interactive Mode

Add this block at the top of the script, right after the variable declarations:

```bash
# Non-interactive mode: if answers are piped via stdin, use them.
# The script already reads from stdin via 'read', so pexpect handles this
# automatically. No changes needed to the script itself — pexpect
# intercepts each prompt and feeds the answer.
#
# One change required: remove 'set -e' OR add error recovery,
# because pexpect will catch failures via exit code instead.
```

Remove `set -e` from the top and replace with explicit checks:

```bash
# Replace: set -e
# With: (leave it out — agent checks exit codes)
```

---

## Step 13 — Run It

```bash
# From project root
cd tazama-rule-agent

# Run UI
streamlit run ui/app.py --server.port 8501

# Or run agent headlessly (no UI)
python3 -c "
from agent import run_pipeline
result = run_pipeline('030', 'Transfer to unfamiliar creditor account - debtor')
print(result)
"
```

Open browser: `http://localhost:8501`

---

## Step 14 — `requirements.txt`

```txt
streamlit>=1.35.0
openai>=1.30.0
python-dotenv>=1.0.0
rich>=13.0.0
pexpect>=4.9.0
```

---

## Debugging Checklist

| Symptom | Check |
|---|---|
| Stage 1/2/3 wrong output | `logs/run_*.log` → inspect raw OpenAI response |
| Script prompts not matched | `logs/script_run_*.log` → see exact prompt text |
| Timeout on stream detection | Increase `SCRIPT_TIMEOUT` in config.py |
| DB write fails | Check postgres pod logs: `kubectl logs deployment/postgres -n tazama` |
| OpenAI rate limited | Increase `MAX_RETRIES` and backoff in `openai_client.py` |
| UI not streaming | Ensure `stream_callback` queue is being drained in the while loop |

---

## Flow Summary

```
User types: rule_num="030", description="Transfer to unfamiliar..."
     │
     ▼
Stage 1 (OpenAI): → maxQueryRange=86400000, exit_conditions=[{.x00}]
     │
     ▼
Stage 2 (OpenAI): → 3 bands: .01 (new), .02 (limited), .03 (established)
     │
     ▼
Stage 3 (OpenAI): → weights: .err=0, .x00=0, .01=400, .02=200, .03=0
     │
     ▼
Stage 4 (pexpect): → Feeds all answers into install-rule.sh automatically
     │
     ▼
Script: pulls image → deploys pod → detects stream version → writes DB → restarts typology-processor
     │
     ▼
UI: ✅ Rule installed
```