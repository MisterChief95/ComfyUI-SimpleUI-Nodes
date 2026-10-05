from .chain import (
    SimpleUIChainInputImage,
    SimpleUIChainInputText,
    SimpleUIChainOutput,
    SimpleUIChainOutputText,
)
from .lora_stack import SimpleUILoraStack
from .version import CONTRACT_VERSION, PACK_NAME, PACK_VERSION

NODE_CLASS_MAPPINGS = {
    "SimpleUILoraStack": SimpleUILoraStack,
    "SimpleUIChainOutput": SimpleUIChainOutput,
    "SimpleUIChainOutputText": SimpleUIChainOutputText,
    "SimpleUIChainInputImage": SimpleUIChainInputImage,
    "SimpleUIChainInputText": SimpleUIChainInputText,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SimpleUILoraStack": "LoRA Stack",
    "SimpleUIChainOutput": "Chain Output (Image)",
    "SimpleUIChainOutputText": "Chain Output (Text)",
    "SimpleUIChainInputImage": "Chain Input (Image)",
    "SimpleUIChainInputText": "Chain Input (Text)",
}
