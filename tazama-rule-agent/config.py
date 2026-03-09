# config.py
# ─────────────────────────────────────────────
# Central configuration — all tunables live here.
# ─────────────────────────────────────────────
import os
from dotenv import load_dotenv

load_dotenv()

# Available models with metadata for UI display
AVAILABLE_MODELS = [
    {"id": "gpt-4.1-nano",  "label": "GPT-4.1 Nano",  "tpm": 60000,  "rpm": 3, "rpd": 200, "tier": "fast",     "description": "Fastest, cheapest — great for structured tasks"},
    {"id": "gpt-4.1-mini",  "label": "GPT-4.1 Mini",  "tpm": 60000,  "rpm": 3, "rpd": 200, "tier": "balanced", "description": "Best balance of speed, cost, and accuracy"},
    {"id": "gpt-4.1",       "label": "GPT-4.1",       "tpm": 10000,  "rpm": 3, "rpd": 200, "tier": "quality",  "description": "Highest quality, lower throughput"},
    {"id": "gpt-5-nano",    "label": "GPT-5 Nano",    "tpm": 40000,  "rpm": 3, "rpd": 200, "tier": "fast",     "description": "Next-gen fast model"},
    {"id": "gpt-5-mini",    "label": "GPT-5 Mini",    "tpm": 60000,  "rpm": 3, "rpd": 200, "tier": "balanced", "description": "Next-gen balanced model"},
    {"id": "gpt-5.1",       "label": "GPT-5.1",       "tpm": 10000,  "rpm": 3, "rpd": 200, "tier": "quality",  "description": "Most capable model available"},
    {"id": "o4-mini",       "label": "o4-mini",        "tpm": 100000, "rpm": 3, "rpd": 200, "tier": "reasoning","description": "Reasoning model — best for complex logic"},
    {"id": "o3",            "label": "o3",             "tpm": 100000, "rpm": 3, "rpd": 200, "tier": "reasoning","description": "Reasoning model — deep analytical tasks"},
    {"id": "gpt-4o",        "label": "GPT-4o",        "tpm": 10000,  "rpm": 3, "rpd": 200, "tier": "legacy",   "description": "Legacy model"},
]

MODEL_IDS = [m["id"] for m in AVAILABLE_MODELS]

class Config:
    # OpenAI
    OPENAI_API_KEY: str   = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str     = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
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
