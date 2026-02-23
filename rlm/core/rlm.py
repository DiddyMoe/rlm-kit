import asyncio
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from types import TracebackType
from typing import Any, cast

from rlm.clients import BaseLM, get_client
from rlm.core.lm_handler import LMHandler
from rlm.core.types import (
    ClientBackend,
    CodeBlock,
    EnvironmentType,
    REPLResult,
    RLMChatCompletion,
    RLMIteration,
    RLMMetadata,
    UsageSummary,
)
from rlm.environments import BaseEnv, SupportsPersistence, get_environment
from rlm.logger import RLMLogger, VerbosePrinter
from rlm.utils.parsing import (
    find_code_blocks,
    find_final_answer,
    format_iteration,
)
from rlm.utils.prompts import (
    RLM_SYSTEM_PROMPT,
    QueryMetadata,
    build_rlm_system_prompt,
    build_user_prompt,
)
from rlm.utils.rlm_utils import filter_sensitive_keys
from rlm.utils.token_utils import count_tokens, get_context_limit


@dataclass
class RLMConfig:
    backend: ClientBackend = "openai"
    backend_kwargs: dict[str, Any] | None = None
    environment: EnvironmentType = "local"
    environment_kwargs: dict[str, Any] | None = None
    depth: int = 0
    max_depth: int = 1
    max_iterations: int = 30
    custom_system_prompt: str | None = None
    other_backends: list[ClientBackend] | None = None
    other_backend_kwargs: list[dict[str, Any]] | None = None
    max_root_tokens: int | None = None
    max_sub_tokens: int | None = None
    on_root_chunk: Callable[[str], None] | None = None
    enable_prefix_cache: bool = False
    logger: RLMLogger | None = None
    verbose: bool = False
    persistent: bool = False
    compaction: bool = False
    compaction_threshold_pct: float = 0.85
    custom_tools: dict[str, Any] | None = None


@dataclass
class _LoopState:
    prompt: str | dict[str, Any]
    root_prompt: str | None
    lm_handler: LMHandler
    environment: BaseEnv
    message_history: list[dict[str, Any]]
    compaction_count: int
    time_start: float


class RLM:
    """
    Recursive Language Model class that the user instantiates and runs on their tasks.

    Each completion() call spawns its own environment and LM handler, which are
    cleaned up when the call completes.
    """

    def __init__(self, config: RLMConfig | None = None):
        """
        Args:
            config: Optional RLM configuration. Defaults to RLMConfig().
        """
        self._apply_config(config or RLMConfig())
        if self.persistent:
            self._validate_persistent_environment_support()
        self._log_metadata()

    def _apply_config(self, config: RLMConfig) -> None:
        self.backend = config.backend
        self.backend_kwargs = config.backend_kwargs
        self.environment_type = config.environment
        self.environment_kwargs = (
            config.environment_kwargs.copy() if config.environment_kwargs is not None else {}
        )
        if config.other_backends is not None and len(config.other_backends) != 1:
            raise ValueError(
                "We currently only support one additional backend for the recursive sub-calls! "
                "This model will be the model used for recursive sub-calls, but this will change in the future"
            )

        self.other_backends = config.other_backends
        self.other_backend_kwargs = config.other_backend_kwargs
        self.max_root_tokens = config.max_root_tokens
        self.max_sub_tokens = config.max_sub_tokens
        self.on_root_chunk = config.on_root_chunk
        self.enable_prefix_cache = config.enable_prefix_cache
        self._prefix_prompt_cache: dict[str, list[dict[str, Any]]] = {}
        self.depth = config.depth
        self.max_depth = config.max_depth
        self.max_iterations = config.max_iterations
        self.system_prompt = config.custom_system_prompt or RLM_SYSTEM_PROMPT
        self.logger = config.logger
        self.verbose = VerbosePrinter(enabled=config.verbose)
        self.compaction = config.compaction
        self.compaction_threshold_pct = config.compaction_threshold_pct
        self.custom_tools = config.custom_tools
        self.persistent = config.persistent
        self._persistent_env: SupportsPersistence | None = None

    def _log_metadata(self) -> None:
        if not (self.logger or self.verbose.enabled):
            return
        metadata = RLMMetadata(
            root_model=self.backend_kwargs.get("model_name", "unknown")
            if self.backend_kwargs
            else "unknown",
            max_depth=self.max_depth,
            max_iterations=self.max_iterations,
            backend=self.backend,
            backend_kwargs=filter_sensitive_keys(self.backend_kwargs)
            if self.backend_kwargs
            else {},
            environment_type=self.environment_type,
            environment_kwargs=filter_sensitive_keys(self.environment_kwargs)
            if self.environment_kwargs
            else {},
            max_root_tokens=self.max_root_tokens,
            max_sub_tokens=self.max_sub_tokens,
            on_root_chunk=self.on_root_chunk is not None,
            enable_prefix_cache=self.enable_prefix_cache,
            other_backends=cast(list[str] | None, self.other_backends),
            run_id=getattr(self.logger, "run_id", None) if self.logger else None,
        )
        if self.logger:
            self.logger.log_metadata(metadata)
        self.verbose.print_metadata(metadata)

    def _create_lm_handler(self) -> LMHandler:
        client: BaseLM = get_client(cast(ClientBackend, self.backend), self.backend_kwargs or {})
        other_backend_client: BaseLM | None = None
        if self.other_backends and self.other_backend_kwargs:
            other_backend_client = get_client(self.other_backends[0], self.other_backend_kwargs[0])

        lm_handler = LMHandler(
            client,
            other_backend_client=other_backend_client,
            max_root_tokens=self.max_root_tokens,
            max_sub_tokens=self.max_sub_tokens,
        )
        if self.other_backends and self.other_backend_kwargs:
            paired_backends = zip(
                self.other_backends,
                self.other_backend_kwargs,
                strict=True,
            )
            for backend, kwargs in paired_backends:
                other_client: BaseLM = get_client(backend, kwargs)
                lm_handler.register_client(other_client.model_name, other_client)
        lm_handler.start()
        return lm_handler

    def _create_environment(self, lm_handler: LMHandler, prompt: str | dict[str, Any]) -> BaseEnv:
        env_kwargs = self.environment_kwargs.copy()
        env_kwargs["lm_handler_address"] = (lm_handler.host, lm_handler.port)
        env_kwargs["context_payload"] = prompt
        env_kwargs["depth"] = self.depth + 1
        env_kwargs["recursive_rlm_config"] = {
            "backend": self.backend,
            "backend_kwargs": self.backend_kwargs.copy() if self.backend_kwargs else None,
            "environment": self.environment_type,
            "environment_kwargs": self.environment_kwargs.copy(),
            "max_depth": self.max_depth,
            "max_iterations": self.max_iterations,
            "other_backends": self.other_backends.copy() if self.other_backends else None,
            "other_backend_kwargs": (
                [kwargs.copy() for kwargs in self.other_backend_kwargs]
                if self.other_backend_kwargs
                else None
            ),
            "max_root_tokens": self.max_root_tokens,
            "max_sub_tokens": self.max_sub_tokens,
        }
        if self.custom_tools is not None:
            env_kwargs["custom_tools"] = self.custom_tools
        return get_environment(cast(EnvironmentType, self.environment_type), env_kwargs)

    @contextmanager
    def _spawn_completion_context(self, prompt: str | dict[str, Any]):
        """
        Spawn an LM handler and environment for a single completion call.

        When persistent=True, the environment is reused across calls.
        When persistent=False (default), creates fresh environment each call.
        """
        lm_handler = self._create_lm_handler()

        # Environment: reuse if persistent, otherwise create fresh
        if self.persistent and self._persistent_env is not None:
            persistent_env = self._persistent_env
            # Defensive check: ensure environment supports persistence methods
            if not self._env_supports_persistence(persistent_env):
                raise RuntimeError(
                    f"Persistent environment of type '{type(persistent_env).__name__}' does not "
                    f"implement required methods (update_handler_address, add_context, get_context_count). "
                    f"This should have been caught at initialization."
                )
            persistent_env.update_handler_address((lm_handler.host, lm_handler.port))
            persistent_env.add_context(prompt)
            environment: BaseEnv = cast(BaseEnv, persistent_env)
        else:
            environment = self._create_environment(lm_handler, prompt)

            if self.persistent:
                if not isinstance(environment, SupportsPersistence):
                    raise RuntimeError(
                        "Persistent mode requires an environment that implements SupportsPersistence."
                    )
                self._persistent_env = environment

        try:
            yield lm_handler, environment
        finally:
            lm_handler.stop()
            if not self.persistent and hasattr(environment, "cleanup"):
                environment.cleanup()

    def _setup_prompt(self, prompt: str | dict[str, Any]) -> list[dict[str, Any]]:
        """
        Setup the system prompt for the RLM. Also include metadata about the prompt and build
        up the initial message history.
        """
        metadata = QueryMetadata(prompt)
        message_history = cast(
            list[dict[str, Any]],
            build_rlm_system_prompt(
                system_prompt=self.system_prompt,
                query_metadata=metadata,
                custom_tools=self.custom_tools,
                compaction=self.compaction,
            ),
        )

        return message_history

    def completion(
        self, prompt: str | dict[str, Any], root_prompt: str | None = None
    ) -> RLMChatCompletion:
        """
        Recursive Language Model completion call. This is the main entry point for querying an RLM, and
        can replace a regular LM completion call.

        Spawns its own environment and LM handler for the duration of this call.

        Args:
            prompt: A single string or dictionary of messages to pass as context to the model.
            root_prompt: We allow the RLM's root LM to see a (small) prompt that the user specifies. A common example of this
            is if the user is asking the RLM to answer a question, we can pass the question as the root prompt.
        Returns:
            A final answer as a string.
        """
        time_start = time.perf_counter()

        # Clear in-memory iteration store for this completion
        if self.logger:
            self.logger.clear_iterations()

        # If we're at max depth, the RLM is an LM, so we fallback to the regular LM.
        if self.depth >= self.max_depth:
            return self._fallback_answer(prompt)

        with self._spawn_completion_context(prompt) as (lm_handler, environment):
            message_history = self._setup_prompt(prompt)
            loop_state = _LoopState(
                prompt=prompt,
                root_prompt=root_prompt,
                lm_handler=lm_handler,
                environment=environment,
                message_history=message_history,
                compaction_count=0,
                time_start=time_start,
            )
            return self._run_iteration_loop(loop_state)

    def _run_iteration_loop(
        self,
        loop_state: _LoopState,
    ) -> RLMChatCompletion:
        for i in range(self.max_iterations):
            loop_state.message_history, loop_state.compaction_count = self._maybe_compact(
                loop_state.lm_handler,
                loop_state.environment,
                loop_state.message_history,
                loop_state.compaction_count,
            )

            iteration = self._run_single_iteration(loop_state, i)
            final_answer = self._record_iteration(iteration, loop_state.environment, i + 1)
            if final_answer is not None:
                return self._finalize_completion(
                    loop_state=loop_state,
                    response=final_answer,
                    iteration_count=i + 1,
                )

            self._append_iteration_messages(loop_state, iteration)

        final_answer = self._default_answer(loop_state.message_history, loop_state.lm_handler)
        return self._finalize_completion(
            loop_state=loop_state,
            response=final_answer,
            iteration_count=self.max_iterations,
        )

    def _run_single_iteration(self, loop_state: _LoopState, iteration_index: int) -> RLMIteration:
        current_prompt = self._build_iteration_prompt(loop_state, iteration_index)
        return self._completion_turn(
            prompt=current_prompt,
            lm_handler=loop_state.lm_handler,
            environment=loop_state.environment,
        )

    def _build_iteration_prompt(
        self, loop_state: _LoopState, iteration_index: int
    ) -> list[dict[str, Any]]:
        context_count, history_count = self._get_prompt_counts(loop_state.environment)
        if self.enable_prefix_cache:
            return self._cached_prompt(
                loop_state.message_history,
                loop_state.root_prompt,
                iteration_index,
                context_count,
                history_count,
            )

        return loop_state.message_history + [
            build_user_prompt(loop_state.root_prompt, iteration_index, context_count, history_count)
        ]

    def _get_prompt_counts(self, environment: BaseEnv) -> tuple[int, int]:
        if not isinstance(environment, SupportsPersistence):
            return 1, 0
        return environment.get_context_count(), environment.get_history_count()

    def _record_iteration(
        self, iteration: RLMIteration, environment: BaseEnv, iteration_number: int
    ) -> str | None:
        final_answer = find_final_answer(iteration.response, environment=environment)
        iteration.final_answer = final_answer
        if self.logger:
            self.logger.log(iteration)
        self.verbose.print_iteration(iteration, iteration_number)
        return final_answer

    def _append_iteration_messages(self, loop_state: _LoopState, iteration: RLMIteration) -> None:
        new_messages = format_iteration(iteration)
        loop_state.message_history.extend(new_messages)
        if self.compaction and hasattr(loop_state.environment, "append_compaction_entry"):
            loop_state.environment.append_compaction_entry(new_messages)

    def _finalize_completion(
        self,
        loop_state: _LoopState,
        response: str,
        iteration_count: int,
    ) -> RLMChatCompletion:
        time_end = time.perf_counter()
        usage = loop_state.lm_handler.get_usage_summary()
        self.verbose.print_final_answer(response)
        self.verbose.print_summary(
            iteration_count, time_end - loop_state.time_start, usage.to_dict()
        )
        if self.persistent and isinstance(loop_state.environment, SupportsPersistence):
            loop_state.environment.add_history(loop_state.message_history)
        return self._build_completion_result(
            prompt=loop_state.prompt,
            response=response,
            usage=usage,
            execution_time=time_end - loop_state.time_start,
        )

    def _maybe_compact(
        self,
        lm_handler: LMHandler,
        environment: BaseEnv,
        message_history: list[dict[str, Any]],
        compaction_count: int,
    ) -> tuple[list[dict[str, Any]], int]:
        """Run compaction when enabled and threshold is reached."""
        if not (self.compaction and hasattr(environment, "append_compaction_entry")):
            return message_history, compaction_count

        current_tokens, threshold_tokens, max_tokens = self._get_compaction_status(message_history)
        self.verbose.print_compaction_status(current_tokens, threshold_tokens, max_tokens)
        if current_tokens < threshold_tokens:
            return message_history, compaction_count

        self.verbose.print_compaction()
        next_count = compaction_count + 1
        compacted_history = self._compact_history(
            lm_handler,
            environment,
            message_history,
            next_count,
        )
        return compacted_history, next_count

    def _build_completion_result(
        self,
        prompt: str | dict[str, Any] | list[dict[str, Any]],
        response: str,
        usage: UsageSummary,
        execution_time: float,
    ) -> RLMChatCompletion:
        """Build the normalized completion return payload."""
        root_model = (
            self.backend_kwargs.get("model_name", "unknown") if self.backend_kwargs else "unknown"
        )
        metadata = self.logger.get_trajectory() if self.logger else None
        return RLMChatCompletion(
            root_model,
            prompt,
            response,
            usage,
            execution_time,
            metadata,
        )

    def _completion_turn(
        self,
        prompt: str | list[dict[str, Any]],
        lm_handler: LMHandler,
        environment: BaseEnv,
    ) -> RLMIteration:
        """
        Perform a single iteration of the RLM, including prompting the model
        and code execution + tool execution.
        """
        iter_start = time.perf_counter()
        if self.on_root_chunk is not None and self.depth == 0:
            response = lm_handler.completion(prompt, on_chunk=self.on_root_chunk)
        else:
            response = lm_handler.completion(prompt)
        code_block_strs = find_code_blocks(response)
        code_blocks: list[CodeBlock] = []

        for code_block_str in code_block_strs:
            code_result: REPLResult = environment.execute_code(code_block_str)
            code_blocks.append(CodeBlock(code=code_block_str, result=code_result))

        iteration_time = time.perf_counter() - iter_start
        return RLMIteration(
            prompt=prompt,
            response=response,
            code_blocks=code_blocks,
            iteration_time=iteration_time,
        )

    def _cached_prompt(
        self,
        message_history: list[dict[str, Any]],
        root_prompt: str | None,
        iteration_index: int,
        context_count: int,
        history_count: int,
    ) -> list[dict[str, Any]]:
        """Build current prompt using a prefix cache keyed by conversation state."""
        user_prompt = build_user_prompt(root_prompt, iteration_index, context_count, history_count)
        prefix_key = (
            f"{len(message_history)}:{hash(str(message_history[-1])) if message_history else 0}"
        )

        cached_prefix = self._prefix_prompt_cache.get(prefix_key)
        if cached_prefix is None:
            cached_prefix = list(message_history)
            self._prefix_prompt_cache[prefix_key] = cached_prefix
            if len(self._prefix_prompt_cache) > 128:
                oldest_key = next(iter(self._prefix_prompt_cache))
                del self._prefix_prompt_cache[oldest_key]

        return [*cached_prefix, user_prompt]

    # ------------------------------------------------------------------
    # Compaction helpers
    # ------------------------------------------------------------------

    def _get_compaction_status(self, message_history: list[dict[str, Any]]) -> tuple[int, int, int]:
        """Return (current_tokens, threshold_tokens, max_tokens) for compaction."""
        model_name = (
            self.backend_kwargs.get("model_name", "unknown") if self.backend_kwargs else "unknown"
        )
        max_tokens = get_context_limit(model_name)
        current_tokens = count_tokens(message_history, model_name)
        threshold_tokens = int(self.compaction_threshold_pct * max_tokens)
        return current_tokens, threshold_tokens, max_tokens

    def _compact_history(
        self,
        lm_handler: LMHandler,
        environment: BaseEnv,
        message_history: list[dict[str, Any]],
        compaction_count: int = 1,
    ) -> list[dict[str, Any]]:
        """
        Summarize current trajectory, append summary to REPL history, and return
        a short message_history with the summary as the new starting point.
        """
        summary_prompt = message_history + [
            {
                "role": "user",
                "content": (
                    "Summarize your progress so far. Include:\n"
                    "1. Which steps/sub-tasks you have completed and which remain.\n"
                    "2. Any concrete intermediate results (numbers, values, variable names) "
                    "you computed — preserve these exactly.\n"
                    "3. What your next action should be.\n"
                    "Be concise (1–3 paragraphs) but preserve all key results and your "
                    "current position in the task."
                ),
            }
        ]
        summary = lm_handler.completion(summary_prompt)
        if hasattr(environment, "append_compaction_entry"):
            environment.append_compaction_entry({"type": "summary", "content": summary})
        # Keep system + initial assistant (metadata), then summary + continue
        new_history = message_history[:2] + [
            {"role": "assistant", "content": summary},
            {
                "role": "user",
                "content": (
                    f"Your conversation has been compacted {compaction_count} time(s). "
                    "Continue from the above summary. Do NOT repeat work you have already "
                    "completed. Use SHOW_VARS() to check which REPL variables exist, "
                    "and check `history` for full context. "
                    "Your next action:"
                ),
            },
        ]
        return new_history

    async def acompletion(
        self,
        prompt: str | dict[str, Any],
        root_prompt: str | None = None,
    ) -> RLMChatCompletion:
        """Asynchronous completion path that preserves existing sync semantics."""
        return await asyncio.to_thread(self.completion, prompt, root_prompt)

    def _default_answer(self, message_history: list[dict[str, Any]], lm_handler: LMHandler) -> str:
        """
        Default behavior if the RLM runs out of iterations and does not find a final answer.
        It will take the message history, and try to generate a final answer from it.
        """
        current_prompt = message_history + [
            {
                "role": "assistant",
                "content": "Please provide a final answer to the user's question based on the information provided.",
            }
        ]
        response = lm_handler.completion(current_prompt)

        if self.logger:
            self.logger.log(
                RLMIteration(
                    prompt=current_prompt,
                    response=response,
                    final_answer=response,
                    code_blocks=[],
                )
            )

        return response

    def _fallback_answer(self, message: str | dict[str, Any]) -> RLMChatCompletion:
        """
        Fallback behavior if the RLM is actually at max depth, and should be treated as an LM.
        """
        client: BaseLM = get_client(cast(ClientBackend, self.backend), self.backend_kwargs or {})
        start_time = time.perf_counter()
        if isinstance(message, dict):
            normalized_message: str | list[dict[str, Any]] = str(message)
        else:
            normalized_message = message
        response = client.completion(normalized_message)
        end_time = time.perf_counter()
        usage = client.get_usage_summary()
        return self._build_completion_result(
            prompt=normalized_message,
            response=response,
            usage=usage,
            execution_time=end_time - start_time,
        )

    def _validate_persistent_environment_support(self) -> None:
        """
        Validate that the configured environment type supports persistent mode.

        Persistent mode requires environments to implement:
        - update_handler_address(address): Update LM handler address between calls
        - add_context(payload, index): Add new context for multi-turn conversations
        - get_context_count(): Return the number of loaded contexts

        Currently only 'local' (LocalREPL) supports these methods.

        Raises:
            ValueError: If the environment type does not support persistent mode.
        """
        # Known environments that support persistence
        persistent_supported_environments = {"local"}

        if self.environment_type not in persistent_supported_environments:
            raise ValueError(
                f"persistent=True is not supported for environment type '{self.environment_type}'. "
                f"Persistent mode requires environments that implement update_handler_address(), "
                f"add_context(), and get_context_count(). "
                f"Supported environments: {sorted(persistent_supported_environments)}"
            )

    @staticmethod
    def _env_supports_persistence(env: object) -> bool:
        """Check if an environment instance supports persistent mode methods."""
        return isinstance(env, SupportsPersistence)

    def close(self) -> None:
        """Clean up persistent environment. Call when done with multi-turn conversations."""
        if self._persistent_env is not None:
            if hasattr(self._persistent_env, "cleanup"):
                self._persistent_env.cleanup()
            self._persistent_env = None

    def __enter__(self) -> "RLM":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        self.close()
        return False
