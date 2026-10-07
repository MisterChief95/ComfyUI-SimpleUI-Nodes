"""ComfyUI entry point for comfyui-simpleui-nodes."""

from .simpleui_nodes import (
    NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS,
    PACK_VERSION,
    routes,  # noqa: F401  registers GET /simpleui/pack
)

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "PACK_VERSION"]
