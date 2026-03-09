# utils/shell.py
# Shell command runner with timeout
import subprocess
from utils.logger import get_logger

log = get_logger("shell")


def run_command(cmd: str, timeout: int = 120) -> tuple:
    """
    Run a shell command with timeout.
    Returns (return_code, stdout, stderr).
    """
    log.debug(f"Running command: {cmd}")
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        log.debug(f"Command exited with code: {result.returncode}")
        if result.stdout:
            log.debug(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            log.debug(f"STDERR:\n{result.stderr}")
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        log.error(f"Command timed out after {timeout}s: {cmd}")
        return -1, "", f"Command timed out after {timeout}s"
    except Exception as e:
        log.error(f"Command failed: {e}")
        return -1, "", str(e)
