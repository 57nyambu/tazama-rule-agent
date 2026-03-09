# stages/stage2_bands.py
# Task: Generate band configuration with validation.
from utils.openai_client import ask
from utils.logger import get_logger

log = get_logger("stage2")

SYSTEM = """
You are a senior financial crime detection architect for the Tazama open-source
real-time transaction monitoring system.

You output ONLY valid JSON. No prose. No markdown. No explanation.

Your task: generate band configuration for a rule processor.

BAND STRUCTURE (critical — follow exactly):
- Bands partition a SINGLE continuous measured value into risk tiers.
- .01 = highest risk (most suspicious behavior)
- .02, .03 etc = decreasing risk levels
- Typically 2-4 bands. Never more than 5.

BAND LIMIT RULES (strict):
- FIRST band (.01): has "upperLimit" ONLY. No "lowerLimit" field at all.
- MIDDLE bands: have BOTH "lowerLimit" AND "upperLimit".
- LAST band: has "lowerLimit" ONLY. No "upperLimit" field at all.
- If only 2 bands: first has upperLimit only, second has lowerLimit only.
- Band boundaries must be CONTIGUOUS: band N's upperLimit = band N+1's lowerLimit.
- All limits are integers.

MEASURED VALUE EXAMPLES:
- Count rules: number of transactions (0, 1, 2, 5, 10...)
- Amount rules: transaction value or aggregated amount
- Time rules: days since last activity (0, 7, 30, 90...)
- Frequency rules: transactions per time period

Determine the measured value from the rule description, then create bands
with sensible thresholds for financial crime detection.
"""


def run(rule_num: str, description: str, exit_conditions: list,
        model: str = None) -> dict:
    log.info(f"Stage 2 — Generating bands for rule-{rule_num}")

    result = ask(
        system_prompt=SYSTEM,
        user_prompt=f"""
Rule number: {rule_num}
Description: {description}
Exit conditions already defined: {exit_conditions}

Steps:
1. Identify what value this rule measures (count, amount, days, etc.)
2. Determine appropriate threshold boundaries for suspicious vs normal behavior
3. Create 2-4 bands with .01 being the most suspicious

Return JSON (strict schema):
{{
  "bands": [
    {{"reason": "<why_this_band_is_suspicious>", "subRuleRef": ".01", "upperLimit": <int>}},
    {{"reason": "<description>", "subRuleRef": ".02", "lowerLimit": <int>, "upperLimit": <int>}},
    {{"reason": "<why_this_band_is_less_suspicious>", "subRuleRef": ".03", "lowerLimit": <int>}}
  ],
  "measured_value_explanation": "what value is being measured and why these thresholds"
}}
""",
        label="stage2",
        model=model,
    )

    # ── Validate & fix band structure ──
    bands = result.get("bands", [])
    if not bands:
        raise RuntimeError("Stage 2: No bands generated")

    for i, band in enumerate(bands):
        # Ensure subRuleRef is correct sequential format
        expected_ref = f".0{i+1}" if i + 1 < 10 else f".{i+1}"
        if band.get("subRuleRef") != expected_ref:
            log.warning(f"Stage 2: Fixed band {i} ref from '{band.get('subRuleRef')}' to '{expected_ref}'")
            band["subRuleRef"] = expected_ref

        # Enforce limit rules
        if i == 0 and "lowerLimit" in band:
            del band["lowerLimit"]
            log.warning("Stage 2: Removed lowerLimit from first band")
        if i == len(bands) - 1 and "upperLimit" in band:
            del band["upperLimit"]
            log.warning("Stage 2: Removed upperLimit from last band")
        if 0 < i < len(bands) - 1:
            if "lowerLimit" not in band or "upperLimit" not in band:
                log.warning(f"Stage 2: Middle band {i} missing limits")

    # Verify contiguity
    for i in range(len(bands) - 1):
        upper = bands[i].get("upperLimit")
        lower = bands[i + 1].get("lowerLimit")
        if upper is not None and lower is not None and upper != lower:
            log.warning(f"Stage 2: Band boundary gap — band {i} upper={upper}, band {i+1} lower={lower}. Fixing.")
            bands[i + 1]["lowerLimit"] = upper

    result["bands"] = bands
    log.info(f"Stage 2 result: {len(bands)} bands generated")
    return result
