"""Minimal stand-ins for the ComfyUI modules the pack imports.

Installed into sys.modules before importing simpleui_nodes so the tests run
without ComfyUI or torch.
"""

import sys
import types

LORAS = ["styles/foo.safetensors", "bar.safetensors", "styles\\win.safetensors"]

calls = []  # (model, clip, lora, strength_model, strength_clip, metadata)
loads = []  # full paths read from disk


def reset():
    calls.clear()
    loads.clear()


def _install():
    folder_paths = types.ModuleType("folder_paths")
    folder_paths.get_filename_list = lambda folder: list(LORAS) if folder == "loras" else []

    def get_full_path_or_raise(folder, name):
        if name not in LORAS:
            raise FileNotFoundError(f"Model in folder '{folder}' with filename '{name}' not found.")
        return "/models/loras/" + name

    folder_paths.get_full_path_or_raise = get_full_path_or_raise

    comfy = types.ModuleType("comfy")
    comfy_sd = types.ModuleType("comfy.sd")
    comfy_utils = types.ModuleType("comfy.utils")

    def load_torch_file(path, safe_load=False, return_metadata=False):
        loads.append(path)
        return {"weights": path}, {"meta": path}

    def load_lora_for_models(model, clip, lora, strength_model, strength_clip, lora_metadata=None):
        calls.append((model, clip, lora, strength_model, strength_clip, lora_metadata))
        return model + [lora["weights"]], clip + [lora["weights"]]

    comfy_utils.load_torch_file = load_torch_file
    comfy_sd.load_lora_for_models = load_lora_for_models
    comfy.sd = comfy_sd
    comfy.utils = comfy_utils

    nodes = types.ModuleType("nodes")

    class LoadImage:
        @classmethod
        def INPUT_TYPES(cls):
            return {"required": {"image": (["a.png"], {"image_upload": True})}}

        RETURN_TYPES = ("IMAGE", "MASK")
        FUNCTION = "load_image"

        def load_image(self, image):
            return ("image:" + image, "mask:" + image)

        @classmethod
        def IS_CHANGED(cls, image):
            return "hash:" + image

        @classmethod
        def VALIDATE_INPUTS(cls, image):
            return True

    nodes.LoadImage = LoadImage

    sys.modules.update(
        {
            "folder_paths": folder_paths,
            "comfy": comfy,
            "comfy.sd": comfy_sd,
            "comfy.utils": comfy_utils,
            "nodes": nodes,
        }
    )


_install()
