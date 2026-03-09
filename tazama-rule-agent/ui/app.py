# ui/app.py
import streamlit as st
import threading
import queue
import json
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent import run_pipeline
from config import cfg, AVAILABLE_MODELS, MODEL_IDS
from utils.openai_client import test_connection

st.set_page_config(
    page_title="Tazama Rule Agent",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ──────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&family=Syne:wght@700;800&display=swap');

  html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }
  h1, h2, h3 { font-family: 'Syne', sans-serif; letter-spacing: -0.03em; }
  code, pre, .log-box { font-family: 'JetBrains Mono', monospace; }

  .stApp {
    background: linear-gradient(135deg, #0a0e1a 0%, #0d1321 50%, #0a0f1e 100%);
    color: #e2e8f0;
  }

  /* ── Header ── */
  .hero-title {
    font-family: 'Syne', sans-serif;
    font-size: 2.2rem;
    font-weight: 800;
    background: linear-gradient(135deg, #60a5fa, #a78bfa, #34d399);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.04em;
    margin-bottom: 0;
  }
  .hero-sub {
    color: #64748b;
    font-size: 0.9rem;
    margin-top: 0;
  }

  /* ── Cards ── */
  .glass-card {
    background: rgba(17, 24, 39, 0.7);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(99, 102, 241, 0.15);
    border-radius: 16px;
    padding: 1.5rem;
    margin-bottom: 1rem;
    transition: border-color 0.2s;
  }
  .glass-card:hover {
    border-color: rgba(99, 102, 241, 0.35);
  }

  /* ── Stage badges ── */
  .stage-badge {
    display: inline-block;
    background: linear-gradient(135deg, #1e3a5f, #1e2d45);
    color: #60a5fa;
    font-size: 0.65rem;
    font-weight: 700;
    padding: 3px 12px;
    border-radius: 20px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  /* ── Log box ── */
  .log-box {
    background: rgba(7, 11, 20, 0.9);
    border: 1px solid #1a2744;
    border-radius: 12px;
    padding: 1rem 1.2rem;
    font-size: 0.72rem;
    color: #94a3b8;
    height: 420px;
    overflow-y: auto;
    line-height: 1.8;
    scrollbar-width: thin;
    scrollbar-color: #1e3a5f transparent;
  }
  .log-box::-webkit-scrollbar { width: 6px; }
  .log-box::-webkit-scrollbar-track { background: transparent; }
  .log-box::-webkit-scrollbar-thumb { background: #1e3a5f; border-radius: 3px; }

  .success { color: #34d399; }
  .error   { color: #f87171; }
  .info    { color: #60a5fa; }
  .warn    { color: #fbbf24; }
  .model   { color: #a78bfa; }
  .dim     { color: #475569; }

  /* ── Sidebar ── */
  div[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #080c18 0%, #0a1020 100%);
    border-right: 1px solid rgba(99, 102, 241, 0.1);
  }

  /* ── Status indicators ── */
  .status-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 6px;
    vertical-align: middle;
  }
  .status-ok   { background: #34d399; box-shadow: 0 0 6px rgba(52, 211, 153, 0.5); }
  .status-fail { background: #f87171; box-shadow: 0 0 6px rgba(248, 113, 113, 0.5); }
  .status-idle { background: #475569; }

  /* ── Model tier badges ── */
  .tier-fast      { background: #064e3b; color: #34d399; }
  .tier-balanced  { background: #1e3a5f; color: #60a5fa; }
  .tier-quality   { background: #3b0764; color: #c084fc; }
  .tier-reasoning { background: #78350f; color: #fbbf24; }
  .tier-legacy    { background: #1f2937; color: #6b7280; }
  .tier-badge {
    display: inline-block;
    font-size: 0.6rem;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 10px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  /* ── Fix Streamlit button styling ── */
  .stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #4f46e5, #6366f1);
    border: none;
    border-radius: 10px;
    font-weight: 600;
    letter-spacing: 0.02em;
    transition: all 0.2s;
  }
  .stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #6366f1, #818cf8);
    box-shadow: 0 4px 16px rgba(99, 102, 241, 0.3);
  }
</style>
""", unsafe_allow_html=True)


# ── Session state init ──────────────────────────────────────────────
for key, default in {
    "installed_rules": [],
    "log_lines": [],
    "last_result": None,
    "api_status": None,
    "selected_model": cfg.OPENAI_MODEL,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ── Sidebar ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Settings")
    st.markdown("---")

    # ── Model selector ──
    st.markdown("### 🧠 Model Selection")

    model_options = [m["id"] for m in AVAILABLE_MODELS]
    model_labels = []
    for m in AVAILABLE_MODELS:
        tier = m["tier"]
        label = f"{m['label']}  •  {m['tpm']//1000}K TPM"
        model_labels.append(label)

    current_idx = model_options.index(st.session_state.selected_model) \
        if st.session_state.selected_model in model_options else 0

    selected_idx = st.selectbox(
        "Choose model",
        range(len(model_options)),
        index=current_idx,
        format_func=lambda i: model_labels[i],
        help="Select which OpenAI model to use for AI stages (1-3)",
    )
    st.session_state.selected_model = model_options[selected_idx]
    selected_model_info = AVAILABLE_MODELS[selected_idx]

    # Model info card
    tier = selected_model_info["tier"]
    st.markdown(f"""
<div class="glass-card" style="padding: 1rem;">
  <span class="tier-badge tier-{tier}">{tier}</span>
  <div style="margin-top: 8px; font-size: 0.8rem; color: #94a3b8;">
    {selected_model_info['description']}<br>
    <span class="dim">{selected_model_info['tpm']:,} TPM · {selected_model_info['rpm']} RPM · {selected_model_info['rpd']} RPD</span>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── API connectivity test ──
    st.markdown("### 🔌 API Connection")
    if st.button("🧪 Test API Connection", use_container_width=True):
        with st.spinner(f"Testing {st.session_state.selected_model}..."):
            status = test_connection(model=st.session_state.selected_model)
            st.session_state.api_status = status

    if st.session_state.api_status:
        s = st.session_state.api_status
        if s["success"]:
            st.markdown(f"""
<div class="glass-card" style="padding: 0.8rem;">
  <span class="status-dot status-ok"></span>
  <strong style="color: #34d399;">Connected</strong><br>
  <span class="dim" style="font-size: 0.75rem;">
    Model: {s['model']}<br>
    Latency: {s['latency_ms']}ms<br>
    Tokens: {s.get('tokens_used', {}).get('total', '?')}
  </span>
</div>
""", unsafe_allow_html=True)
        else:
            st.markdown(f"""
<div class="glass-card" style="padding: 0.8rem; border-color: rgba(248, 113, 113, 0.3);">
  <span class="status-dot status-fail"></span>
  <strong style="color: #f87171;">Connection Failed</strong><br>
  <span style="font-size: 0.72rem; color: #f87171; word-break: break-all;">
    {s['message'][:200]}
  </span>
</div>
""", unsafe_allow_html=True)

    st.markdown("---")

    # ── Infra config display ──
    st.markdown("### 🏗️ Infrastructure")
    st.markdown(f"""
<div style="font-size: 0.78rem; color: #64748b; line-height: 2;">
  Namespace: <code>{cfg.NAMESPACE}</code><br>
  Image tag: <code>{cfg.IMAGE_TAG}</code><br>
  Typology: <code>{cfg.TYPOLOGY_ID}</code><br>
  Log level: <code>{cfg.LOG_LEVEL}</code>
</div>
""", unsafe_allow_html=True)

    st.markdown("---")

    # ── Installed rules ──
    st.markdown("### 📋 Session History")
    if st.session_state.installed_rules:
        for r in st.session_state.installed_rules:
            icon = "✅" if r.get("success") else "❌"
            model_used = r.get("model", "?")
            st.markdown(
                f"{icon} `rule-{r['rule_num']}` — {model_used}",
            )
    else:
        st.caption("No rules installed this session.")

    st.markdown("---")

    # ── Recent logs ──
    log_dir = cfg.LOG_DIR
    if os.path.isdir(log_dir):
        logs = sorted(os.listdir(log_dir), reverse=True)[:5]
        if logs:
            st.markdown("### 🗂️ Recent Logs")
            for l in logs:
                st.caption(l)


# ── Main Header ─────────────────────────────────────────────────────
st.markdown('<p class="hero-title">🛡️ Tazama Rule Agent</p>', unsafe_allow_html=True)
st.markdown(f'<p class="hero-sub">Autonomous rule installation · Powered by <strong>{st.session_state.selected_model}</strong></p>', unsafe_allow_html=True)
st.markdown("---")

# ── Layout ──────────────────────────────────────────────────────────
col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.markdown("### 🚀 Install a Rule")

    with st.form("rule_form", clear_on_submit=False):
        rule_num = st.text_input(
            "Rule Number",
            placeholder="e.g. 030",
            help="3-digit rule number (e.g. 006, 028, 030)",
        )
        description = st.text_area(
            "Rule Description",
            placeholder="e.g. Transfer to unfamiliar creditor account - debtor",
            height=120,
            help="Human-readable description of the financial crime pattern this rule detects",
        )

        fcol1, fcol2 = st.columns([2, 1])
        with fcol1:
            submitted = st.form_submit_button(
                "🚀 Install Rule",
                use_container_width=True,
                type="primary",
            )
        with fcol2:
            dry_run = st.form_submit_button(
                "🔍 Dry Run (AI only)",
                use_container_width=True,
            )

    # ── Stage output cards ──
    if st.session_state.last_result:
        res = st.session_state.last_result
        st.markdown("### 📊 Stage Outputs")

        if res.get("stage1"):
            with st.expander("🔬 Stage 1 — Rule Metadata", expanded=False):
                s1 = res["stage1"]
                c1, c2 = st.columns(2)
                with c1:
                    qr = s1.get("maxQueryRange", 0)
                    days = qr / 86400000
                    st.metric("Query Range", f"{days:.0f} days", f"{qr:,} ms")
                with c2:
                    st.metric("Exit Conditions", len(s1.get("exit_conditions", [])))
                st.json(s1)

        if res.get("stage2"):
            with st.expander("📊 Stage 2 — Bands", expanded=False):
                s2 = res["stage2"]
                st.metric("Bands", len(s2.get("bands", [])))
                if s2.get("measured_value_explanation"):
                    st.info(f"📐 **Measured value:** {s2['measured_value_explanation']}")
                st.json(s2)

        if res.get("stage3"):
            with st.expander("⚖️ Stage 3 — Weights", expanded=False):
                s3 = res["stage3"]
                st.metric("Weight Entries", len(s3.get("weights", [])))
                st.json(s3)

        if res.get("stage4"):
            with st.expander("🔧 Stage 4 — Script Execution", expanded=False):
                s4 = res["stage4"]
                if s4.get("success"):
                    st.success("Script completed successfully")
                else:
                    st.error("Script execution failed")

with col2:
    st.markdown("### 📡 Live Agent Log")
    log_placeholder = st.empty()
    status_placeholder = st.empty()

    def render_log():
        lines_html = ""
        for line in st.session_state.log_lines[-150:]:
            if "[ERROR]" in line or "❌" in line:
                cls = "error"
            elif "✅" in line or "✓" in line:
                cls = "success"
            elif "▶" in line or "Stage" in line:
                cls = "info"
            elif "[WARN]" in line or "⚠" in line:
                cls = "warn"
            elif "🧠" in line or "model" in line.lower():
                cls = "model"
            elif "ℹ" in line:
                cls = "dim"
            else:
                cls = ""
            safe = line.replace("<", "&lt;").replace(">", "&gt;")
            lines_html += f'<div class="{cls}">{safe}</div>'
        if not lines_html:
            lines_html = '<div class="dim">Waiting for pipeline to start...</div>'
        log_placeholder.markdown(
            f'<div class="log-box">{lines_html}</div>',
            unsafe_allow_html=True
        )

    render_log()


# ── Pipeline execution ───────────────────────────────────────────────
should_run = submitted or dry_run

if should_run:
    if not rule_num or not rule_num.strip() or not description or not description.strip():
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
                model=st.session_state.selected_model,
            )
            msg_queue.put(("__DONE__", result))

        thread = threading.Thread(target=run_agent, daemon=True)
        thread.start()

        action = "Dry run" if dry_run else "Installing"
        with st.spinner(f"{action} with {st.session_state.selected_model}..."):
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
        if result and result.get("success"):
            status_placeholder.success(
                f"✅ Rule {rule_num} installed and registered successfully."
            )
        elif result and result.get("error"):
            status_placeholder.error(
                f"❌ Pipeline error: {result['error'][:300]}"
            )
        elif result:
            status_placeholder.warning(
                f"⚠️ Pipeline completed but script execution failed. Check logs."
            )

        st.rerun()
