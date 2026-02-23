from typing import Any, Literal

from rlm.environments.base_env import BaseEnv, SupportsPersistence, config_from_kwargs
from rlm.environments.local_repl import LocalREPL

__all__ = ["BaseEnv", "LocalREPL", "SupportsPersistence", "get_environment"]


def get_environment(
    environment: Literal["local", "modal", "docker", "daytona", "prime", "e2b"],
    environment_kwargs: dict[str, Any],
) -> BaseEnv:
    """
    Routes a specific environment and the args (as a dict) to the appropriate environment if supported.
    Currently supported environments: ['local', 'modal', 'docker', 'daytona', 'prime', 'e2b']
    """
    if environment == "local":
        return LocalREPL(**environment_kwargs)
    elif environment == "modal":
        from rlm.environments.modal_repl import ModalREPL, ModalREPLConfig

        config, extra = config_from_kwargs(ModalREPLConfig, environment_kwargs)
        return ModalREPL(config, **extra)
    elif environment == "docker":
        from rlm.environments.docker_repl import DockerREPL, DockerREPLConfig

        config, extra = config_from_kwargs(DockerREPLConfig, environment_kwargs)
        return DockerREPL(config, **extra)
    elif environment == "daytona":
        from rlm.environments.daytona_repl import DaytonaREPL, DaytonaREPLConfig

        config, extra = config_from_kwargs(DaytonaREPLConfig, environment_kwargs)
        return DaytonaREPL(config, **extra)
    elif environment == "prime":
        from rlm.environments.prime_repl import PrimeREPL, PrimeREPLConfig

        config, extra = config_from_kwargs(PrimeREPLConfig, environment_kwargs)
        return PrimeREPL(config, **extra)
    elif environment == "e2b":
        from rlm.environments.e2b_repl import E2BREPL, E2BREPLConfig

        config, extra = config_from_kwargs(E2BREPLConfig, environment_kwargs)
        return E2BREPL(config, **extra)
    else:
        raise ValueError(
            f"Unknown environment: {environment}. Supported: ['local', 'modal', 'docker', 'daytona', 'prime', 'e2b']"
        )
