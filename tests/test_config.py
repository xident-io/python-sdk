"""Tests for SDK configuration."""

import platform
import sys

import pytest

from xident._config import SDK_VERSION, Config


class TestConfig:
    def test_defaults(self) -> None:
        config = Config(api_key="sk_test_123")
        assert config.api_key == "sk_test_123"
        assert config.base_url == "http://localhost:9000"
        assert config.timeout == 30
        assert config.max_retries == 3
        assert config.headers is None

    def test_custom_values(self) -> None:
        config = Config(
            api_key="sk_test_abc",
            base_url="https://custom.api.io",
            timeout=60,
            max_retries=5,
            headers={"X-Custom": "value"},
        )
        assert config.api_key == "sk_test_abc"
        assert config.base_url == "https://custom.api.io"
        assert config.timeout == 60
        assert config.max_retries == 5
        assert config.headers == {"X-Custom": "value"}

    def test_empty_api_key_raises(self) -> None:
        with pytest.raises(ValueError, match="API key cannot be empty"):
            Config(api_key="")

    def test_trailing_slash_stripped(self) -> None:
        config = Config(api_key="sk_test_123", base_url="https://api.xident.io/")
        assert config.base_url == "https://api.xident.io"

    def test_multiple_trailing_slashes_stripped(self) -> None:
        config = Config(api_key="sk_test_123", base_url="https://api.xident.io///")
        assert config.base_url == "https://api.xident.io"

    def test_timeout_clamped_to_minimum(self) -> None:
        config = Config(api_key="sk_test_123", timeout=0)
        assert config.timeout == 1

    def test_negative_timeout_clamped(self) -> None:
        config = Config(api_key="sk_test_123", timeout=-5)
        assert config.timeout == 1

    def test_max_retries_clamped_to_zero(self) -> None:
        config = Config(api_key="sk_test_123", max_retries=-1)
        assert config.max_retries == 0

    def test_api_url(self) -> None:
        config = Config(api_key="sk_test_123", base_url="https://api.xident.io")
        assert config.api_url == "https://api.xident.io/verify/v1"

    def test_user_agent(self) -> None:
        config = Config(api_key="sk_test_123")
        py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        expected = f"Xident-Python/{SDK_VERSION} Python/{py_version} {platform.system()}/{platform.release()}"
        assert config.user_agent == expected

    def test_frozen_immutability(self) -> None:
        config = Config(api_key="sk_test_123")
        with pytest.raises(AttributeError):
            config.api_key = "changed"  # type: ignore[misc]
        with pytest.raises(AttributeError):
            config.base_url = "changed"  # type: ignore[misc]

    def test_sdk_version_is_string(self) -> None:
        assert isinstance(SDK_VERSION, str)
        assert len(SDK_VERSION) > 0
