"""Shared password-setting policy; authentication accepts shorter legacy secrets."""

from typing import Annotated

from pydantic import AfterValidator, Field, SecretStr


def validate_new_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    _validate_bytes(password)
    return password


def _validate_bytes(password: str) -> None:
    try:
        encoded = password.encode("utf-8")
    except UnicodeError:
        raise ValueError("Password must be valid UTF-8") from None
    if len(encoded) > 72:
        raise ValueError("Password must be at most 72 UTF-8 bytes")


def _secret_bytes(value: SecretStr) -> SecretStr:
    _validate_bytes(value.get_secret_value())
    return value


NewPassword = Annotated[
    SecretStr, Field(min_length=8, max_length=72, repr=False), AfterValidator(_secret_bytes)
]
# Do not lock out existing users whose passwords predate the 8-character rule.
ExistingPassword = Annotated[
    SecretStr, Field(min_length=1, max_length=72, repr=False), AfterValidator(_secret_bytes)
]
