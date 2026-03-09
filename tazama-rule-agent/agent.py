# agent.py
# Runs all 4 stages in sequence with full error handling.
# Supports dynamic model selection per run.
from config import cfg
from utils.logger import get_logger
from stages import stage1_rule_info, stage2_bands, stage3_weights, stage4_executor

log = get_logger("agent")


def run_pipeline(rule_num: str, description: str,
                 stream_callback=None, model: str = None) -> dict:
    """
    Full pipeline: Stage1 → Stage2 → Stage3 → Stage4
    stream_callback(msg: str) used to push progress to UI.
    model: override which OpenAI model to use for stages 1-3.
    Returns result dict with success flag and all stage outputs.
    """
    model = model or cfg.OPENAI_MODEL

    def emit(msg: str):
        log.info(msg)
        if stream_callback:
            stream_callback(msg)

    result = {
        "rule_num": rule_num,
        "description": description,
        "model": model,
        "success": False,
        "stage1": None,
        "stage2": None,
        "stage3": None,
        "stage4": None,
        "error": None,
    }

    try:
        emit(f"🧠 Using model: {model}")

        # ── Stage 1 ──────────────────────────────────────────────
        emit("▶ Stage 1 — Analyzing rule & determining metadata...")
        s1 = stage1_rule_info.run(rule_num, description, model=model)
        result["stage1"] = s1
        emit(f"  ✓ maxQueryRange: {s1['maxQueryRange']}ms ({_ms_to_human(s1['maxQueryRange'])})")
        emit(f"  ✓ Exit conditions: {len(s1['exit_conditions'])}")
        for ec in s1["exit_conditions"]:
            emit(f"    {ec['subRuleRef']}: {ec['reason']}")

        # ── Stage 2 ──────────────────────────────────────────────
        emit("▶ Stage 2 — Generating band configuration...")
        s2 = stage2_bands.run(rule_num, description, s1["exit_conditions"], model=model)
        result["stage2"] = s2
        emit(f"  ✓ {len(s2['bands'])} bands generated")
        if s2.get("measured_value_explanation"):
            emit(f"  ℹ Measured value: {s2['measured_value_explanation']}")
        for b in s2["bands"]:
            limits = []
            if "lowerLimit" in b:
                limits.append(f"lower={b['lowerLimit']}")
            if "upperLimit" in b:
                limits.append(f"upper={b['upperLimit']}")
            limit_str = f" ({', '.join(limits)})" if limits else ""
            emit(f"    {b['subRuleRef']}: {b['reason']}{limit_str}")

        # ── Stage 3 ──────────────────────────────────────────────
        emit("▶ Stage 3 — Generating typology weights...")
        s3 = stage3_weights.run(
            rule_num, description,
            s2["bands"], s1["exit_conditions"],
            model=model,
        )
        result["stage3"] = s3
        emit(f"  ✓ {len(s3['weights'])} weight entries")
        for w in s3["weights"]:
            emit(f"    {w['ref']} → {w['wght']}")

        # ── Cross-stage validation ────────────────────────────────
        emit("▶ Validating cross-stage consistency...")
        issues = _validate_outputs(s1, s2, s3)
        if issues:
            for issue in issues:
                emit(f"  ⚠ {issue}")
        else:
            emit("  ✓ All outputs consistent")

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


def _ms_to_human(ms: int) -> str:
    """Convert milliseconds to human-readable string."""
    seconds = ms / 1000
    if seconds < 3600:
        return f"{seconds / 60:.0f} minutes"
    elif seconds < 86400:
        return f"{seconds / 3600:.0f} hours"
    elif seconds < 2592000:
        return f"{seconds / 86400:.0f} days"
    else:
        return f"{seconds / 2592000:.0f} months"


def _validate_outputs(s1: dict, s2: dict, s3: dict) -> list:
    """Cross-validate outputs from all three AI stages."""
    issues = []
    band_refs = {b["subRuleRef"] for b in s2.get("bands", [])}
    exit_refs = {e["subRuleRef"] for e in s1.get("exit_conditions", [])}
    weight_refs = {w["ref"] for w in s3.get("weights", [])}

    all_required = {".err"} | exit_refs | band_refs

    # Check all refs have weights
    missing_weights = all_required - weight_refs
    if missing_weights:
        issues.append(f"Missing weight entries for: {missing_weights}")

    # Check for extra weights
    extra_weights = weight_refs - all_required
    if extra_weights:
        issues.append(f"Extra weight entries (no matching ref): {extra_weights}")

    # Check band ordering
    bands = s2.get("bands", [])
    for i in range(len(bands) - 1):
        upper = bands[i].get("upperLimit")
        lower = bands[i + 1].get("lowerLimit")
        if upper is not None and lower is not None and upper != lower:
            issues.append(f"Band boundary gap: .0{i+1} upper={upper} vs .0{i+2} lower={lower}")

    # Check weight ordering (higher risk = higher weight)
    band_weights = [(w["ref"], int(w["wght"])) for w in s3.get("weights", [])
                    if w["ref"] in band_refs]
    band_weights.sort(key=lambda x: x[0])
    for i in range(len(band_weights) - 1):
        if band_weights[i][1] < band_weights[i + 1][1]:
            issues.append(
                f"Weight inversion: {band_weights[i][0]}={band_weights[i][1]} "
                f"< {band_weights[i+1][0]}={band_weights[i+1][1]}"
            )

    return issues
