"""Local project state store (ADR-010): one shared SQLite file under `.agentdraft/`,
alongside the schema being worked on. Checkpointing (`FR-5`) is the first consumer;
schema version history (`FR-9`) and run history (`FR-6`) are planned to share the
same file rather than each owning a separate one.
"""

from pathlib import Path

LOCAL_STORE_DIR = Path(".agentdraft")
STATE_DB_PATH = LOCAL_STORE_DIR / "state.db"


def ensure_local_store_dir() -> Path:
    """Create `.agentdraft/` (relative to cwd) if missing, and return `STATE_DB_PATH`."""
    LOCAL_STORE_DIR.mkdir(exist_ok=True)
    return STATE_DB_PATH
