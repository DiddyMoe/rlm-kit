from typing import Any, Literal

from rlm.environments.base_env import BaseEnv, SupportsPersistence
from rlm.environments.local_repl import LocalREPL

__all__ = ["BaseEnv", "LocalREPL", "SupportsPersistence", "get_environment"]


def get_environment(
    environment: Literal["local"],
    environment_kwargs: dict[str, Any],
) -> BaseEnv:
    """Return an environment instance for the given type.

    Only ``local`` is supported when running inside the VS Code extension.
    """
    if environment == "local":
        return LocalREPL(**environment_kwargs)
    raise ValueError(f"Unknown environment: {environment}. Supported: ['local']")
