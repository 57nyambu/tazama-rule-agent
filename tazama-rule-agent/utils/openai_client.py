# utils/openai_client.py
# Thin wrapper: one call per stage, with retry + structured JSON output.
# Supports dynamic model selection and API connectivity testing.
import json
import time
from openai import OpenAI
from config import cfg
from utils.logger import get_logger

log = get_logger("openai_client")
client = OpenAI(api_key=cfg.OPENAI_API_KEY)


def test_connection(model: str = None) -> dict:
    """
    Test OpenAI API connectivity and model access.
    Returns dict with: success, model, message, latency_ms
    """
    model = model or cfg.OPENAI_MODEL
    start = time.time()
    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            max_tokens=20,
            messages=[
                {"role": "system", "content": "Reply with exactly: {\"status\": \"ok\"}"},
                {"role": "user", "content": "ping"},
            ],
            response_format={"type": "json_object"},
        )
        latency = int((time.time() - start) * 1000)
        raw = response.choices[0].message.content
        usage = response.usage
        log.info(f"API test passed — model={model}, latency={latency}ms")
        return {
            "success": True,
            "model": model,
            "message": f"Connected successfully in {latency}ms",
            "latency_ms": latency,
            "response": raw,
            "tokens_used": {
                "prompt": usage.prompt_tokens if usage else 0,
                "completion": usage.completion_tokens if usage else 0,
                "total": usage.total_tokens if usage else 0,
            },
        }
    except Exception as e:
        latency = int((time.time() - start) * 1000)
        error_msg = str(e)
        log.error(f"API test failed — model={model}: {error_msg}")
        return {
            "success": False,
            "model": model,
            "message": error_msg,
            "latency_ms": latency,
        }


def ask(system_prompt: str, user_prompt: str, label: str = "",
        model: str = None) -> dict:
    """
    Single OpenAI call. Always returns parsed JSON dict.
    Retries up to cfg.MAX_RETRIES on failure.
    Accepts optional model override.
    """
    model = model or cfg.OPENAI_MODEL
    is_reasoning = model.startswith("o3") or model.startswith("o4")

    for attempt in range(1, cfg.MAX_RETRIES + 1):
        log.debug(f"[{label}] Attempt {attempt} — sending to {model}")
        log.debug(f"[{label}] USER PROMPT:\n{user_prompt}")
        try:
            # Reasoning models (o3, o4) don't support temperature or response_format
            create_kwargs = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
            }
            if not is_reasoning:
                create_kwargs["temperature"] = cfg.OPENAI_TEMPERATURE
                create_kwargs["response_format"] = {"type": "json_object"}

            response = client.chat.completions.create(**create_kwargs)
            raw = response.choices[0].message.content
            log.debug(f"[{label}] RAW RESPONSE:\n{raw}")

            # For reasoning models, extract JSON from potential markdown wrapping
            if is_reasoning:
                raw = _extract_json(raw)

            parsed = json.loads(raw)
            log.info(f"[{label}] ✓ Parsed successfully (model={model})")
            return parsed

        except Exception as e:
            log.warning(f"[{label}] Attempt {attempt} failed: {e}")
            if attempt < cfg.MAX_RETRIES:
                time.sleep(2 ** attempt)
            else:
                raise RuntimeError(f"[{label}] All {cfg.MAX_RETRIES} attempts failed: {e}")


def _extract_json(text: str) -> str:
    """Extract JSON from text that may be wrapped in markdown code blocks."""
    text = text.strip()
    # Remove ```json ... ``` wrapping
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json) and last line (```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    return text
