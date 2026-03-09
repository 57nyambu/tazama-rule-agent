# agent.py
# ─────────────────────────────────────────────────────────────────
# Local Intelligence Engine — Orchestrator
# Uses pre-computed rule knowledge (no AI dependency).
# Supports single rule and batch installation.
# ─────────────────────────────────────────────────────────────────
from config import cfg
from utils.logger import get_logger
from rules_knowledge import (
    get_rule, validate_rule_config, ms_to_human, ALREADY_RUNNING
)
from stages import stage4_executor

log = get_logger("agent")


def run_single(rule_num: str, stream_callback=None) -> dict:
    """
    Install a single rule using local knowledge base.
    Looks up config → validates → runs install script.
    Returns result dict.
    """

    def emit(msg: str):
        log.info(msg)
        if stream_callback:
            stream_callback(msg)

    result = {
        "rule_num": rule_num,
        "description": "",
        "success": False,
        "config": None,
        "validation": None,
        "error": None,
    }

    try:
        # ── Lookup ────────────────────────────────────────────────
        emit(f"🔍 Looking up rule-{rule_num} in knowledge base...")
        rule_cfg = get_rule(rule_num)
        if not rule_cfg:
            emit(f"❌ Rule {rule_num} not found in knowledge base")
            result["error"] = f"Rule {rule_num} not in catalog"
            return result

        result["description"] = rule_cfg["description"]
        result["config"] = rule_cfg
        emit(f"  ✓ Found: {rule_cfg['description']}")
        cats = ", ".join(rule_cfg.get("categories", []))
        emit(f"  ℹ Categories: {cats}")

        # ── Check if already running ──────────────────────────────
        if rule_num in ALREADY_RUNNING:
            emit(f"⚠ Rule {rule_num} is already deployed — proceeding with reinstall")

        # ── Validate ──────────────────────────────────────────────
        emit("🔬 Validating configuration...")
        issues = validate_rule_config(rule_num)
        result["validation"] = issues
        if issues:
            for issue in issues:
                emit(f"  ⚠ {issue}")
            emit("❌ Configuration validation failed — aborting")
            result["error"] = f"Validation failed: {'; '.join(issues)}"
            return result
        emit("  ✓ Configuration valid")

        # ── Display config summary ────────────────────────────────
        emit("📋 Configuration summary:")
        emit(f"  Query range: {rule_cfg['maxQueryRange']}ms ({ms_to_human(rule_cfg['maxQueryRange'])})")

        emit(f"  Exit conditions ({len(rule_cfg['exit_conditions'])}):")
        for ec in rule_cfg["exit_conditions"]:
            emit(f"    {ec['subRuleRef']}: {ec['reason']}")

        emit(f"  Bands ({len(rule_cfg['bands'])}):")
        for b in rule_cfg["bands"]:
            limits = []
            if "lowerLimit" in b:
                limits.append(f"≥{b['lowerLimit']}")
            if "upperLimit" in b:
                limits.append(f"<{b['upperLimit']}")
            lim = " ".join(limits) if limits else "—"
            emit(f"    {b['subRuleRef']} [{lim}]: {b['reason']}")

        emit(f"  Weights ({len(rule_cfg['weights'])}):")
        for w in rule_cfg["weights"]:
            bar = "█" * (int(w["wght"]) // 100) if w["wght"] != "0" else "○"
            emit(f"    {w['ref']} → {w['wght']} {bar}")

        # ── Execute install script ────────────────────────────────
        emit(f"🚀 Running install-rule.sh for rule-{rule_num}...")
        success = stage4_executor.run(
            rule_num=rule_num,
            image_tag=cfg.IMAGE_TAG,
            description=rule_cfg["description"],
            bands=rule_cfg["bands"],
            exit_conditions=rule_cfg["exit_conditions"],
            weights=rule_cfg["weights"],
            stream_callback=stream_callback,
        )

        result["success"] = success
        if success:
            emit(f"✅ Rule {rule_num} ({rule_cfg['description']}) installed successfully!")
        else:
            emit(f"❌ Script execution failed for rule-{rule_num}")
            result["error"] = "Install script returned non-zero exit code"

    except Exception as e:
        result["error"] = str(e)
        log.error(f"Pipeline error for rule-{rule_num}: {e}", exc_info=True)
        emit(f"❌ Error installing rule-{rule_num}: {e}")

    return result


def run_batch(rule_nums: list, stream_callback=None) -> dict:
    """
    Install multiple rules in sequence.
    Returns summary dict with per-rule results.
    """

    def emit(msg: str):
        log.info(msg)
        if stream_callback:
            stream_callback(msg)

    batch_result = {
        "total": len(rule_nums),
        "succeeded": 0,
        "failed": 0,
        "skipped": 0,
        "results": {},
    }

    emit(f"{'═' * 50}")
    emit(f"🛡️ Batch Install — {len(rule_nums)} rules queued")
    emit(f"{'═' * 50}")
    emit("")

    for idx, rule_num in enumerate(rule_nums, 1):
        emit(f"{'─' * 50}")
        emit(f"📦 [{idx}/{len(rule_nums)}] Installing rule-{rule_num}...")
        emit(f"{'─' * 50}")

        r = run_single(rule_num, stream_callback=stream_callback)
        batch_result["results"][rule_num] = r

        if r["success"]:
            batch_result["succeeded"] += 1
        elif r.get("error", "").startswith("Rule") and "not in catalog" in r.get("error", ""):
            batch_result["skipped"] += 1
        else:
            batch_result["failed"] += 1

        emit("")

    # ── Final summary ─────────────────────────────────────────────
    emit(f"{'═' * 50}")
    emit(f"📊 BATCH COMPLETE")
    emit(f"{'═' * 50}")
    emit(f"  ✅ Succeeded: {batch_result['succeeded']}")
    emit(f"  ❌ Failed:    {batch_result['failed']}")
    emit(f"  ⏭️  Skipped:   {batch_result['skipped']}")
    emit(f"  📦 Total:     {batch_result['total']}")

    if batch_result["failed"] > 0:
        emit("")
        emit("Failed rules:")
        for rn, r in batch_result["results"].items():
            if not r["success"] and r.get("error"):
                emit(f"  ❌ rule-{rn}: {r['error']}")

    return batch_result
