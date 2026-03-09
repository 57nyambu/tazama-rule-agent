# config.py
# ─────────────────────────────────────────────
# Central configuration — all tunables live here.
# ─────────────────────────────────────────────
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Engine mode (local = pre-computed knowledge base, no AI)
    ENGINE_MODE: str      = os.getenv("ENGINE_MODE", "local")

    # OpenAI (kept for optional future use — not required for local mode)
    OPENAI_API_KEY: str   = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str     = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    OPENAI_TEMPERATURE: float = 0.1
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
    IMAGE_TAG: str        = os.getenv("IMAGE_TAG", "3.0.0")

    # Script
    INSTALL_SCRIPT_PATH: str = os.getenv("INSTALL_SCRIPT_PATH", "./install-rule.sh")
    SUDO_PASSWORD: str    = os.getenv("SUDO_PASSWORD", "")
    SCRIPT_TIMEOUT: int   = 300

    # Logging
    LOG_LEVEL: str        = os.getenv("LOG_LEVEL", "DEBUG")
    LOG_DIR: str          = "./logs"

cfg = Config()
