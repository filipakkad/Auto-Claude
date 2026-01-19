"""
AWS Bedrock Configuration
=========================

Utilities for running Auto Claude with AWS Bedrock as the model provider.

Usage:
    Set in your .env file:
        CLAUDE_CODE_USE_BEDROCK=true
        AWS_PROFILE=your-profile
        AWS_REGION=us-east-1
"""

import os

# OAuth token env vars that must be cleared when using Bedrock
OAUTH_TOKEN_VARS = ["CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY"]

# Model mapping: friendly names -> Bedrock model IDs
BEDROCK_MODELS = {
    "opus": "us.anthropic.claude-opus-4-5-20251101-v1:0",
    "sonnet": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "haiku": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
}

DEFAULT_BEDROCK_MODEL = BEDROCK_MODELS["sonnet"]

# AWS env vars to pass to subprocesses
AWS_ENV_VARS = [
    "AWS_PROFILE", "AWS_REGION", "AWS_DEFAULT_REGION",
    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
]


def is_bedrock_enabled() -> bool:
    """Check if AWS Bedrock mode is enabled."""
    return os.environ.get("CLAUDE_CODE_USE_BEDROCK", "").lower() in ("true", "1", "yes")


def clear_oauth_for_bedrock() -> None:
    """
    Clear OAuth tokens from environment when Bedrock mode is enabled.

    Must be called after loading .env to prevent OAuth from interfering
    with AWS authentication in CLI subprocesses.
    """
    if is_bedrock_enabled():
        for var in OAUTH_TOKEN_VARS:
            os.environ.pop(var, None)


def get_bedrock_model(model_hint: str | None = None) -> str:
    """
    Resolve a model name to a Bedrock model ID.

    Args:
        model_hint: Model name (opus/sonnet/haiku) or full Bedrock ID

    Returns:
        Full Bedrock model ID
    """
    # Environment override takes precedence
    env_model = os.environ.get("BEDROCK_MODEL")
    if env_model:
        return _resolve_model(env_model)

    if model_hint:
        return _resolve_model(model_hint)

    return DEFAULT_BEDROCK_MODEL


def _resolve_model(model: str) -> str:
    """Resolve a model string to Bedrock ID."""
    # Already a Bedrock ID
    if model.startswith("us.anthropic.") or model.startswith("anthropic."):
        return model

    # Try direct mapping
    model_lower = model.lower()
    if model_lower in BEDROCK_MODELS:
        return BEDROCK_MODELS[model_lower]

    # Detect family from name (handles claude-sonnet-4-5-20250929 etc.)
    for family in ("opus", "sonnet", "haiku"):
        if family in model_lower:
            return BEDROCK_MODELS[family]

    return DEFAULT_BEDROCK_MODEL


def get_bedrock_env_vars() -> dict[str, str]:
    """
    Get environment variables for Bedrock mode subprocesses.

    Returns:
        Dict of env vars to pass to Claude CLI subprocess
    """
    env = {"CLAUDE_CODE_USE_BEDROCK": "1"}

    for var in AWS_ENV_VARS:
        if value := os.environ.get(var):
            env[var] = value

    # Ensure region is set
    if "AWS_REGION" not in env and "AWS_DEFAULT_REGION" not in env:
        env["AWS_REGION"] = os.environ.get("AWS_REGION", "us-east-1")

    return env


def remove_oauth_from_env(env: dict[str, str]) -> None:
    """Remove OAuth tokens from an env dict (mutates in place)."""
    for var in OAUTH_TOKEN_VARS:
        env.pop(var, None)


def require_bedrock_credentials() -> None:
    """
    Validate AWS credentials are available or raise ValueError.
    """
    has_profile = bool(os.environ.get("AWS_PROFILE"))
    has_keys = bool(os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY"))

    if not has_profile and not has_keys:
        raise ValueError(
            "No AWS credentials found for Bedrock.\n\n"
            "Set AWS_PROFILE in .env for LEAPP/SSO, or set\n"
            "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY for explicit credentials."
        )
