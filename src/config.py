"""User configuration for ambiguous-unit defaults (ADR 0004). Read-only: the server never writes it."""
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from .affine import normalize_reading
from .ambiguity import PROFILES, AssumptionError, find_candidate


class ConfigError(ValueError):
    """Raised when the config file is missing, malformed, or names unknown symbols/candidates."""


@dataclass(frozen=True)
class Config:
    profile: Optional[str] = None
    defaults: Dict[str, str] = field(default_factory=dict)
    readings: Dict[str, str] = field(default_factory=dict)  # canonical reading key -> choice


def config_path() -> Optional[Path]:
    """`SKOOKUM_CONFIG` if set (must exist), else `$XDG_CONFIG_HOME/skookum/config.toml` if present."""
    env = os.environ.get("SKOOKUM_CONFIG")
    if env:
        path = Path(env).expanduser()
        if not path.is_file():
            raise ConfigError(f"SKOOKUM_CONFIG points to '{path}', which does not exist.")
        return path
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    path = base / "skookum" / "config.toml"
    return path if path.is_file() else None


def load_config() -> Config:
    path = config_path()
    if path is None:
        return Config()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"Invalid TOML in '{path}': {e}")

    profile = data.get("profile")
    if profile is not None and profile not in PROFILES:
        raise ConfigError(f"profile must be one of {', '.join(PROFILES)} (got {profile!r}) in '{path}'.")

    defaults = data.get("defaults", {})
    if not isinstance(defaults, dict):
        raise ConfigError(f"[defaults] must be a table in '{path}'.")
    for symbol, candidate_id in defaults.items():
        try:
            find_candidate(symbol, candidate_id)
        except AssumptionError as e:
            raise ConfigError(f"Bad [defaults] entry in '{path}': {e}")

    raw_readings = data.get("readings", {})
    if not isinstance(raw_readings, dict):
        raise ConfigError(f"[readings] must be a table in '{path}'.")
    readings: Dict[str, str] = {}
    for question, choice in raw_readings.items():
        try:
            key, value = normalize_reading(question, choice)
        except ValueError as e:
            raise ConfigError(f"Bad [readings] entry in '{path}': {e}")
        readings[key] = value
    return Config(profile=profile, defaults=dict(defaults), readings=readings)
