from unittest.mock import patch

import pytest

from rlm.core.retry import retry_with_backoff


class TestRetryWithBackoff:
    def test_success_on_first_attempt(self) -> None:
        calls = {"count": 0}

        def succeed() -> str:
            calls["count"] += 1
            return "ok"

        with patch("rlm.core.retry.time.sleep") as sleep_mock:
            result = retry_with_backoff(succeed)

        assert result == "ok"
        assert calls["count"] == 1
        sleep_mock.assert_not_called()

    def test_retries_then_succeeds(self) -> None:
        calls = {"count": 0}

        def flaky() -> str:
            calls["count"] += 1
            if calls["count"] < 3:
                raise ConnectionError("temporary")
            return "done"

        with patch("rlm.core.retry.time.sleep") as sleep_mock:
            result = retry_with_backoff(
                flaky, max_attempts=5, initial_delay=0.5, backoff_factor=2.0
            )

        assert result == "done"
        assert calls["count"] == 3
        assert sleep_mock.call_args_list[0].args == (0.5,)
        assert sleep_mock.call_args_list[1].args == (1.0,)

    def test_raises_after_max_attempts(self) -> None:
        calls = {"count": 0}

        def always_fail() -> str:
            calls["count"] += 1
            raise TimeoutError("boom")

        with patch("rlm.core.retry.time.sleep") as sleep_mock:
            with pytest.raises(TimeoutError, match="boom"):
                retry_with_backoff(always_fail, max_attempts=3, initial_delay=0.1)

        assert calls["count"] == 3
        assert len(sleep_mock.call_args_list) == 2

    def test_exponential_backoff_respects_max_delay(self) -> None:
        def always_fail() -> str:
            raise OSError("still failing")

        with patch("rlm.core.retry.time.sleep") as sleep_mock:
            with pytest.raises(OSError, match="still failing"):
                retry_with_backoff(
                    always_fail,
                    max_attempts=4,
                    initial_delay=1.0,
                    backoff_factor=3.0,
                    max_delay=2.0,
                )

        delays = [call.args[0] for call in sleep_mock.call_args_list]
        assert delays == [1.0, 2.0, 2.0]
