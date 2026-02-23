from importlib import import_module
from typing import Any

from dotenv import load_dotenv

from rlm.clients.base_lm import BaseLM
from rlm.core.types import ClientBackend

load_dotenv()

_SUPPORTED_BACKENDS: tuple[ClientBackend, ...] = (
    "openai",
    "vllm",
    "portkey",
    "openrouter",
    "litellm",
    "anthropic",
    "azure_openai",
    "gemini",
    "vercel",
    "ollama",
    "vscode_lm",
)

_CLIENT_SPECS: dict[ClientBackend, tuple[str, str]] = {
    "openai": ("rlm.clients.openai", "OpenAIClient"),
    "vllm": ("rlm.clients.openai", "OpenAIClient"),
    "portkey": ("rlm.clients.portkey", "PortkeyClient"),
    "openrouter": ("rlm.clients.openai", "OpenAIClient"),
    "vercel": ("rlm.clients.openai", "OpenAIClient"),
    "litellm": ("rlm.clients.litellm", "LiteLLMClient"),
    "anthropic": ("rlm.clients.anthropic", "AnthropicClient"),
    "gemini": ("rlm.clients.gemini", "GeminiClient"),
    "azure_openai": ("rlm.clients.azure_openai", "AzureOpenAIClient"),
    "ollama": ("rlm.clients.ollama", "OllamaClient"),
    "vscode_lm": ("rlm.clients.vscode_lm", "VsCodeLM"),
}

_OPENAI_BACKEND_DEFAULT_BASE_URLS: dict[ClientBackend, str] = {
    "openrouter": "https://openrouter.ai/api/v1",
    "vercel": "https://ai-gateway.vercel.sh/v1",
}


def _load_client_class(module_path: str, class_name: str) -> type[BaseLM]:
    module = import_module(module_path)
    client_class = getattr(module, class_name)
    return client_class


def _build_openai_like_client(backend: ClientBackend, backend_kwargs: dict[str, Any]) -> BaseLM:
    default_base_url = _OPENAI_BACKEND_DEFAULT_BASE_URLS.get(backend)
    if default_base_url is not None:
        backend_kwargs.setdefault("base_url", default_base_url)

    if backend == "vllm":
        assert "base_url" in backend_kwargs, (
            "base_url is required to be set to local vLLM server address for vLLM"
        )

    openai_client_class = _load_client_class("rlm.clients.openai", "OpenAIClient")
    return openai_client_class(**backend_kwargs)


def get_client(
    backend: ClientBackend,
    backend_kwargs: dict[str, Any],
) -> BaseLM:
    """
    Routes a specific backend and the args (as a dict) to the appropriate client if supported.
    Currently supported backends: ['openai']
    """
    if backend not in _SUPPORTED_BACKENDS:
        raise ValueError(
            f"Unknown backend: {backend}. Supported backends: {list(_SUPPORTED_BACKENDS)}"
        )

    if backend in {"openai", "vllm", "openrouter", "vercel"}:
        return _build_openai_like_client(backend, backend_kwargs)

    module_path, class_name = _CLIENT_SPECS[backend]
    client_class = _load_client_class(module_path, class_name)
    return client_class(**backend_kwargs)
