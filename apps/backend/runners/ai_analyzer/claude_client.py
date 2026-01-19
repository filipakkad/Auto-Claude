"""
Claude SDK client wrapper for AI analysis.
"""

import json
from pathlib import Path
from typing import Any

try:
    from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
    from core.auth import get_sdk_env_vars
    from core.bedrock import get_bedrock_env_vars, get_bedrock_model, is_bedrock_enabled
    from phase_config import resolve_model_id

    CLAUDE_SDK_AVAILABLE = True
except ImportError:
    CLAUDE_SDK_AVAILABLE = False


class ClaudeAnalysisClient:
    """Wrapper for Claude SDK client with analysis-specific configuration."""

    DEFAULT_MODEL = "sonnet"  # Shorthand - resolved via API Profile if configured
    ALLOWED_TOOLS = ["Read", "Glob", "Grep"]
    MAX_TURNS = 50

    def __init__(self, project_dir: Path):
        """
        Initialize Claude client.

        Args:
            project_dir: Root directory of project being analyzed
        """
        if not CLAUDE_SDK_AVAILABLE:
            raise RuntimeError(
                "claude-agent-sdk not available. Install with: pip install claude-agent-sdk"
            )

        self.project_dir = project_dir
        self._validate_oauth_token()

    def _validate_oauth_token(self) -> None:
        """Validate that an authentication token is available."""
        from core.auth import require_auth_token

        require_auth_token()  # Raises ValueError if no token found

    async def run_analysis_query(self, prompt: str) -> str:
        """
        Run a Claude query for analysis.

        Args:
            prompt: The analysis prompt

        Returns:
            Claude's response text
        """
        settings_file = self._create_settings_file()

        try:
            client = self._create_client(settings_file)

            async with client:
                await client.query(prompt)
                return await self._collect_response(client)

        finally:
            # Cleanup settings file
            if settings_file.exists():
                settings_file.unlink()

    def _create_settings_file(self) -> Path:
        """
        Create temporary security settings file.

        Returns:
            Path to settings file
        """
        settings = {
            "sandbox": {"enabled": True, "autoAllowBashIfSandboxed": True},
            "permissions": {
                "defaultMode": "acceptEdits",
                "allow": [
                    "Read(./**)",
                    "Glob(./**)",
                    "Grep(./**)",
                ],
            },
        }

        settings_file = self.project_dir / ".claude_ai_analyzer_settings.json"
        with open(settings_file, "w") as f:
            json.dump(settings, f, indent=2)

        return settings_file

    def _create_client(self, settings_file: Path) -> Any:
        """
        Create configured Claude SDK client.

        Args:
            settings_file: Path to security settings file

        Returns:
            ClaudeSDKClient instance
        """
        system_prompt = (
            f"You are a senior software architect analyzing this codebase. "
            f"Your working directory is: {self.project_dir.resolve()}\n"
            f"Use Read, Grep, and Glob tools to analyze actual code. "
            f"Output your analysis as valid JSON only."
        )

        # Resolve model and build SDK environment
        model = resolve_model_id(self.DEFAULT_MODEL)
        sdk_env = get_sdk_env_vars()

        # Add Bedrock-specific configuration if enabled
        if is_bedrock_enabled():
            from core.bedrock import remove_oauth_from_env
            sdk_env.update(get_bedrock_env_vars())
            model = get_bedrock_model(model)
            remove_oauth_from_env(sdk_env)

        return ClaudeSDKClient(
            options=ClaudeAgentOptions(
                model=model,
                system_prompt=system_prompt,
                allowed_tools=self.ALLOWED_TOOLS,
                max_turns=self.MAX_TURNS,
                cwd=str(self.project_dir.resolve()),
                settings=str(settings_file.resolve()),
                env=sdk_env,
            )
        )

    async def _collect_response(self, client: Any) -> str:
        """
        Collect text response from Claude client.

        Args:
            client: ClaudeSDKClient instance

        Returns:
            Collected response text
        """
        response_text = ""

        async for msg in client.receive_response():
            msg_type = type(msg).__name__

            if msg_type == "AssistantMessage":
                for content in msg.content:
                    if hasattr(content, "text"):
                        response_text += content.text

        return response_text
