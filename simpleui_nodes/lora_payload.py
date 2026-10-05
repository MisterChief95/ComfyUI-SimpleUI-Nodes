"""Parsing and validation of the LoRA Stack `loras` payload.

Pure Python with no ComfyUI imports so it can be unit tested in isolation.
"""

import json
import math
from dataclasses import dataclass

SUPPORTED_SCHEMA = 1
DEFAULT_PAYLOAD = '{"schema":1,"loras":[]}'


class LoraPayloadError(ValueError):
    pass


@dataclass(frozen=True)
class LoraEntry:
    name: str
    strength_model: float
    strength_clip: float
    enabled: bool
    trigger_words: str


def _reject_constant(value):
    # json.loads accepts NaN/Infinity by default; they are not valid JSON.
    raise LoraPayloadError(f"loras is not valid JSON: {value} is not allowed")


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def parse_payload(text):
    """Parse a `loras` payload into a list of LoraEntry in array order.

    Raises LoraPayloadError naming the problem. Unknown keys are ignored.
    """
    if not isinstance(text, str):
        raise LoraPayloadError(f"loras must be a string, got {type(text).__name__}")
    try:
        data = json.loads(text, parse_constant=_reject_constant)
    except json.JSONDecodeError as e:
        raise LoraPayloadError(f"loras is not valid JSON: {e}") from None

    if not isinstance(data, dict):
        raise LoraPayloadError("loras must be a JSON object with 'schema' and 'loras' keys")

    if "schema" not in data:
        raise LoraPayloadError("loras is missing the 'schema' key")
    schema = data["schema"]
    if not isinstance(schema, int) or isinstance(schema, bool):
        raise LoraPayloadError(f"loras 'schema' must be an integer, got {schema!r}")
    if schema > SUPPORTED_SCHEMA:
        raise LoraPayloadError(
            f"loras uses schema {schema}, but this node pack supports schema {SUPPORTED_SCHEMA}; update comfyui-simpleui-nodes"
        )
    if schema < 1:
        raise LoraPayloadError(f"loras 'schema' must be >= 1, got {schema}")

    if "loras" not in data:
        raise LoraPayloadError("loras is missing the 'loras' key")
    items = data["loras"]
    if not isinstance(items, list):
        raise LoraPayloadError("loras 'loras' must be a list")

    return [_parse_entry(i, item) for i, item in enumerate(items)]


def _parse_entry(index, item):
    where = f"loras[{index}]"
    if not isinstance(item, dict):
        raise LoraPayloadError(f"{where} must be an object")

    for key in ("name", "strength_model", "strength_clip", "enabled"):
        if key not in item:
            raise LoraPayloadError(f"{where} is missing '{key}'")

    name = item["name"]
    if not isinstance(name, str) or not name.strip():
        raise LoraPayloadError(f"{where}.name must be a non-empty string")
    if "\\" in name:
        raise LoraPayloadError(f"{where}.name '{name}' must use forward slashes")
    where = f"{where} ('{name}')"

    strengths = {}
    for key in ("strength_model", "strength_clip"):
        value = item[key]
        if not _is_number(value):
            raise LoraPayloadError(f"{where}.{key} must be a number, got {value!r}")
        if not math.isfinite(value):
            raise LoraPayloadError(f"{where}.{key} must be finite, got {value!r}")
        strengths[key] = float(value)

    enabled = item["enabled"]
    if not isinstance(enabled, bool):
        raise LoraPayloadError(f"{where}.enabled must be true or false, got {enabled!r}")

    trigger_words = item.get("trigger_words", "")
    if not isinstance(trigger_words, str):
        raise LoraPayloadError(f"{where}.trigger_words must be a string, got {trigger_words!r}")

    return LoraEntry(
        name=name,
        strength_model=strengths["strength_model"],
        strength_clip=strengths["strength_clip"],
        enabled=enabled,
        trigger_words=trigger_words,
    )


def enabled_entries(entries):
    return [e for e in entries if e.enabled]


def resolve_names(entries, available):
    """Map each entry name to the name ComfyUI uses for it.

    `available` is folder_paths.get_filename_list("loras"), which uses OS
    separators. Payload names use forward slashes. Raises LoraPayloadError
    for the first name that is not installed.
    """
    by_slash_name = {n.replace("\\", "/"): n for n in available}
    resolved = []
    for e in entries:
        if e.name not in by_slash_name:
            raise LoraPayloadError(f"LoRA file not found: '{e.name}'")
        resolved.append(by_slash_name[e.name])
    return resolved


def join_trigger_words(entries):
    """Join trigger words of enabled entries with ", ".

    Each entry's trigger_words is split on commas; phrases are trimmed, empty
    ones dropped, and duplicates removed keeping the first occurrence.
    """
    seen = []
    for e in enabled_entries(entries):
        for phrase in e.trigger_words.split(","):
            phrase = phrase.strip()
            if phrase and phrase not in seen:
                seen.append(phrase)
    return ", ".join(seen)
