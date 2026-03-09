# stages/stage1_rule_info.py
# Task: Given rule number + description, determine:
#   - maxQueryRange
#   - number of exit conditions and their refs/reasons
# Produces validated, consistent metadata.
from utils.openai_client import ask
from utils.logger import get_logger

log = get_logger("stage1")

SYSTEM = """
You are a senior financial crime detection architect for the Tazama open-source
real-time transaction monitoring system. You have deep expertise in AML/CFT rules,
typology patterns, and the Tazama rule processor framework.

You output ONLY valid JSON. No prose. No markdown. No explanation.

Your task: analyze a rule's number and description to produce precise metadata.

DECISION FRAMEWORK for maxQueryRange (milliseconds):
- Rules about single-transaction properties (amount, party checks): 86400000 (1 day)
- Rules about short-term patterns (velocity, frequency): 604800000 (7 days)
- Rules about relationship/history patterns (dormancy, familiarity): 2592000000 (30 days)
- Rules about long-term behavioral analysis: 7776000000 (90 days)
- Choose the MINIMUM range that captures the rule's detection logic.

DECISION FRAMEWORK for exit_conditions:
- .x00 MUST ALWAYS be included with reason: "Incoming transaction is unsuccessful"
  (every rule validates transaction success first).
- Add .x01 if the rule requires a specific precondition that may not be met
  (e.g., "No historical transactions found", "Creditor account not found").
- Add .x02+ only for additional distinct early-exit scenarios.
- Each exit condition = a case where the rule CANNOT produce a band result.
- Exit reasons must be specific and actionable, not vague.
- Keep exit condition count realistic: most rules have 1-2, complex rules 3 max.
"""


def run(rule_num: str, description: str, model: str = None) -> dict:
    log.info(f"Stage 1 — Determining rule metadata for rule-{rule_num}")

    result = ask(
        system_prompt=SYSTEM,
        user_prompt=f"""
Rule number: {rule_num}
Description: {description}

Analyze this rule carefully. Think about:
1. What time window is needed to evaluate this rule's conditions?
2. What preconditions must be true for the rule to produce a meaningful band result?
3. Under what circumstances should the rule exit early without scoring?

Return JSON (strict schema — no extra fields):
{{
  "maxQueryRange": <integer_milliseconds>,
  "exit_conditions": [
    {{"reason": "Incoming transaction is unsuccessful", "subRuleRef": ".x00"}},
    {{"reason": "<specific_precondition_failure>", "subRuleRef": ".x01"}}
  ]
}}
""",
        label="stage1",
        model=model,
    )

    # ── Validate & enforce invariants ──
    if "maxQueryRange" not in result:
        result["maxQueryRange"] = 86400000
        log.warning("Stage 1: maxQueryRange missing — defaulted to 86400000")

    if "exit_conditions" not in result or not result["exit_conditions"]:
        result["exit_conditions"] = [
            {"reason": "Incoming transaction is unsuccessful", "subRuleRef": ".x00"}
        ]
        log.warning("Stage 1: exit_conditions missing — added default .x00")

    # Ensure .x00 always exists
    refs = [ec["subRuleRef"] for ec in result["exit_conditions"]]
    if ".x00" not in refs:
        result["exit_conditions"].insert(
            0, {"reason": "Incoming transaction is unsuccessful", "subRuleRef": ".x00"}
        )
        log.warning("Stage 1: .x00 was missing — injected")

    # Validate subRuleRef format
    for ec in result["exit_conditions"]:
        ref = ec.get("subRuleRef", "")
        if not ref.startswith(".x"):
            log.warning(f"Stage 1: suspicious exit ref '{ref}' — expected .x## format")

    log.info(f"Stage 1 result: {result}")
    return result
