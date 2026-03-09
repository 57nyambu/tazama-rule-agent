# rules_knowledge.py
# ─────────────────────────────────────────────────────────────────
# Local Intelligence Engine — Complete rule catalog with pre-computed
# configurations. Replaces AI-based stages 1-3 with expert-defined
# rule metadata, band configurations, and typology weights.
#
# Each rule entry contains everything needed to feed install-rule.sh:
#   - description, categories, maxQueryRange
#   - exit_conditions (with subRuleRef and reason)
#   - bands (properly structured: first=upperLimit only, last=lowerLimit only)
#   - weights (all refs covered, strings, .err/.x##=0, .01=highest)
# ─────────────────────────────────────────────────────────────────

# Rules already deployed in the cluster (from kubectl get pods)
ALREADY_RUNNING = {"002", "003", "006", "007", "010", "030", "901", "902"}

# ─── Full Rule Catalog ──────────────────────────────────────────

RULE_CATALOG = {

    # ════════════════════════════════════════════════════════════
    #  ALREADY RUNNING — included for reference / re-deployment
    # ════════════════════════════════════════════════════════════

    "002": {
        "description": "Transaction convergence - debtor",
        "categories": ["local", "international"],
        "maxQueryRange": 604800000,  # 7 days
        "exit_conditions": [
            {"reason": "Incoming transaction is unsuccessful", "subRuleRef": ".x00"},
        ],
        "bands": [
            {"reason": "High convergence - multiple sources funneling to debtor account", "subRuleRef": ".01", "upperLimit": 3},
            {"reason": "Moderate convergence pattern detected in debtor inflows", "subRuleRef": ".02", "lowerLimit": 3, "upperLimit": 8},
            {"reason": "Normal inflow pattern - no convergence indicators", "subRuleRef": ".03", "lowerLimit": 8},
        ],
        "weights": [
            {"ref": ".err", "wght": "0"},
            {"ref": ".x00", "wght": "0"},
            {"ref": ".01",  "wght": "400"},
            {"ref": ".02",  "wght": "200"},
            {"ref": ".03",  "wght": "0"},
        ],
    },

    "003": {
        "description": "Account dormancy - creditor",
        "categories": ["local"],
        "maxQueryRange": 7776000000,  # 90 days
        "exit_conditions": [
            {"reason": "Incoming transaction is unsuccessful", "subRuleRef": ".x00"},
        ],
        "bands": [
            {"reason": "Fully dormant creditor account reactivated - no incoming activity in period", "subRuleRef": ".01", "upperLimit": 2},
            {"reason": "Semi-dormant creditor account - minimal incoming transactions", "subRuleRef": ".02", "lowerLimit": 2, "upperLimit": 10},
            {"reason": "Active creditor account - regular incoming transaction history", "subRuleRef": ".03", "lowerLimit": 10},
        ],
        "weights": [
            {"ref": ".err", "wght": "0"},
            {"ref": ".x00", "wght": "0"},
            {"ref": ".01",  "wght": "400"},
            {"ref": ".02",  "wght": "200"},
            {"ref": ".03",  "wght": "0"},
        ],
    },

    "006": {
        "description": "Outgoing transfer similarity - amounts",
        "categories": ["local", "international"],
        "maxQueryRange": 604800000,  # 7 days
        "exit_conditions": [
            {"reason": "Incoming transaction is unsuccessful", "subRuleRef": ".x00"},
            {"reason": "No historical outgoing transactions for comparison", "subRuleRef": ".x01"},
        ],
        "bands": [
            {"reason": "Very low amount variance - repetitive identical/near-identical amounts (structuring)", "subRuleRef": ".01", "upperLimit": 5},
            {"reason": "Moderate amount clustering - some pattern repetition detected", "subRuleRef": ".02", "lowerLimit": 5, "upperLimit": 20},
            {"reason": "Normal amount diversity - no structuring pattern", "subRuleRef": ".03", "lowerLimit": 20},
        ],
        "weights": [
            {"ref": ".err", "wght": "0"},
            {"ref": ".x00", "wght": "0"},
            {"ref": ".x01", "wght": "0"},
            {"ref": ".01",  "wght": "400"},
            {"ref": ".02",  "wght": "200"},
            {"ref": ".03",  "wght": "0"},
        ],
    },

    "007": {
        "description": "Account type inconsistency",
        "categories": ["local"],
        "maxQueryRange": 86400000,  # 1 day
        "exit_conditions": [
            {"reason": "Incoming transaction is unsuccessful", "subRuleRef": ".x00"},
        ],
        "bands": [
            {"reason": "Account type significantly inconsistent with transaction pattern", "subRuleRef": ".01", "upperLimit": 2},
            {"reason": "Minor account type irregularity detected", "subRuleRef": ".02", "lowerLimit": 2, "upperLimit": 5},
            {"reason": "Account type consistent with transaction activity", "subRuleRef": ".03", "lowerLimit": 5},
        ],
        "weights": [
            {"ref": ".err", "wght": "0"},
            {"ref": ".x00", "wght": "0"},
            {"ref": ".01",  "wght": "300"},
            {"ref": ".02",  "wght": "100"},
            {"ref": ".03",  "wght": "0"},
        ],
    },

    "010": {
        "description": "Increased account activity: volume - debtor",
        "categories": ["local", "international"],
        "maxQueryRange": 604800000,  # 7 days
        "exit_conditions": [
            {"reason": "Incoming transaction is unsuccessful", "subRuleRef": ".x00"},
            {"reason": "Insufficient historical data for debtor activity baseline", "subRuleRef": ".x01"},
        ],
        "bands": [
            {"reason": "Extreme spike in outgoing volume vs historical baseline", "subRuleRef": ".01", "upperLimit": 3},
            {"reason": "Moderate increase in outgoing activity compared to baseline", "subRuleRef": ".02", "lowerLimit": 3, "upperLimit": 7},
            {"reason": "Outgoing activity within normal historical range", "subRuleRef": ".03", "lowerLimit": 7},
        ],
        "weights": [
            {"ref": ".err", "wght": "0"},
            {"ref": ".x00", "wght": "0"},
            {"ref": ".x01", "wght": "0"},
            {"ref": ".01",  "wght": "400"},
            {"ref": ".02",  "wght": "200"},
            {"ref": ".03",  "wght": "0"},
        ],
    },

    "030": {
        "description": "Transfer to unfamiliar creditor account - debtor",
        "categories": ["international"],
        "maxQueryRange": 2592000000,  # 30 days
        "exit_conditions": [
            {"reason": "Incoming transaction is unsuccessful", "subRuleRef": ".x00"},
        ],
        "bands": [
            {"reason": "First-ever transaction to this creditor - completely unfamiliar", "subRuleRef": ".01", "upperLimit": 1},
            {"reason": "Very few prior transactions with creditor - limited familiarity", "subRuleRef": ".02", "lowerLimit": 1, "upperLimit": 5},
            {"reason": "Established relationship with creditor account", "subRuleRef": ".03", "lowerLimit": 5},
        ],
        "weights": [
            {"ref": ".err", "wght": "0"},
            {"ref": ".x00", "wght": "0"},
            {"ref": ".01",  "wght": "400"},
            {"ref": ".02",  "wght": "200"},
            {"ref": ".03",  "wght": "0"},
        ],
    },

    "901": {
        "description": "System rule - network scoring baseline",
        "categories": ["system"],
        "maxQueryRange": 86400000,
        "exit_conditions": [
            {"reason": "Incoming transaction is unsuccessful", "subRuleRef": ".x00"},
        ],
        "bands": [
            {"reason": "Network anomaly detected", "subRuleRef": ".01", "upperLimit": 5},
            {"reason": "Minor network deviation", "subRuleRef": ".02", "lowerLimit": 5, "upperLimit": 15},
            {"reason": "Normal network behavior", "subRuleRef": ".03", "lowerLimit": 15},
        ],
        "weights": [
            {"ref": ".err", "wght": "0"},
            {"ref": ".x00", "wght": "0"},
            {"ref": ".01",  "wght": "300"},
            {"ref": ".02",  "wght": "100"},
            {"ref": ".03",  "wght": "0"},
        ],
    },

    "902": {
        "description": "System rule - statistical baseline validation",
        "categories": ["system"],
        "maxQueryRange": 86400000,
        "exit_conditions": [
            {"reason": "Incoming transaction is unsuccessful", "subRuleRef": ".x00"},
        ],
        "bands": [
            {"reason": "Statistical baseline violation", "subRuleRef": ".01", "upperLimit": 3},
            {"reason": "Minor statistical deviation", "subRuleRef": ".02", "lowerLimit": 3, "upperLimit": 10},
            {"reason": "Within statistical norms", "subRuleRef": ".03", "lowerLimit": 10},
        ],
        "weights": [
            {"ref": ".err", "wght": "0"},
            {"ref": ".x00", "wght": "0"},
            {"ref": ".01",  "wght": "200"},
            {"ref": ".02",  "wght": "100"},
            {"ref": ".03",  "wght": "0"},
        ],
    },

    # ════════════════════════════════════════════════════════════
    #  TO INSTALL — Local Transaction Rules
    # ════════════════════════════════════════════════════════════

    "004": {
        "description": "Account dormancy - debtor",
        "categories": ["local"],
        "maxQueryRange": 7776000000,  # 90 days
        "exit_conditions": [
            {"reason": "Incoming transaction is unsuccessful", "subRuleRef": ".x00"},
        ],
        "bands": [
            {"reason": "Fully dormant debtor account reactivated - no outgoing activity in monitoring period", "subRuleRef": ".01", "upperLimit": 2},
            {"reason": "Semi-dormant debtor account - minimal outgoing transaction activity", "subRuleRef": ".02", "lowerLimit": 2, "upperLimit": 10},
            {"reason": "Active debtor account - regular outgoing transaction pattern", "subRuleRef": ".03", "lowerLimit": 10},
        ],
        "weights": [
            {"ref": ".err", "wght": "0"},
            {"ref": ".x00", "wght": "0"},
            {"ref": ".01",  "wght": "400"},
            {"ref": ".02",  "wght": "200"},
            {"ref": ".03",  "wght": "0"},
        ],
    },

    "011": {
        "description": "Increased account activity: volume - creditor",
        "categories": ["local"],
        "maxQueryRange": 604800000,  # 7 days
        "exit_conditions": [
            {"reason": "Incoming transaction is unsuccessful", "subRuleRef": ".x00"},
            {"reason": "Insufficient historical data for creditor activity baseline", "subRuleRef": ".x01"},
        ],
        "bands": [
            {"reason": "Extreme spike in incoming volume vs historical baseline", "subRuleRef": ".01", "upperLimit": 3},
            {"reason": "Moderate increase in incoming activity compared to baseline", "subRuleRef": ".02", "lowerLimit": 3, "upperLimit": 7},
            {"reason": "Incoming activity within normal historical range", "subRuleRef": ".03", "lowerLimit": 7},
        ],
        "weights": [
            {"ref": ".err", "wght": "0"},
            {"ref": ".x00", "wght": "0"},
            {"ref": ".x01", "wght": "0"},
            {"ref": ".01",  "wght": "400"},
            {"ref": ".02",  "wght": "200"},
            {"ref": ".03",  "wght": "0"},
        ],
    },

    # ════════════════════════════════════════════════════════════
    #  TO INSTALL — Shared Local + International Rules
    # ════════════════════════════════════════════════════════════

    "017": {
        "description": "Transaction divergence - debtor",
        "categories": ["local", "international"],
        "maxQueryRange": 604800000,  # 7 days
        "exit_conditions": [
            {"reason": "Incoming transaction is unsuccessful", "subRuleRef": ".x00"},
        ],
        "bands": [
            {"reason": "High transaction divergence - funds dispersed to many unique recipients (layering)", "subRuleRef": ".01", "upperLimit": 3},
            {"reason": "Moderate outgoing divergence pattern detected", "subRuleRef": ".02", "lowerLimit": 3, "upperLimit": 8},
            {"reason": "Normal outgoing distribution - concentrated to known recipients", "subRuleRef": ".03", "lowerLimit": 8},
        ],
        "weights": [
            {"ref": ".err", "wght": "0"},
            {"ref": ".x00", "wght": "0"},
            {"ref": ".01",  "wght": "400"},
            {"ref": ".02",  "wght": "200"},
            {"ref": ".03",  "wght": "0"},
        ],
    },

    "018": {
        "description": "Exceptionally large outgoing transfer - debtor",
        "categories": ["local", "international"],
        "maxQueryRange": 2592000000,  # 30 days
        "exit_conditions": [
            {"reason": "Incoming transaction is unsuccessful", "subRuleRef": ".x00"},
            {"reason": "Insufficient outgoing transaction history for debtor", "subRuleRef": ".x01"},
        ],
        "bands": [
            {"reason": "Exceptionally large transfer - no similar historical amounts (extreme outlier)", "subRuleRef": ".01", "upperLimit": 2},
            {"reason": "Unusually large transfer - few similar historical transactions", "subRuleRef": ".02", "lowerLimit": 2, "upperLimit": 5},
            {"reason": "Transfer amount within normal historical range for debtor", "subRuleRef": ".03", "lowerLimit": 5},
        ],
        "weights": [
            {"ref": ".err", "wght": "0"},
            {"ref": ".x00", "wght": "0"},
            {"ref": ".x01", "wght": "0"},
            {"ref": ".01",  "wght": "400"},
            {"ref": ".02",  "wght": "200"},
            {"ref": ".03",  "wght": "0"},
        ],
    },

    "020": {
        "description": "Large transaction amount vs history - creditor",
        "categories": ["local", "international"],
        "maxQueryRange": 2592000000,  # 30 days
        "exit_conditions": [
            {"reason": "Incoming transaction is unsuccessful", "subRuleRef": ".x00"},
            {"reason": "No incoming transaction history for creditor account", "subRuleRef": ".x01"},
        ],
        "bands": [
            {"reason": "Incoming amount unprecedented - far exceeds any historical transaction for creditor", "subRuleRef": ".01", "upperLimit": 2},
            {"reason": "Incoming amount unusually large - exceeds most historical transactions", "subRuleRef": ".02", "lowerLimit": 2, "upperLimit": 5},
            {"reason": "Incoming amount within creditor's normal historical range", "subRuleRef": ".03", "lowerLimit": 5},
        ],
        "weights": [
            {"ref": ".err", "wght": "0"},
            {"ref": ".x00", "wght": "0"},
            {"ref": ".x01", "wght": "0"},
            {"ref": ".01",  "wght": "400"},
            {"ref": ".02",  "wght": "200"},
            {"ref": ".03",  "wght": "0"},
        ],
    },

    "024": {
        "description": "Non-commissioned transaction mirroring - creditor",
        "categories": ["local", "international"],
        "maxQueryRange": 86400000,  # 1 day
        "exit_conditions": [
            {"reason": "Incoming transaction is unsuccessful", "subRuleRef": ".x00"},
        ],
        "bands": [
            {"reason": "Rapid mirror detected - matching outbound within 30 minutes of inbound (echo transaction)", "subRuleRef": ".01", "upperLimit": 30},
            {"reason": "Possible mirror - matching outbound within 2 hours of inbound", "subRuleRef": ".02", "lowerLimit": 30, "upperLimit": 120},
            {"reason": "No mirror pattern - outbound timing does not suggest mirroring", "subRuleRef": ".03", "lowerLimit": 120},
        ],
        "weights": [
            {"ref": ".err", "wght": "0"},
            {"ref": ".x00", "wght": "0"},
            {"ref": ".01",  "wght": "400"},
            {"ref": ".02",  "wght": "200"},
            {"ref": ".03",  "wght": "0"},
        ],
    },

    "025": {
        "description": "Non-commissioned transaction mirroring - debtor",
        "categories": ["local", "international"],
        "maxQueryRange": 86400000,  # 1 day
        "exit_conditions": [
            {"reason": "Incoming transaction is unsuccessful", "subRuleRef": ".x00"},
        ],
        "bands": [
            {"reason": "Rapid outgoing mirror - matching amount sent within 30 minutes of receiving", "subRuleRef": ".01", "upperLimit": 30},
            {"reason": "Possible outgoing mirror - matching amount sent within 2 hours", "subRuleRef": ".02", "lowerLimit": 30, "upperLimit": 120},
            {"reason": "No outgoing mirror pattern detected", "subRuleRef": ".03", "lowerLimit": 120},
        ],
        "weights": [
            {"ref": ".err", "wght": "0"},
            {"ref": ".x00", "wght": "0"},
            {"ref": ".01",  "wght": "400"},
            {"ref": ".02",  "wght": "200"},
            {"ref": ".03",  "wght": "0"},
        ],
    },

    "048": {
        "description": "Large transaction amount vs history - debtor",
        "categories": ["local", "international"],
        "maxQueryRange": 2592000000,  # 30 days
        "exit_conditions": [
            {"reason": "Incoming transaction is unsuccessful", "subRuleRef": ".x00"},
            {"reason": "No outgoing transaction history for debtor account", "subRuleRef": ".x01"},
        ],
        "bands": [
            {"reason": "Outgoing amount unprecedented - far exceeds debtor's historical transaction range", "subRuleRef": ".01", "upperLimit": 2},
            {"reason": "Outgoing amount unusually large compared to debtor's history", "subRuleRef": ".02", "lowerLimit": 2, "upperLimit": 5},
            {"reason": "Outgoing amount within debtor's normal historical range", "subRuleRef": ".03", "lowerLimit": 5},
        ],
        "weights": [
            {"ref": ".err", "wght": "0"},
            {"ref": ".x00", "wght": "0"},
            {"ref": ".x01", "wght": "0"},
            {"ref": ".01",  "wght": "400"},
            {"ref": ".02",  "wght": "200"},
            {"ref": ".03",  "wght": "0"},
        ],
    },

    "054": {
        "description": "Synthetic data check - Benford's Law - debtor",
        "categories": ["local", "international"],
        "maxQueryRange": 2592000000,  # 30 days
        "exit_conditions": [
            {"reason": "Incoming transaction is unsuccessful", "subRuleRef": ".x00"},
            {"reason": "Insufficient outgoing transaction count for statistical analysis", "subRuleRef": ".x01"},
        ],
        "bands": [
            {"reason": "Severe Benford's Law deviation - outgoing amounts likely fabricated/synthetic", "subRuleRef": ".01", "upperLimit": 30},
            {"reason": "Moderate Benford's deviation - outgoing amount distribution partially non-conforming", "subRuleRef": ".02", "lowerLimit": 30, "upperLimit": 70},
            {"reason": "Outgoing amounts conform to Benford's Law - natural distribution", "subRuleRef": ".03", "lowerLimit": 70},
        ],
        "weights": [
            {"ref": ".err", "wght": "0"},
            {"ref": ".x00", "wght": "0"},
            {"ref": ".x01", "wght": "0"},
            {"ref": ".01",  "wght": "400"},
            {"ref": ".02",  "wght": "200"},
            {"ref": ".03",  "wght": "0"},
        ],
    },

    "063": {
        "description": "Synthetic data check - Benford's Law - creditor",
        "categories": ["local", "international"],
        "maxQueryRange": 2592000000,  # 30 days
        "exit_conditions": [
            {"reason": "Incoming transaction is unsuccessful", "subRuleRef": ".x00"},
            {"reason": "Insufficient incoming transaction count for statistical analysis", "subRuleRef": ".x01"},
        ],
        "bands": [
            {"reason": "Severe Benford's Law deviation - incoming amounts likely fabricated/synthetic", "subRuleRef": ".01", "upperLimit": 30},
            {"reason": "Moderate Benford's deviation - incoming amount distribution partially non-conforming", "subRuleRef": ".02", "lowerLimit": 30, "upperLimit": 70},
            {"reason": "Incoming amounts conform to Benford's Law - natural distribution", "subRuleRef": ".03", "lowerLimit": 70},
        ],
        "weights": [
            {"ref": ".err", "wght": "0"},
            {"ref": ".x00", "wght": "0"},
            {"ref": ".x01", "wght": "0"},
            {"ref": ".01",  "wght": "400"},
            {"ref": ".02",  "wght": "200"},
            {"ref": ".03",  "wght": "0"},
        ],
    },

    # ════════════════════════════════════════════════════════════
    #  TO INSTALL — International Only Rules
    # ════════════════════════════════════════════════════════════

    "074": {
        "description": "Distance over time from last transaction location - debtor",
        "categories": ["international"],
        "maxQueryRange": 604800000,  # 7 days
        "exit_conditions": [
            {"reason": "Incoming transaction is unsuccessful", "subRuleRef": ".x00"},
            {"reason": "No prior transaction location data available for debtor", "subRuleRef": ".x01"},
        ],
        "bands": [
            {"reason": "Impossible travel - transaction locations imply implausible speed between events", "subRuleRef": ".01", "upperLimit": 2},
            {"reason": "Suspicious travel velocity - rapid location change between transactions", "subRuleRef": ".02", "lowerLimit": 2, "upperLimit": 8},
            {"reason": "Reasonable travel time between transaction locations", "subRuleRef": ".03", "lowerLimit": 8},
        ],
        "weights": [
            {"ref": ".err", "wght": "0"},
            {"ref": ".x00", "wght": "0"},
            {"ref": ".x01", "wght": "0"},
            {"ref": ".01",  "wght": "400"},
            {"ref": ".02",  "wght": "200"},
            {"ref": ".03",  "wght": "0"},
        ],
    },

    "075": {
        "description": "Distance from habitual locations - debtor",
        "categories": ["international"],
        "maxQueryRange": 2592000000,  # 30 days
        "exit_conditions": [
            {"reason": "Incoming transaction is unsuccessful", "subRuleRef": ".x00"},
            {"reason": "No historical location data available for debtor", "subRuleRef": ".x01"},
        ],
        "bands": [
            {"reason": "Transaction far from all habitual locations - significant geographic anomaly", "subRuleRef": ".01", "upperLimit": 30},
            {"reason": "Transaction moderately distant from habitual pattern", "subRuleRef": ".02", "lowerLimit": 30, "upperLimit": 70},
            {"reason": "Transaction within habitual geographic pattern", "subRuleRef": ".03", "lowerLimit": 70},
        ],
        "weights": [
            {"ref": ".err", "wght": "0"},
            {"ref": ".x00", "wght": "0"},
            {"ref": ".x01", "wght": "0"},
            {"ref": ".01",  "wght": "400"},
            {"ref": ".02",  "wght": "200"},
            {"ref": ".03",  "wght": "0"},
        ],
    },

    "090": {
        "description": "Upstream transaction divergence - debtor",
        "categories": ["international"],
        "maxQueryRange": 604800000,  # 7 days
        "exit_conditions": [
            {"reason": "Incoming transaction is unsuccessful", "subRuleRef": ".x00"},
            {"reason": "Insufficient upstream transaction chain data", "subRuleRef": ".x01"},
        ],
        "bands": [
            {"reason": "Highly divergent upstream chain - funds trace back to many disparate sources", "subRuleRef": ".01", "upperLimit": 3},
            {"reason": "Moderate upstream divergence - some branching in transaction origin", "subRuleRef": ".02", "lowerLimit": 3, "upperLimit": 8},
            {"reason": "Concentrated upstream chain - clear traceable origin", "subRuleRef": ".03", "lowerLimit": 8},
        ],
        "weights": [
            {"ref": ".err", "wght": "0"},
            {"ref": ".x00", "wght": "0"},
            {"ref": ".x01", "wght": "0"},
            {"ref": ".01",  "wght": "400"},
            {"ref": ".02",  "wght": "200"},
            {"ref": ".03",  "wght": "0"},
        ],
    },

    "091": {
        "description": "Transaction amount vs regulatory threshold",
        "categories": ["international"],
        "maxQueryRange": 86400000,  # 1 day
        "exit_conditions": [
            {"reason": "Incoming transaction is unsuccessful", "subRuleRef": ".x00"},
        ],
        "bands": [
            {"reason": "Amount within 10% below regulatory threshold - potential structuring to avoid CTR/FATF reporting", "subRuleRef": ".01", "upperLimit": 10},
            {"reason": "Amount within 30% of regulatory threshold - approaching reporting limit", "subRuleRef": ".02", "lowerLimit": 10, "upperLimit": 30},
            {"reason": "Amount well below regulatory threshold - no structuring indicators", "subRuleRef": ".03", "lowerLimit": 30},
        ],
        "weights": [
            {"ref": ".err", "wght": "0"},
            {"ref": ".x00", "wght": "0"},
            {"ref": ".01",  "wght": "400"},
            {"ref": ".02",  "wght": "200"},
            {"ref": ".03",  "wght": "0"},
        ],
    },
}

# ─── Helper Functions ──────────────────────────────────────────

def get_rule(rule_num: str) -> dict | None:
    """Get full configuration for a rule number."""
    return RULE_CATALOG.get(rule_num)


def get_installable_rules() -> dict:
    """Return rules that are NOT already running."""
    return {k: v for k, v in RULE_CATALOG.items() if k not in ALREADY_RUNNING}


def get_running_rules() -> dict:
    """Return rules that ARE already running."""
    return {k: v for k, v in RULE_CATALOG.items() if k in ALREADY_RUNNING}


def get_rules_by_category(category: str) -> dict:
    """Return rules matching a specific category."""
    return {k: v for k, v in RULE_CATALOG.items()
            if category in v.get("categories", [])}


def get_local_installable() -> dict:
    """Local rules that still need to be installed."""
    local = get_rules_by_category("local")
    return {k: v for k, v in local.items() if k not in ALREADY_RUNNING}


def get_international_installable() -> dict:
    """International rules that still need to be installed."""
    intl = get_rules_by_category("international")
    return {k: v for k, v in intl.items() if k not in ALREADY_RUNNING}


def validate_rule_config(rule_num: str) -> list:
    """
    Validate a rule's configuration for correctness.
    Returns list of issues (empty = valid).
    """
    rule = get_rule(rule_num)
    if not rule:
        return [f"Rule {rule_num} not found in catalog"]

    issues = []
    bands = rule.get("bands", [])
    exits = rule.get("exit_conditions", [])
    weights = rule.get("weights", [])

    # Check band structure
    if not bands:
        issues.append("No bands defined")
    else:
        # First band: upperLimit only
        if "lowerLimit" in bands[0]:
            issues.append("First band should not have lowerLimit")
        if "upperLimit" not in bands[0]:
            issues.append("First band missing upperLimit")

        # Last band: lowerLimit only
        if "upperLimit" in bands[-1]:
            issues.append("Last band should not have upperLimit")
        if "lowerLimit" not in bands[-1] and len(bands) > 1:
            issues.append("Last band missing lowerLimit")

        # Check contiguity
        for i in range(len(bands) - 1):
            upper = bands[i].get("upperLimit")
            lower = bands[i + 1].get("lowerLimit")
            if upper != lower:
                issues.append(f"Band gap: band {i} upper={upper} ≠ band {i+1} lower={lower}")

        # Check subRuleRef format
        for i, b in enumerate(bands):
            expected = f".0{i+1}" if i + 1 < 10 else f".{i+1}"
            if b.get("subRuleRef") != expected:
                issues.append(f"Band {i} has ref '{b.get('subRuleRef')}', expected '{expected}'")

    # Check exit conditions
    if not exits:
        issues.append("No exit conditions defined")
    else:
        refs = [e["subRuleRef"] for e in exits]
        if ".x00" not in refs:
            issues.append("Missing .x00 exit condition")

    # Check weight completeness
    if weights:
        weight_refs = {w["ref"] for w in weights}
        required_refs = {".err"}
        required_refs.update(b["subRuleRef"] for b in bands)
        required_refs.update(e["subRuleRef"] for e in exits)
        missing = required_refs - weight_refs
        if missing:
            issues.append(f"Missing weight entries: {missing}")

        # Check all weights are strings
        for w in weights:
            if not isinstance(w["wght"], str):
                issues.append(f"Weight for {w['ref']} is not a string")

        # Check .err and exits are weight 0
        for w in weights:
            if (w["ref"] == ".err" or w["ref"].startswith(".x")) and w["wght"] != "0":
                issues.append(f"{w['ref']} should have weight '0', has '{w['wght']}'")

    return issues


def ms_to_human(ms: int) -> str:
    """Convert milliseconds to readable string."""
    seconds = ms / 1000
    if seconds < 3600:
        return f"{seconds / 60:.0f} min"
    elif seconds < 86400:
        return f"{seconds / 3600:.0f} hours"
    elif seconds < 2592000:
        return f"{seconds / 86400:.0f} days"
    else:
        return f"{seconds / 2592000:.0f} months"
