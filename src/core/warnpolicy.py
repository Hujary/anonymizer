import warnings
import os

def apply_from_settings() -> None:
    try:
        from .einstellungen import DEBUG
    except Exception:
        DEBUG = False
    silence_env = os.getenv("ANON_SILENCE_WARNINGS", "").lower() in ("1", "true", "yes")
    if not DEBUG or silence_env:
        warnings.filterwarnings("ignore", category=Warning, module=r"urllib3(\.|$)")