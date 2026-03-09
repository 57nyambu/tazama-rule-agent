# stages/stage4_executor.py
# Task: Feed all generated config into install-rule.sh non-interactively.
import pexpect
import os
import sys
from config import cfg
from utils.logger import get_logger

log = get_logger("stage4")


def build_answers(rule_num: str, image_tag: str, description: str,
                  bands: list, exit_conditions: list, weights: list) -> list:
    """
    Returns ordered list of answers to match every script prompt exactly.
    """
    answers = [
        rule_num,                        # Rule number
        image_tag,                       # Image tag
        description,                     # Description
        str(len(bands)),                 # Number of bands
    ]

    for i, band in enumerate(bands):
        answers.append(band["subRuleRef"])
        answers.append(band["reason"])
        if i < len(bands) - 1:
            answers.append(str(band["upperLimit"]))

    answers.append(str(len(exit_conditions)))   # Exit condition count
    for ec in exit_conditions:
        answers.append(ec["subRuleRef"])
        answers.append(ec["reason"])

    answers.append(str(len(weights)))            # Weight count
    for w in weights:
        answers.append(w["ref"])
        answers.append(str(w["wght"]))

    answers.append("y")                          # Confirm proceed

    log.debug(f"Prepared {len(answers)} answers for script prompts")
    return answers


def run(rule_num: str, image_tag: str, description: str,
        bands: list, exit_conditions: list, weights: list,
        stream_callback=None) -> bool:
    """
    Runs install-rule.sh using pexpect to answer prompts automatically.
    stream_callback(line: str) is called for each output line (for UI streaming).
    Returns True on success.
    """
    answers = build_answers(rule_num, image_tag, description,
                            bands, exit_conditions, weights)
    answer_index = [0]  # mutable for closure

    log.info(f"Stage 4 — Running install-rule.sh for rule-{rule_num}")

    # Ensure script is executable
    script_path = cfg.INSTALL_SCRIPT_PATH
    try:
        os.chmod(script_path, 0o755)
    except OSError:
        pass  # may already be executable or on Windows

    try:
        child = pexpect.spawn(
            f"sudo bash {script_path}",
            timeout=cfg.SCRIPT_TIMEOUT,
            encoding="utf-8"
        )
        child.logfile_read = open(
            f"{cfg.LOG_DIR}/script_run_{rule_num}.log", "w"
        )

        # ── Handle sudo password prompt ──────────────────────
        sudo_idx = child.expect([
            r"\[sudo\].*password.*:",   # [sudo] password for <user>:
            r"[Pp]assword.*:",          # Password:
            r">\s*$",                   # Already authenticated — script prompt
            pexpect.EOF,
            pexpect.TIMEOUT,
        ], timeout=30)

        if sudo_idx in (0, 1):
            # Send sudo password
            sudo_pw = cfg.SUDO_PASSWORD
            if not sudo_pw:
                log.error("Sudo password required but SUDO_PASSWORD not set in .env")
                if stream_callback:
                    stream_callback("[ERROR] SUDO_PASSWORD not configured in .env")
                return False
            log.debug("Sending sudo password")
            if stream_callback:
                stream_callback("🔑 Authenticating sudo...")
            child.sendline(sudo_pw)
            # Wait for the first actual script prompt after auth
            auth_idx = child.expect([
                r">\s*$",
                r"sudo:.*incorrect",
                pexpect.EOF,
                pexpect.TIMEOUT,
            ], timeout=30)
            if auth_idx == 1:
                log.error("Sudo password incorrect")
                if stream_callback:
                    stream_callback("[ERROR] Sudo password incorrect")
                return False
            elif auth_idx in (2, 3):
                log.error("Unexpected response after sudo auth")
                if stream_callback:
                    stream_callback("[ERROR] Unexpected response after sudo authentication")
                return False
            # auth_idx == 0: got script prompt, stream output and answer
            output = child.before or ""
            for line in output.splitlines():
                line = line.strip()
                if line:
                    log.debug(f"[script] {line}")
                    if stream_callback:
                        stream_callback(line)
            if stream_callback:
                stream_callback("✓ Sudo authenticated")
            # Answer the first prompt
            if answer_index[0] < len(answers):
                ans = answers[answer_index[0]]
                log.debug(f"  → Answering prompt [{answer_index[0]}]: {ans!r}")
                child.sendline(ans)
                answer_index[0] += 1
        elif sudo_idx == 2:
            # No sudo prompt — already at script prompt, answer it
            output = child.before or ""
            for line in output.splitlines():
                line = line.strip()
                if line:
                    log.debug(f"[script] {line}")
                    if stream_callback:
                        stream_callback(line)
            if answer_index[0] < len(answers):
                ans = answers[answer_index[0]]
                log.debug(f"  → Answering prompt [{answer_index[0]}]: {ans!r}")
                child.sendline(ans)
                answer_index[0] += 1
        elif sudo_idx in (3, 4):
            log.error("Script did not produce any prompt or sudo challenge")
            if stream_callback:
                stream_callback("[ERROR] Script did not start — check install-rule.sh path")
            return False

        # ── Main prompt loop ─────────────────────────────────
        while True:
            try:
                idx = child.expect([
                    r">\s*$",           # Script prompt
                    pexpect.EOF,
                    pexpect.TIMEOUT,
                ], timeout=120)

                # Stream output so far to UI
                output = child.before or ""
                for line in output.splitlines():
                    line = line.strip()
                    if line:
                        log.debug(f"[script] {line}")
                        if stream_callback:
                            stream_callback(line)

                if idx == 0:
                    if answer_index[0] < len(answers):
                        ans = answers[answer_index[0]]
                        log.debug(f"  → Answering prompt [{answer_index[0]}]: {ans!r}")
                        child.sendline(ans)
                        answer_index[0] += 1
                    else:
                        log.warning("More prompts than expected answers — sending empty")
                        child.sendline("")

                elif idx == 1:   # EOF — script finished
                    remaining = child.before or ""
                    for line in remaining.splitlines():
                        line = line.strip()
                        if line:
                            log.debug(f"[script] {line}")
                            if stream_callback:
                                stream_callback(line)
                    break

                elif idx == 2:   # TIMEOUT
                    log.error("Script timed out waiting for prompt")
                    if stream_callback:
                        stream_callback("[ERROR] Script timed out")
                    return False

            except pexpect.EOF:
                break

        exit_status = child.wait()
        log.info(f"Script exited with status: {exit_status}")
        return exit_status == 0

    except Exception as e:
        log.error(f"Stage 4 failed: {e}", exc_info=True)
        if stream_callback:
            stream_callback(f"[ERROR] {e}")
        return False
