"""Production must never start with a public or missing JWT signing secret."""
import pytest
from pydantic import ValidationError

from app.core.config import DEFAULT_SECRET_KEY, Settings


@pytest.mark.parametrize("secret", [DEFAULT_SECRET_KEY, "", "your_secret_key", "replace_with_generated_secret_key", "too-short"])
def test_production_rejects_fallback_and_placeholder_keys(secret):
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None, ENVIRONMENT="production", SECRET_KEY=secret)
    assert "Production requires a generated SECRET_KEY" in str(exc.value)
    assert "input_value" not in str(exc.value)


def test_development_fallback_is_explicitly_not_production():
    assert Settings(_env_file=None, ENVIRONMENT="development", SECRET_KEY=DEFAULT_SECRET_KEY).ENVIRONMENT == "development"
    assert Settings(_env_file=None, ENVIRONMENT="production", SECRET_KEY="a-generated-test-key-with-over-32-characters").ENVIRONMENT == "production"
