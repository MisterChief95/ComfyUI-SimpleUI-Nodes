import json
import unittest

from tests import comfy_stubs

from simpleui_nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
from simpleui_nodes.chain import (
    SimpleUIChainInputImage,
    SimpleUIChainInputText,
    SimpleUIChainOutput,
    SimpleUIChainOutputText,
)
from simpleui_nodes.lora_stack import SimpleUILoraStack


def stack(*entries):
    return json.dumps({"schema": 1, "loras": list(entries)})


def entry(name, sm=1.0, sc=1.0, enabled=True, tw=""):
    return {"name": name, "strength_model": sm, "strength_clip": sc, "enabled": enabled, "trigger_words": tw}


class MappingTests(unittest.TestCase):
    def test_all_nodes_registered_with_prefix_and_category(self):
        self.assertEqual(set(NODE_CLASS_MAPPINGS), set(NODE_DISPLAY_NAME_MAPPINGS))
        self.assertEqual(set(NODE_CLASS_MAPPINGS), {
            "SimpleUILoraStack", "SimpleUIChainOutput", "SimpleUIChainOutputText",
            "SimpleUIChainInputImage", "SimpleUIChainInputText",
        })
        for cls in NODE_CLASS_MAPPINGS.values():
            self.assertEqual(cls.CATEGORY, "SimpleUI")
            self.assertFalse(getattr(cls, "OUTPUT_NODE", False))

    def test_input_names_match_contract(self):
        def names(cls):
            types = cls.INPUT_TYPES()
            return list(types["required"]) + list(types.get("optional", {}))
        self.assertEqual(names(SimpleUILoraStack), ["model", "clip", "loras"])
        self.assertEqual(names(SimpleUIChainOutput), ["image", "name"])
        self.assertEqual(names(SimpleUIChainOutputText), ["text", "name"])
        self.assertEqual(names(SimpleUIChainInputImage), ["image", "name"])
        self.assertEqual(names(SimpleUIChainInputText), ["text", "name"])

    def test_loras_is_an_optional_socket_without_widget(self):
        types = SimpleUILoraStack.INPUT_TYPES()
        self.assertNotIn("loras", types["required"])
        self.assertEqual(types["optional"]["loras"], ("STRING", {"forceInput": True}))

    def test_defaults(self):
        for cls in (SimpleUIChainOutput, SimpleUIChainOutputText, SimpleUIChainInputImage, SimpleUIChainInputText):
            self.assertEqual(cls.INPUT_TYPES()["required"]["name"][1]["default"], "")


class LoraStackTests(unittest.TestCase):
    def setUp(self):
        comfy_stubs.reset()
        self.node = SimpleUILoraStack()

    def test_applies_enabled_entries_in_order(self):
        text = stack(
            entry("bar.safetensors", 0.5, 0.25, tw="b"),
            entry("styles/foo.safetensors", enabled=False, tw="hidden"),
            entry("styles/win.safetensors", 0, 0, tw="w"),
        )
        model, clip, words = self.node.apply([], [], text)
        self.assertEqual(model, ["/models/loras/bar.safetensors", "/models/loras/styles\\win.safetensors"])
        self.assertEqual(clip, model)
        self.assertEqual([(c[3], c[4]) for c in comfy_stubs.calls], [(0.5, 0.25), (0.0, 0.0)])
        self.assertEqual(comfy_stubs.calls[0][5], {"meta": "/models/loras/bar.safetensors"})
        self.assertEqual(words, "b, w")

    def test_empty_and_all_disabled_pass_through(self):
        model, clip = object(), object()
        for text in ('{"schema":1,"loras":[]}', stack(entry("bar.safetensors", enabled=False, tw="x"))):
            out = self.node.apply(model, clip, text)
            self.assertIs(out[0], model)
            self.assertIs(out[1], clip)
            self.assertEqual(out[2], "")
        self.assertEqual(comfy_stubs.calls, [])

    def test_absent_or_blank_payload_passes_through(self):
        model, clip = object(), object()
        for kwargs in ({}, {"loras": None}, {"loras": ""}, {"loras": "  \n"}):
            out = self.node.apply(model, clip, **kwargs)
            self.assertIs(out[0], model)
            self.assertIs(out[1], clip)
            self.assertEqual(out[2], "")
            self.assertIs(SimpleUILoraStack.VALIDATE_INPUTS(**kwargs), True)
        self.assertEqual(comfy_stubs.calls, [])

    def test_unknown_lora_raises_naming_file(self):
        with self.assertRaisesRegex(ValueError, "LoRA file not found: 'nope.safetensors'"):
            self.node.apply([], [], stack(entry("nope.safetensors")))

    def test_disabled_unknown_lora_is_ignored(self):
        self.node.apply([], [], stack(entry("nope.safetensors", enabled=False)))

    def test_bad_payload_raises(self):
        with self.assertRaisesRegex(ValueError, "LoRA Stack: loras is not valid JSON"):
            self.node.apply([], [], "{")

    def test_reuses_loaded_files_across_runs(self):
        self.node.apply([], [], stack(entry("bar.safetensors"), entry("bar.safetensors", 0.5)))
        self.node.apply([], [], stack(entry("bar.safetensors", 0.3)))
        self.assertEqual(comfy_stubs.loads, ["/models/loras/bar.safetensors"])
        self.node.apply([], [], stack(entry("styles/foo.safetensors")))
        self.node.apply([], [], stack(entry("bar.safetensors")))
        self.assertEqual(comfy_stubs.loads, [
            "/models/loras/bar.safetensors",
            "/models/loras/styles/foo.safetensors",
            "/models/loras/bar.safetensors",
        ])

    def test_validate_inputs(self):
        self.assertIs(SimpleUILoraStack.VALIDATE_INPUTS(stack(entry("bar.safetensors"))), True)
        self.assertIs(SimpleUILoraStack.VALIDATE_INPUTS(None), True)
        self.assertEqual(
            SimpleUILoraStack.VALIDATE_INPUTS(stack(entry("nope.safetensors"))),
            "LoRA Stack: LoRA file not found: 'nope.safetensors'",
        )
        self.assertIn("schema 9", SimpleUILoraStack.VALIDATE_INPUTS('{"schema":9,"loras":[]}'))

    def test_errors_never_contain_host_paths(self):
        msg = SimpleUILoraStack.VALIDATE_INPUTS(stack(entry("nope.safetensors")))
        self.assertNotIn("/models", msg)


class ChainTests(unittest.TestCase):
    def test_output_image_is_identity(self):
        image = object()
        self.assertIs(SimpleUIChainOutput().passthrough(image, "stage1")[0], image)

    def test_output_text_is_identity(self):
        self.assertEqual(SimpleUIChainOutputText().passthrough("a prompt", ""), ("a prompt",))

    def test_input_text_returns_widget_value(self):
        self.assertEqual(SimpleUIChainInputText().passthrough("hello", "x"), ("hello",))

    def test_input_image_delegates_to_load_image(self):
        node = SimpleUIChainInputImage()
        self.assertEqual(node.load_chain_image("a.png", "x"), ("image:a.png", "mask:a.png"))
        self.assertEqual(SimpleUIChainInputImage.RETURN_TYPES, ("IMAGE", "MASK"))
        self.assertTrue(SimpleUIChainInputImage.INPUT_TYPES()["required"]["image"][1]["image_upload"])
        self.assertEqual(SimpleUIChainInputImage.IS_CHANGED(image="a.png", name="x"), "hash:a.png")


if __name__ == "__main__":
    unittest.main()
