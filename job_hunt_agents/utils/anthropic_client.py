"""Shared helper for calling the Anthropic API with tool-use enforced JSON
output and exponential backoff retries.

Every agent asks Claude to call a single "emit_report" style tool whose
input schema mirrors a Pydantic model. Forcing a tool call (rather than
asking the model to "return only JSON") gives us a validated, parseable
structure every time.
"""

import json
import logging
import time
from typing import Any, Dict, Type, TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

from config import (
    ANTHROPIC_API_KEY,
    BACKOFF_MULTIPLIER,
    INITIAL_BACKOFF_SECONDS,
    MAX_API_RETRIES,
    MAX_TOKENS,
    MODEL,
    REQUEST_TIMEOUT_SECONDS,
)

logger = logging.getLogger("job_hunt_agents")

T = TypeVar("T", bound=BaseModel)

RETRYABLE_ERRORS = (
    anthropic.APIConnectionError,
    anthropic.APITimeoutError,
    anthropic.RateLimitError,
    anthropic.InternalServerError,
)


def _client() -> anthropic.Anthropic:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Export it as an environment "
            "variable or fill it in in config.py."
        )
    return anthropic.Anthropic(
        api_key=ANTHROPIC_API_KEY, timeout=REQUEST_TIMEOUT_SECONDS
    )


def _pydantic_model_to_tool(name: str, description: str, model: Type[BaseModel]) -> Dict[str, Any]:
    """Convert a Pydantic model into an Anthropic tool definition."""
    schema = model.model_json_schema()
    # Anthropic tool schemas don't use the "title" / "$defs" wrapper keys the
    # way OpenAPI does, but passing them through is harmless for Claude.
    return {
        "name": name,
        "description": description,
        "input_schema": schema,
    }


def call_agent_for_json(
    system_prompt: str,
    user_message: str,
    response_model: Type[T],
    tool_name: str = "emit_report",
    tool_description: str = "Return the structured report.",
) -> T:
    """Call Claude with a forced tool call and validate the result against
    a Pydantic model. Retries with exponential backoff on transient errors.

    Args:
        system_prompt: The agent's system prompt.
        user_message: The user-turn content (inputs for this agent).
        response_model: Pydantic model the tool's input must satisfy.
        tool_name: Name of the tool Claude must call.
        tool_description: Description shown to Claude for the tool.

    Returns:
        An instance of response_model populated from Claude's tool call.
    """
    client = _client()
    tool = _pydantic_model_to_tool(tool_name, tool_description, response_model)

    backoff = INITIAL_BACKOFF_SECONDS
    last_error: Exception | None = None

    for attempt in range(1, MAX_API_RETRIES + 1):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                tools=[tool],
                tool_choice={"type": "tool", "name": tool_name},
                messages=[{"role": "user", "content": user_message}],
            )
            for block in response.content:
                if block.type == "tool_use" and block.name == tool_name:
                    try:
                        return response_model.model_validate(block.input)
                    except ValidationError as ve:
                        raise ValueError(
                            f"Claude's tool call did not match the expected "
                            f"schema for {response_model.__name__}: {ve}"
                        ) from ve
            raise ValueError(
                f"Claude did not call the required tool '{tool_name}'. "
                f"Response content: {response.content}"
            )
        except RETRYABLE_ERRORS as exc:
            last_error = exc
            if attempt == MAX_API_RETRIES:
                break
            logger.warning(
                "Anthropic API call failed (attempt %d/%d): %s. Retrying in %.1fs...",
                attempt,
                MAX_API_RETRIES,
                exc,
                backoff,
            )
            time.sleep(backoff)
            backoff *= BACKOFF_MULTIPLIER
        except (anthropic.BadRequestError, anthropic.AuthenticationError, anthropic.PermissionDeniedError):
            # Non-retryable: fail fast with a clear error.
            raise

    raise RuntimeError(
        f"Anthropic API call failed after {MAX_API_RETRIES} attempts: {last_error}"
    )


def dump_json(model: BaseModel, path: str) -> None:
    """Write a Pydantic model to disk as pretty-printed JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(model.model_dump(), f, indent=2, ensure_ascii=False)
    logger.info("Saved %s", path)
