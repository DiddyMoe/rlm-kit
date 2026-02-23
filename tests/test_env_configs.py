"""Tests for environment configuration dataclasses and config_from_kwargs helper."""

from rlm.environments.base_env import config_from_kwargs
from rlm.environments.daytona_repl import DaytonaREPLConfig
from rlm.environments.docker_repl import DockerREPLConfig
from rlm.environments.e2b_repl import E2BREPLConfig
from rlm.environments.modal_repl import ModalREPLConfig
from rlm.environments.prime_repl import PrimeREPLConfig


class TestConfigFromKwargs:
    """Tests for the config_from_kwargs helper."""

    def test_splits_known_and_unknown_keys(self):
        kwargs: dict[str, int | bool | str] = {
            "timeout": 999,
            "persistent": True,
            "depth": 3,
            "unknown_extra": "value",
        }
        config, extra = config_from_kwargs(E2BREPLConfig, kwargs)
        assert config.timeout == 999
        assert config.persistent is True
        assert config.depth == 3
        assert extra == {"unknown_extra": "value"}

    def test_defaults_applied_for_missing_keys(self):
        kwargs: dict[str, object] = {"unknown_extra": "value"}
        config, extra = config_from_kwargs(E2BREPLConfig, kwargs)
        assert config.timeout == 300  # default
        assert config.persistent is False
        assert config.depth == 1
        assert extra == {"unknown_extra": "value"}

    def test_empty_kwargs_uses_all_defaults(self):
        config, extra = config_from_kwargs(ModalREPLConfig, {})
        assert config.app_name == "rlm-sandbox"
        assert config.timeout == 600
        assert extra == {}


class TestDaytonaREPLConfigRoundTrip:
    """Test DaytonaREPLConfig to_dict/from_dict round-trip."""

    def test_round_trip_defaults(self):
        config = DaytonaREPLConfig()
        data = config.to_dict()
        restored = DaytonaREPLConfig.from_dict(data)
        assert restored.api_key == config.api_key
        assert restored.target == config.target
        assert restored.name == config.name
        assert restored.timeout == config.timeout
        assert restored.cpu == config.cpu
        assert restored.memory == config.memory
        assert restored.disk == config.disk
        assert restored.auto_stop_interval == config.auto_stop_interval
        assert restored.persistent == config.persistent
        assert restored.depth == config.depth

    def test_round_trip_with_lm_handler_address(self):
        config = DaytonaREPLConfig(lm_handler_address=("127.0.0.1", 9999))
        data = config.to_dict()
        assert data["lm_handler_address"] == ["127.0.0.1", 9999]
        restored = DaytonaREPLConfig.from_dict(data)
        assert restored.lm_handler_address == ("127.0.0.1", 9999)

    def test_round_trip_custom_values(self):
        config = DaytonaREPLConfig(
            api_key="test-key",
            target="eu",
            name="my-sandbox",
            timeout=1200,
            cpu=4,
            memory=8,
            disk=20,
            auto_stop_interval=30,
            depth=2,
        )
        data = config.to_dict()
        restored = DaytonaREPLConfig.from_dict(data)
        assert restored.api_key == "test-key"
        assert restored.target == "eu"
        assert restored.name == "my-sandbox"
        assert restored.timeout == 1200
        assert restored.cpu == 4
        assert restored.memory == 8
        assert restored.disk == 20
        assert restored.auto_stop_interval == 30
        assert restored.depth == 2


class TestPrimeREPLConfigRoundTrip:
    """Test PrimeREPLConfig to_dict/from_dict round-trip."""

    def test_round_trip(self):
        config = PrimeREPLConfig(
            name="test",
            docker_image="python:3.12",
            timeout_minutes=30,
            network_access=False,
        )
        data = config.to_dict()
        restored = PrimeREPLConfig.from_dict(data)
        assert restored.name == "test"
        assert restored.docker_image == "python:3.12"
        assert restored.timeout_minutes == 30
        assert restored.network_access is False


class TestModalREPLConfigRoundTrip:
    """Test ModalREPLConfig to_dict/from_dict round-trip."""

    def test_round_trip(self):
        config = ModalREPLConfig(app_name="custom-app", timeout=900, depth=3)
        data = config.to_dict()
        restored = ModalREPLConfig.from_dict(data)
        assert restored.app_name == "custom-app"
        assert restored.timeout == 900
        assert restored.depth == 3


class TestDockerREPLConfigRoundTrip:
    """Test DockerREPLConfig to_dict/from_dict round-trip."""

    def test_round_trip(self):
        config = DockerREPLConfig(
            image="ubuntu:22.04",
            lm_handler_address=("localhost", 8080),
        )
        data = config.to_dict()
        restored = DockerREPLConfig.from_dict(data)
        assert restored.image == "ubuntu:22.04"
        assert restored.lm_handler_address == ("localhost", 8080)


class TestE2BREPLConfigRoundTrip:
    """Test E2BREPLConfig to_dict/from_dict round-trip."""

    def test_round_trip(self):
        config = E2BREPLConfig(timeout=600, depth=2)
        data = config.to_dict()
        restored = E2BREPLConfig.from_dict(data)
        assert restored.timeout == 600
        assert restored.depth == 2
