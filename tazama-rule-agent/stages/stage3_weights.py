# stages/stage3_weights.py
# Task: Generate typology weights for each subRuleRef with validation.
from utils.openai_client import ask
from utils.logger import get_logger

log = get_logger("stage3")

SYSTEM = """
You are a senior financial crime detection architect for the Tazama open-source
real-time transaction monitoring system.

You output ONLY valid JSON. No prose. No markdown. No explanation.

Your task: generate typology weights that map each possible rule output to a
risk score used by the typology processor.

WEIGHT RULES (critical — follow exactly):
- EVERY possible subRuleRef the rule can return MUST have exactly one weight entry.
- Required entries: .err, ALL exit condition refs (.x00, .x01...), ALL band refs (.01, .02...)
- .err weight is ALWAYS "0" (error = no signal)
- Exit condition weights (.x00, .x01...) are ALWAYS "0" (no signal)
- Band .01 (most suspicious) gets the HIGHEST weight
- Band weights DECREASE as band number increases (.01 > .02 > .03...)
- Last band (least suspicious / normal behavior) should be "0"
- Weight scale: use multiples of 100 → "0", "100", "200", "300", "400"
- ALL weight values MUST be strings, not integers

ORDERING:
- List .err first, then exit conditions in order, then bands in order.
"""


def run(rule_num: str, description: str, bands: list, exit_conditions: list,
        model: str = None) -> dict:
    log.info(f"Stage 3 — Generating weights for rule-{rule_num}")

    band_refs = [b["subRuleRef"] for b in bands]
    exit_refs = [e["subRuleRef"] for e in exit_conditions]
    all_required = [".err"] + exit_refs + band_refs

    result = ask(
        system_prompt=SYSTEM,
        user_prompt=f"""
Rule number: {rule_num}
Description: {description}

All subRuleRefs this rule can return (every one needs a weight):
- .err (error case)
- Exit conditions: {exit_refs}
- Band results (in order, .01 = most suspicious): {band_refs}

Total entries needed: {len(all_required)}

Return JSON (strict schema):
{{
  "weights": [
    {{"ref": ".err",  "wght": "0"}},
    {{"ref": ".x00",  "wght": "0"}},
    {{"ref": ".01",   "wght": "400"}},
    {{"ref": ".02",   "wght": "200"}},
    {{"ref": ".03",   "wght": "0"}}
  ]
}}
""",
        label="stage3",
        model=model,
    )

    # ── Validate & enforce completeness ──
    weights = result.get("weights", [])
    weight_refs = {w["ref"] for w in weights}

    # Ensure all required refs are present
    for ref in all_required:
        if ref not in weight_refs:
            if ref == ".err" or ref.startswith(".x"):
                weights.append({"ref": ref, "wght": "0"})
                log.warning(f"Stage 3: Added missing weight for {ref} = 0")
            else:
                # Band ref missing — assign declining weight
                band_idx = band_refs.index(ref)
                max_w = len(band_refs) - 1
                wght = str((max_w - band_idx) * 100) if band_idx < max_w else "0"
                weights.append({"ref": ref, "wght": wght})
                log.warning(f"Stage 3: Added missing weight for {ref} = {wght}")

    # Ensure all weights are strings
    for w in weights:
        if not isinstance(w["wght"], str):
            w["wght"] = str(w["wght"])
            log.warning(f"Stage 3: Converted weight for {w['ref']} to string")

    # Ensure .err and exit conditions are 0
    for w in weights:
        if (w["ref"] == ".err" or w["ref"].startswith(".x")) and w["wght"] != "0":
            log.warning(f"Stage 3: Forced {w['ref']} weight to 0 (was {w['wght']})")
            w["wght"] = "0"

    # Sort: .err first, then .x refs, then band refs
    def sort_key(w):
        ref = w["ref"]
        if ref == ".err":
            return (0, ref)
        elif ref.startswith(".x"):
            return (1, ref)
        else:
            return (2, ref)

    weights.sort(key=sort_key)
    result["weights"] = weights

    log.info(f"Stage 3 result: {len(weights)} weight entries")
    return result
