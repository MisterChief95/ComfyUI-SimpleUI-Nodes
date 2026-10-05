import comfy.sd
import comfy.utils
import folder_paths

from .lora_payload import (
    LoraPayloadError,
    enabled_entries,
    join_trigger_words,
    parse_payload,
    resolve_names,
)


def _is_empty(loras):
    return loras is None or (isinstance(loras, str) and not loras.strip())


class SimpleUILoraStack:
    """Applies a list of LoRAs, described by a JSON payload, in array order."""

    CATEGORY = "SimpleUI"
    DESCRIPTION = "Applies an ordered list of LoRAs from a JSON payload. Replaces chains of LoraLoader nodes."
    RETURN_TYPES = ("MODEL", "CLIP", "STRING")
    RETURN_NAMES = ("MODEL", "CLIP", "trigger_words")
    FUNCTION = "apply"

    def __init__(self):
        # Loaded LoRA files keyed by ComfyUI-relative name, kept only for the
        # LoRAs used in the latest run so strength-only edits skip file reads.
        self._loaded = {}

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "clip": ("CLIP",),
            },
            # Socket only, no widget: SimpleUI injects the payload into the API
            # JSON at submission, or a text node can be wired in on the canvas.
            "optional": {
                "loras": ("STRING", {"forceInput": True}),
            },
        }

    @classmethod
    def VALIDATE_INPUTS(cls, loras=None):
        # Absent, empty, or linked (not known yet; apply() validates it).
        if _is_empty(loras):
            return True
        try:
            entries = parse_payload(loras)
            resolve_names(enabled_entries(entries), folder_paths.get_filename_list("loras"))
        except LoraPayloadError as e:
            return f"LoRA Stack: {e}"
        return True

    def apply(self, model, clip, loras=None):
        if _is_empty(loras):
            return (model, clip, "")
        try:
            entries = parse_payload(loras)
            active = enabled_entries(entries)
            names = resolve_names(active, folder_paths.get_filename_list("loras"))
        except LoraPayloadError as e:
            raise ValueError(f"LoRA Stack: {e}") from None

        loaded = {}
        for entry, name in zip(active, names):
            lora, metadata = loaded.get(name) or self._loaded.get(name) or self._load(name)
            loaded[name] = (lora, metadata)
            model, clip = comfy.sd.load_lora_for_models(
                model, clip, lora, entry.strength_model, entry.strength_clip, lora_metadata=metadata
            )
        self._loaded = loaded

        return (model, clip, join_trigger_words(entries))

    @staticmethod
    def _load(name):
        path = folder_paths.get_full_path_or_raise("loras", name)
        return comfy.utils.load_torch_file(path, safe_load=True, return_metadata=True)
