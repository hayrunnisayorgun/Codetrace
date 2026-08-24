import subprocess
import json

DEFAULT_FOUNDRY_PORT = 43456


def discover_foundry_endpoint() -> str:
    """
    Read the service's current address from `foundry status`.

    Foundry Local can pick a different port every time it restarts, so the CLI
    is asked each time rather than trusting a hardcoded value. Falls back to the
    default port when the service is down or the CLI is missing -- callers
    already surface the connection failure with a readable message.
    """
    try:
        result = subprocess.run(
            ["foundry", "status", "--output", "json"],
            capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace"
        )
        web_urls = json.loads(result.stdout).get("service", {}).get("webUrls", [])
        if web_urls:
            return web_urls[0].rstrip("/")
    except Exception as e:
        print(f"[Foundry Local] Could not determine the service address: {e}")
    return f"http://127.0.0.1:{DEFAULT_FOUNDRY_PORT}"


def get_chat_completions_url() -> str:
    """Return the OpenAI-compatible chat completions endpoint of Foundry Local."""
    return f"{discover_foundry_endpoint()}/v1/chat/completions"


def is_model_loaded(model_alias: str) -> bool:
    """
    Check `foundry cache ls` to see whether the model is loaded into memory.
    """
    try:
        result = subprocess.run(
            ["foundry", "cache", "ls", "--output", "json"],
            capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace"
        )
        data = json.loads(result.stdout)
        for model in data.get("models", []):
            if model.get("alias") == model_alias and model.get("loaded"):
                return True
        return False
    except Exception as e:
        print(f"[Foundry Local] Could not check model status: {e}")
        return False


def is_service_running() -> bool:
    try:
        result = subprocess.run(
            ["foundry", "status", "--output", "json"],
            capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace"
        )
        return json.loads(result.stdout).get("service", {}).get("ready", False)
    except Exception:
        return False


def ensure_service_running():
    """Start the daemon if it is down -- it can exit on its own under memory pressure."""
    if is_service_running():
        return
    print("[Foundry Local] Service is not running; starting it...")
    try:
        result = subprocess.run(
            ["foundry", "server", "start"],
            capture_output=True, text=True, timeout=120, encoding="utf-8", errors="replace"
        )
        if result.returncode == 0:
            print("[Foundry Local] Service started.")
        else:
            print(f"[Foundry Local] Could not start the service: {result.stderr or result.stdout}")
    except FileNotFoundError:
        print("[Foundry Local] 'foundry' command not found. Check that Foundry Local is installed and on PATH.")
    except Exception as e:
        print(f"[Foundry Local] Error while starting the service: {e}")


def ensure_model_loaded(model_alias: str):
    """
    Called at backend startup to get the service and model ready. Does nothing
    if the model is already loaded. If Foundry Local is missing or will not
    start, the error is logged but startup continues -- the README and chat
    endpoints fall back on their own.
    """
    ensure_service_running()

    if is_model_loaded(model_alias):
        print(f"[Foundry Local] '{model_alias}' is already loaded.")
        return

    print(f"[Foundry Local] Loading '{model_alias}'; this can take a moment...")
    try:
        result = subprocess.run(
            ["foundry", "model", "load", model_alias],
            capture_output=True, text=True, timeout=180, encoding="utf-8", errors="replace"
        )
        if result.returncode == 0:
            print(f"[Foundry Local] '{model_alias}' loaded.")
        else:
            print(f"[Foundry Local] Could not load '{model_alias}': {result.stderr or result.stdout}")
    except FileNotFoundError:
        print("[Foundry Local] 'foundry' command not found. Check that Foundry Local is installed and on PATH.")
    except subprocess.TimeoutExpired:
        print(f"[Foundry Local] Timed out loading '{model_alias}'.")
    except Exception as e:
        print(f"[Foundry Local] Error while loading '{model_alias}': {e}")
