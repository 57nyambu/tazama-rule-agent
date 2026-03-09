# ui/app.py
# ─────────────────────────────────────────────────────────────────
# Tazama Rule Agent — Catalog UI
# Local Intelligence Engine: browse, select, and batch-install rules.
# ─────────────────────────────────────────────────────────────────
import streamlit as st
import threading
import queue
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent import run_single, run_batch
from config import cfg
from rules_knowledge import (
    RULE_CATALOG, ALREADY_RUNNING,
    get_installable_rules, get_running_rules,
    validate_rule_config, ms_to_human,
)

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

  .glass-card {
    background: rgba(17, 24, 39, 0.7);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(99, 102, 241, 0.15);
    border-radius: 16px;
    padding: 1.5rem;
    margin-bottom: 1rem;
    transition: border-color 0.2s;
  }
  .glass-card:hover { border-color: rgba(99, 102, 241, 0.35); }

  .log-box {
    background: rgba(7, 11, 20, 0.9);
    border: 1px solid #1a2744;
    border-radius: 12px;
    padding: 1rem 1.2rem;
    font-size: 0.72rem;
    color: #94a3b8;
    height: 520px;
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
  .accent  { color: #a78bfa; }
  .dim     { color: #475569; }

  div[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #080c18 0%, #0a1020 100%);
    border-right: 1px solid rgba(99, 102, 241, 0.1);
  }

  .cat-local         { background: #064e3b; color: #34d399; }
  .cat-international  { background: #1e3a5f; color: #60a5fa; }
  .cat-system         { background: #1f2937; color: #6b7280; }
  .cat-badge {
    display: inline-block;
    font-size: 0.6rem;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 10px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-right: 4px;
  }
  .running-badge {
    display: inline-block;
    background: #064e3b;
    color: #34d399;
    font-size: 0.6rem;
    font-weight: 700;
    padding: 2px 10px;
    border-radius: 10px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .rule-card {
    background: rgba(17, 24, 39, 0.5);
    border: 1px solid rgba(99, 102, 241, 0.1);
    border-radius: 12px;
    padding: 0.8rem 1rem;
    margin-bottom: 0.5rem;
  }
  .rule-card-running {
    background: rgba(6, 78, 59, 0.15);
    border: 1px solid rgba(52, 211, 153, 0.15);
    border-radius: 12px;
    padding: 0.8rem 1rem;
    margin-bottom: 0.5rem;
  }

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

  /* stats row */
  .stat-box {
    background: rgba(17, 24, 39, 0.6);
    border: 1px solid rgba(99, 102, 241, 0.12);
    border-radius: 12px;
    padding: 1rem 1.2rem;
    text-align: center;
  }
  .stat-num {
    font-family: 'Syne', sans-serif;
    font-size: 1.8rem;
    font-weight: 800;
    color: #60a5fa;
    margin: 0;
  }
  .stat-label {
    color: #64748b;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
</style>
""", unsafe_allow_html=True)


# ── Session state ───────────────────────────────────────────────────
for key, default in {
    "installed_rules": [],
    "log_lines": [],
    "batch_result": None,
    "running": False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

installable = get_installable_rules()
running = get_running_rules()


# ── Sidebar ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Configuration")
    st.markdown("---")

    st.markdown("### 🏗️ Infrastructure")
    st.markdown(f"""
<div style="font-size: 0.78rem; color: #64748b; line-height: 2.2;">
  Namespace: <code>{cfg.NAMESPACE}</code><br>
  Image tag: <code>{cfg.IMAGE_TAG}</code><br>
  Typology: <code>{cfg.TYPOLOGY_ID}</code><br>
  PG deploy: <code>{cfg.PG_DEPLOY}</code><br>
  Database:  <code>{cfg.PG_DB}</code><br>
  Script: <code>{cfg.INSTALL_SCRIPT_PATH}</code>
</div>
""", unsafe_allow_html=True)

    st.markdown("---")

    st.markdown("### 📋 Session History")
    if st.session_state.installed_rules:
        for r in st.session_state.installed_rules:
            icon = "✅" if r.get("success") else "❌"
            st.markdown(f"{icon} `rule-{r['rule_num']}`")
    else:
        st.caption("No rules installed this session.")

    st.markdown("---")

    st.markdown("### 🗂️ Log Files")
    log_dir = cfg.LOG_DIR
    if os.path.isdir(log_dir):
        logs = sorted(os.listdir(log_dir), reverse=True)[:5]
        for lf in logs:
            st.caption(lf)
    else:
        st.caption("No logs yet.")

    st.markdown("---")
    st.markdown(
        '<div style="font-size:0.68rem; color:#334155;">'
        'Local Intelligence Engine v2.0<br>'
        'No AI dependency — pre-computed configs'
        '</div>',
        unsafe_allow_html=True,
    )


# ── Header ──────────────────────────────────────────────────────────
st.markdown('<p class="hero-title">🛡️ Tazama Rule Agent</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="hero-sub">Autonomous rule installation · Local Intelligence Engine · '
    'Click to install</p>',
    unsafe_allow_html=True,
)
st.markdown("---")

# ── Stats Row ───────────────────────────────────────────────────────
s1, s2, s3, s4 = st.columns(4)
with s1:
    st.markdown(f'''<div class="stat-box">
        <p class="stat-num">{len(RULE_CATALOG)}</p>
        <p class="stat-label">Total Rules</p></div>''', unsafe_allow_html=True)
with s2:
    st.markdown(f'''<div class="stat-box">
        <p class="stat-num">{len(running)}</p>
        <p class="stat-label">Running</p></div>''', unsafe_allow_html=True)
with s3:
    st.markdown(f'''<div class="stat-box">
        <p class="stat-num" style="color:#a78bfa;">{len(installable)}</p>
        <p class="stat-label">Available to Install</p></div>''', unsafe_allow_html=True)
with s4:
    installed_this_session = sum(
        1 for r in st.session_state.installed_rules if r.get("success")
    )
    st.markdown(f'''<div class="stat-box">
        <p class="stat-num" style="color:#34d399;">{installed_this_session}</p>
        <p class="stat-label">Installed This Session</p></div>''', unsafe_allow_html=True)

st.markdown("")

# ── Main Layout ─────────────────────────────────────────────────────
col_catalog, col_log = st.columns([1, 1], gap="large")

# ── Left Column — Rule Catalog ──────────────────────────────────────
with col_catalog:
    st.markdown("### 📋 Rule Catalog")

    # ── Installable rules with checkboxes ───────────────────────
    st.markdown(
        f'<span style="color:#a78bfa; font-size:0.85rem; font-weight:600;">'
        f'Available to Install ({len(installable)})</span>',
        unsafe_allow_html=True,
    )

    # Select all toggle
    select_all = st.checkbox("Select all rules", key="select_all")

    sorted_installable = sorted(installable.keys())

    for rn in sorted_installable:
        rule = installable[rn]
        cats_html = ""
        for cat in rule.get("categories", []):
            cats_html += f'<span class="cat-badge cat-{cat}">{cat}</span>'
        qr = ms_to_human(rule["maxQueryRange"])
        b_count = len(rule["bands"])
        e_count = len(rule["exit_conditions"])
        w_count = len(rule["weights"])

        cb_col, info_col = st.columns([0.08, 0.92])
        with cb_col:
            st.checkbox(
                f"rule-{rn}",
                value=select_all,
                key=f"rule_{rn}",
                label_visibility="collapsed",
            )
        with info_col:
            st.markdown(f"""
<div class="rule-card">
  <div style="display:flex; align-items:center; justify-content:space-between;">
    <div>
      <strong style="color:#e2e8f0; font-size:0.9rem;">rule-{rn}</strong>
      <span style="color:#64748b; font-size:0.78rem; margin-left:8px;">{rule['description']}</span>
    </div>
    <div>{cats_html}</div>
  </div>
  <div style="margin-top:6px; font-size:0.68rem; color:#475569;">
    📊 {b_count} bands · 🚪 {e_count} exits · ⚖️ {w_count} weights · ⏱️ {qr}
  </div>
</div>""", unsafe_allow_html=True)

    st.markdown("")

    # ── Already running rules ───────────────────────────────────
    st.markdown(
        f'<span style="color:#34d399; font-size:0.85rem; font-weight:600;">'
        f'Already Running ({len(running)})</span>',
        unsafe_allow_html=True,
    )

    for rn in sorted(running.keys()):
        rule = running[rn]
        cats_html = ""
        for cat in rule.get("categories", []):
            cats_html += f'<span class="cat-badge cat-{cat}">{cat}</span>'

        st.markdown(f"""
<div class="rule-card-running">
  <div style="display:flex; align-items:center; justify-content:space-between;">
    <div>
      <span class="running-badge">✓ RUNNING</span>
      <strong style="color:#94a3b8; font-size:0.9rem; margin-left:8px;">rule-{rn}</strong>
      <span style="color:#4b5563; font-size:0.78rem; margin-left:8px;">{rule['description']}</span>
    </div>
    <div>{cats_html}</div>
  </div>
</div>""", unsafe_allow_html=True)

    st.markdown("")

    # ── Install button ──────────────────────────────────────────
    selected = [rn for rn in sorted_installable if st.session_state.get(f"rule_{rn}", False)]

    bcol1, bcol2 = st.columns([3, 1])
    with bcol1:
        install_clicked = st.button(
            f"🚀 Install Selected ({len(selected)} rules)",
            disabled=len(selected) == 0 or st.session_state.running,
            use_container_width=True,
            type="primary",
        )
    with bcol2:
        preview_clicked = st.button(
            "🔍 Preview",
            disabled=len(selected) == 0,
            use_container_width=True,
        )

    # ── Config preview ──────────────────────────────────────────
    if preview_clicked and selected:
        st.markdown("### 🔬 Configuration Preview")
        for rn in selected:
            rule = RULE_CATALOG[rn]
            issues = validate_rule_config(rn)
            valid_icon = "✅" if not issues else "⚠️"
            with st.expander(f"{valid_icon} rule-{rn}: {rule['description']}", expanded=False):
                mc1, mc2, mc3 = st.columns(3)
                with mc1:
                    st.metric("Query Range", ms_to_human(rule["maxQueryRange"]))
                with mc2:
                    st.metric("Bands", len(rule["bands"]))
                with mc3:
                    st.metric("Exit Conditions", len(rule["exit_conditions"]))

                st.markdown("**Bands:**")
                for b in rule["bands"]:
                    limits = []
                    if "lowerLimit" in b:
                        limits.append(f"≥{b['lowerLimit']}")
                    if "upperLimit" in b:
                        limits.append(f"<{b['upperLimit']}")
                    lim = " ".join(limits) or "—"
                    st.markdown(f"- `{b['subRuleRef']}` [{lim}]: {b['reason']}")

                st.markdown("**Exit Conditions:**")
                for ec in rule["exit_conditions"]:
                    st.markdown(f"- `{ec['subRuleRef']}`: {ec['reason']}")

                st.markdown("**Weights:**")
                for w in rule["weights"]:
                    bar = "█" * (int(w["wght"]) // 100) if w["wght"] != "0" else "○"
                    st.markdown(f"- `{w['ref']}` → {w['wght']} {bar}")

                if issues:
                    st.warning("Validation issues:\n" + "\n".join(f"- {i}" for i in issues))


# ── Right Column — Live Log ─────────────────────────────────────────
with col_log:
    st.markdown("### 📡 Live Agent Log")
    log_placeholder = st.empty()
    status_placeholder = st.empty()

    def render_log():
        lines_html = ""
        for line in st.session_state.log_lines[-200:]:
            if "[ERROR]" in line or "❌" in line:
                cls = "error"
            elif "✅" in line or "✓" in line or "COMPLETE" in line:
                cls = "success"
            elif "▶" in line or "📦" in line or "🚀" in line:
                cls = "info"
            elif "[WARN]" in line or "⚠" in line:
                cls = "warn"
            elif "═" in line or "─" in line:
                cls = "accent"
            elif "ℹ" in line or "📋" in line:
                cls = "dim"
            else:
                cls = ""
            safe = line.replace("<", "&lt;").replace(">", "&gt;")
            lines_html += f'<div class="{cls}">{safe}</div>'
        if not lines_html:
            lines_html = '<div class="dim">Select rules from the catalog and click Install...</div>'
        log_placeholder.markdown(
            f'<div class="log-box">{lines_html}</div>',
            unsafe_allow_html=True,
        )

    render_log()


# ── Pipeline Execution ──────────────────────────────────────────────
if install_clicked and selected:
    st.session_state.log_lines = []
    st.session_state.batch_result = None
    st.session_state.running = True

    msg_queue = queue.Queue()

    def callback(msg: str):
        msg_queue.put(msg)

    def run_agent_batch():
        result = run_batch(selected, stream_callback=callback)
        msg_queue.put(("__DONE__", result))

    thread = threading.Thread(target=run_agent_batch, daemon=True)
    thread.start()

    with st.spinner(f"Installing {len(selected)} rules..."):
        while True:
            try:
                item = msg_queue.get(timeout=0.3)
            except queue.Empty:
                if not thread.is_alive():
                    break
                render_log()
                continue

            if isinstance(item, tuple) and item[0] == "__DONE__":
                batch = item[1]
                st.session_state.batch_result = batch
                # Add individual results to session history
                for rn, r in batch.get("results", {}).items():
                    st.session_state.installed_rules.append(r)
                break

            st.session_state.log_lines.append(item)
            render_log()

    st.session_state.running = False

    # Final summary
    batch = st.session_state.batch_result
    if batch:
        if batch["failed"] == 0 and batch["succeeded"] > 0:
            status_placeholder.success(
                f"✅ All {batch['succeeded']} rules installed successfully!"
            )
        elif batch["succeeded"] > 0:
            status_placeholder.warning(
                f"⚠️ {batch['succeeded']} succeeded, {batch['failed']} failed. Check logs."
            )
        else:
            status_placeholder.error(
                f"❌ Installation failed. {batch['failed']} rules failed."
            )

    st.rerun()
