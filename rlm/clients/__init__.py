from rlm.clients.base_lm import BaseLM
from rlm.clients.openai import OpenAIClient
from rlm.clients.portkey import PortkeyClient
from rlm.core.types import ClientBackend

from dotenv import load_dotenv
from typing import Dict, Any

load_dotenv()


def get_client(
    backend: ClientBackend,
    backend_kwargs: Dict[str, Any],
) -> BaseLM:
    """
    Routes a specific backend and the args (as a dict) to the appropriate client if supported.
    Currently supported backends: ['openai']
    """
    if backend == "openai":
        return OpenAIClient(**backend_kwargs)
    elif backend == "portkey":
        return PortkeyClient(**backend_kwargs)
    else:
        raise ValueError(f"Unknown backend: {backend}. Supported backends: ['openai']")
