"""Chain marker nodes.

Outputs are plain passthroughs that mark a stage result for the SimpleUI app.
Inputs are entry points the app fills at submission; standalone they use their
own widget value.
"""

import nodes

NAME_INPUT = ("STRING", {"default": "", "tooltip": "Chain reference name. Empty means unnamed."})


class SimpleUIChainOutput:
    CATEGORY = "SimpleUI"
    DESCRIPTION = "Marks this image as the stage result for the next SimpleUI stage. Passes the image through unchanged; wire it into a Save or Preview node."
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "passthrough"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("IMAGE",), "name": NAME_INPUT}}

    def passthrough(self, image, name):
        return (image,)


class SimpleUIChainOutputText:
    CATEGORY = "SimpleUI"
    DESCRIPTION = "Marks this text as the stage result for the next SimpleUI stage. Passes the text through unchanged. Type the text here or connect it from another node; an unconnected, empty text passes an empty string."
    RETURN_TYPES = ("STRING",)
    FUNCTION = "passthrough"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {"name": NAME_INPUT},
            "optional": {"text": ("STRING", {"multiline": True, "default": ""})},
        }

    def passthrough(self, name, text=""):
        return (text,)


class SimpleUIChainInputImage(nodes.LoadImage):
    """LoadImage with a chain `name`; image loading is LoadImage's own."""

    CATEGORY = "SimpleUI"
    DESCRIPTION = "Loads an image like Load Image. SimpleUI replaces the image with a previous stage's output when this node is bound in a chain."
    FUNCTION = "load_chain_image"

    @classmethod
    def INPUT_TYPES(cls):
        types = super().INPUT_TYPES()
        types["required"]["name"] = NAME_INPUT
        return types

    def load_chain_image(self, image, name):
        return self.load_image(image)

    # ComfyUI passes every input to IS_CHANGED, so accept and ignore `name`.
    @classmethod
    def IS_CHANGED(cls, image, name=""):
        return super().IS_CHANGED(image)


class SimpleUIChainInputText:
    CATEGORY = "SimpleUI"
    DESCRIPTION = "Provides text for this stage. SimpleUI replaces the text with a previous stage's output when this node is bound in a chain."
    RETURN_TYPES = ("STRING",)
    FUNCTION = "passthrough"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"text": ("STRING", {"multiline": True, "default": ""}), "name": NAME_INPUT}}

    def passthrough(self, text, name):
        return (text,)
