"""Tests for the exception hierarchy."""

import pytest

from xident.errors import (
    APIError,
    AuthenticationError,
    NetworkError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
    XidentError,
)


class TestExceptionHierarchy:
    def test_xident_error_is_base(self) -> None:
        assert issubclass(APIError, XidentError)
        assert issubclass(NetworkError, XidentError)

    def test_api_error_subtypes(self) -> None:
        assert issubclass(AuthenticationError, APIError)
        assert issubclass(ValidationError, APIError)
        assert issubclass(NotFoundError, APIError)
        assert issubclass(RateLimitError, APIError)
        assert issubclass(ServerError, APIError)

    def test_all_inherit_from_exception(self) -> None:
        for cls in [
            XidentError,
            APIError,
            AuthenticationError,
            ValidationError,
            NotFoundError,
            RateLimitError,
            ServerError,
            NetworkError,
        ]:
            assert issubclass(cls, Exception)


class TestXidentError:
    def test_message(self) -> None:
        err = XidentError("test message")
        assert err.message == "test message"
        assert str(err) == "test message"


class TestAPIError:
    def test_attributes(self) -> None:
        err = APIError(
            "test error",
            status_code=400,
            error_code="INVALID_REQUEST",
            request_id="req_123",
        )
        assert err.message == "test error"
        assert err.status_code == 400
        assert err.error_code == "INVALID_REQUEST"
        assert err.request_id == "req_123"

    def test_str_formatting(self) -> None:
        err = APIError(
            "Something went wrong",
            status_code=500,
            error_code="INTERNAL",
            request_id="req_abc",
        )
        s = str(err)
        assert "Something went wrong" in s
        assert "code=INTERNAL" in s
        assert "request_id=req_abc" in s
        assert "status=500" in s

    def test_str_without_optional_fields(self) -> None:
        err = APIError("error", status_code=400)
        s = str(err)
        assert "error" in s
        assert "status=400" in s
        assert "code=" not in s
        assert "request_id=" not in s

    def test_defaults(self) -> None:
        err = APIError("test", status_code=400)
        assert err.error_code == ""
        assert err.request_id is None


class TestAuthenticationError:
    def test_catch_as_api_error(self) -> None:
        err = AuthenticationError("Unauthorized", status_code=401)
        with pytest.raises(APIError):
            raise err

    def test_catch_as_xident_error(self) -> None:
        err = AuthenticationError("Forbidden", status_code=403)
        with pytest.raises(XidentError):
            raise err


class TestRateLimitError:
    def test_retry_after(self) -> None:
        err = RateLimitError(
            "Rate limited",
            status_code=429,
            retry_after=30,
        )
        assert err.retry_after == 30
        assert err.status_code == 429

    def test_retry_after_none(self) -> None:
        err = RateLimitError("Rate limited", status_code=429)
        assert err.retry_after is None

    def test_default_status_code(self) -> None:
        err = RateLimitError("Rate limited")
        assert err.status_code == 429


class TestNetworkError:
    def test_catch_as_xident_error(self) -> None:
        err = NetworkError("Connection refused")
        with pytest.raises(XidentError):
            raise err

    def test_not_api_error(self) -> None:
        err = NetworkError("Timeout")
        assert not isinstance(err, APIError)
