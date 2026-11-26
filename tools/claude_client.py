"""The one place the pipeline talks to Claude through the Anthropic API.

Two calls, both streamed (long answers never hit an HTTP timeout) and both with the server-side
refusal fallback on, so a rare policy decline is answered by the fallback model instead of stopping
a stage:

    ask_text(system, user)                     -> str      the storyboard planner
    ask_json(system, user, schema, images=...) -> dict     the frame critic (structured output)

`system` is the part of the prompt that does not change between calls (rules, scene catalog): it is
sent as a cached block, so the planner's repair rounds and the critic's beat-by-beat calls pay for
it once. Credentials: ANTHROPIC_API_KEY in the environment or in `.env.local` at the repo root
(git-ignored), or whatever `ant auth login` stored; nothing is ever written to a committed file.
The model is claude-opus-5-5 unless STORYLOOM_CLAUDE_MODEL says otherwise.
"""
import base64
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = os.environ.get("STORYLOOM_CLAUDE_MODEL", "claude-opus-5-5")
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class ClaudeError(RuntimeError):
    """Claude gave no usable answer (refused, ran out of room, or the API failed)."""


def _env_key():
    if os.environ.get("ANTHROPIC_API_KEY"):
        return None                       # the SDK reads it itself
    env = ROOT / ".env.local"
    if env.is_file():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip()
    return None                           # the SDK falls back to an `ant auth login` profile


def client():
    try:
        import anthropic
    except ImportError as exc:
        raise ClaudeError("the anthropic package is not installed: python -m pip install anthropic") from exc
    key = _env_key()
    return anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()


def _image_block(path):
    path = Path(path)
    media = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}[path.suffix.lower()]
    return {"type": "image", "source": {"type": "base64", "media_type": media,
                                        "data": base64.standard_b64encode(path.read_bytes()).decode("ascii")}}


def _call(system, content, *, effort, max_tokens, output_config_extra=None, api=None):
    import anthropic
    api = api or client()
    output_config = {"effort": effort, **(output_config_extra or {})}
    try:
        with api.beta.messages.stream(
            model=MODEL,
            max_tokens=max_tokens,
            betas=[FALLBACK_BETA],
            fallbacks="default",
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            output_config=output_config,
            messages=[{"role": "user", "content": content}],
        ) as stream:
            message = stream.get_final_message()
    except anthropic.AuthenticationError as exc:
        raise ClaudeError("the Anthropic API key was refused (ANTHROPIC_API_KEY or .env.local)") from exc
    except anthropic.RateLimitError as exc:
        raise ClaudeError("rate limited by the Anthropic API after the SDK's retries; try again later") from exc
    except anthropic.APIStatusError as exc:
        raise ClaudeError(f"Anthropic API error {exc.status_code}: {exc.message}") from exc
    except anthropic.APIConnectionError as exc:
        raise ClaudeError(f"the Anthropic API could not be reached: {exc}") from exc
    if message.stop_reason == "refusal":
        details = getattr(message, "stop_details", None)
        raise ClaudeError(f"Claude declined ({getattr(details, 'category', None)}): {getattr(details, 'explanation', '')}")
    if message.stop_reason == "max_tokens":
        raise ClaudeError(f"the answer was cut off at max_tokens={max_tokens}")
    return "".join(b.text for b in message.content if getattr(b, "type", None) == "text")


def ask_text(system, user, *, effort="high", max_tokens=64000, api=None):
    return _call(system, [{"type": "text", "text": user}], effort=effort, max_tokens=max_tokens, api=api)


def ask_json(system, user, schema, *, images=(), effort="high", max_tokens=16000, api=None):
    """A JSON object that matches `schema` (structured output: the API enforces it)."""
    import json
    content = [_image_block(p) for p in images] + [{"type": "text", "text": user}]
    text = _call(system, content, effort=effort, max_tokens=max_tokens, api=api,
                 output_config_extra={"format": {"type": "json_schema", "schema": schema}})
    try:
        return json.loads(text)
    except ValueError as exc:
        raise ClaudeError(f"the structured answer was not JSON: {text[:200]!r}") from exc
