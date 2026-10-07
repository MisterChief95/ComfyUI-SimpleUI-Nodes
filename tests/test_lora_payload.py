import json
import unittest

from simpleui_nodes.lora_payload import (
    DEFAULT_PAYLOAD,
    LoraPayloadError,
    join_trigger_words,
    parse_payload,
    resolve_names,
)


def entry(name="styles/foo.safetensors", **overrides):
    e = {"name": name, "strength_model": 1.0, "strength_clip": 1.0, "enabled": True}
    e.update(overrides)
    return e


def payload(*entries, schema=1, **extra):
    return json.dumps({"schema": schema, "loras": list(entries), **extra})


class ParsePayloadTests(unittest.TestCase):
    def test_default_payload_is_empty(self):
        self.assertEqual(parse_payload(DEFAULT_PAYLOAD), [])

    def test_preserves_array_order(self):
        entries = parse_payload(payload(entry("b.safetensors"), entry("a.safetensors"), entry("c.safetensors")))
        self.assertEqual([e.name for e in entries], ["b.safetensors", "a.safetensors", "c.safetensors"])

    def test_reads_fields(self):
        [e] = parse_payload(payload(entry(strength_model=0.5, strength_clip=-2, enabled=False, trigger_words="x")))
        self.assertEqual((e.strength_model, e.strength_clip, e.enabled, e.trigger_words), (0.5, -2.0, False, "x"))

    def test_zero_strengths_are_kept(self):
        [e] = parse_payload(payload(entry(strength_model=0, strength_clip=0)))
        self.assertEqual((e.strength_model, e.strength_clip, e.enabled), (0.0, 0.0, True))

    def test_trigger_words_optional(self):
        [e] = parse_payload(payload(entry()))
        self.assertEqual(e.trigger_words, "")

    def test_unknown_keys_ignored(self):
        text = payload(entry(thumbnail="x.png", extra={"a": 1}), app_state={"open": True})
        [e] = parse_payload(text)
        self.assertEqual(e.name, "styles/foo.safetensors")

    def assertPayloadError(self, text, fragment):
        with self.assertRaises(LoraPayloadError) as ctx:
            parse_payload(text)
        self.assertIn(fragment, str(ctx.exception))

    def test_malformed_json(self):
        self.assertPayloadError('{"schema": 1, "loras": [', "not valid JSON")

    def test_nan_rejected(self):
        self.assertPayloadError(
            '{"schema":1,"loras":[{"name":"a","strength_model":NaN,"strength_clip":1,"enabled":true}]}', "NaN"
        )

    def test_not_an_object(self):
        self.assertPayloadError("[]", "JSON object")

    def test_non_string(self):
        with self.assertRaises(LoraPayloadError):
            parse_payload(None)

    def test_missing_schema(self):
        self.assertPayloadError('{"loras": []}', "missing the 'schema'")

    def test_future_schema(self):
        self.assertPayloadError(payload(schema=2), "schema 2")

    def test_bad_schema_types(self):
        self.assertPayloadError(payload(schema="1"), "must be an integer")
        self.assertPayloadError(payload(schema=True), "must be an integer")
        self.assertPayloadError(payload(schema=0), ">= 1")

    def test_missing_or_bad_loras_list(self):
        self.assertPayloadError('{"schema": 1}', "missing the 'loras'")
        self.assertPayloadError('{"schema": 1, "loras": {}}', "must be a list")

    def test_entry_not_object(self):
        self.assertPayloadError(payload("foo"), "loras[0] must be an object")

    def test_missing_required_fields(self):
        for key in ("name", "strength_model", "strength_clip", "enabled"):
            e = entry()
            del e[key]
            self.assertPayloadError(payload(e), f"missing '{key}'")

    def test_bad_name(self):
        self.assertPayloadError(payload(entry(name="")), "non-empty string")
        self.assertPayloadError(payload(entry(name=3)), "non-empty string")
        self.assertPayloadError(payload(entry(name="styles\\foo.safetensors")), "forward slashes")

    def test_non_numeric_strengths(self):
        self.assertPayloadError(payload(entry(strength_model="1")), "strength_model must be a number")
        self.assertPayloadError(payload(entry(strength_clip=None)), "strength_clip must be a number")
        self.assertPayloadError(payload(entry(strength_clip=True)), "strength_clip must be a number")

    def test_non_boolean_enabled(self):
        self.assertPayloadError(payload(entry(enabled=1)), "enabled must be true or false")
        self.assertPayloadError(payload(entry(enabled="true")), "enabled must be true or false")

    def test_non_string_trigger_words(self):
        self.assertPayloadError(payload(entry(trigger_words=["a"])), "trigger_words must be a string")

    def test_error_names_the_entry(self):
        self.assertPayloadError(payload(entry(), entry("x.safetensors", enabled=1)), "loras[1] ('x.safetensors')")


class ResolveNamesTests(unittest.TestCase):
    def test_maps_forward_slash_names_to_os_names(self):
        entries = parse_payload(payload(entry("styles/win.safetensors"), entry("bar.safetensors")))
        available = ["bar.safetensors", "styles\\win.safetensors"]
        self.assertEqual(resolve_names(entries, available), ["styles\\win.safetensors", "bar.safetensors"])

    def test_unknown_name_is_named_in_error(self):
        entries = parse_payload(payload(entry("missing/x.safetensors")))
        with self.assertRaises(LoraPayloadError) as ctx:
            resolve_names(entries, ["bar.safetensors"])
        self.assertEqual(str(ctx.exception), "LoRA file not found: 'missing/x.safetensors'")


class TriggerWordTests(unittest.TestCase):
    def test_joins_enabled_entries_only(self):
        entries = parse_payload(
            payload(
                entry(trigger_words="foo style, bar"),
                entry(trigger_words="hidden", enabled=False),
                entry(trigger_words="baz"),
            )
        )
        self.assertEqual(join_trigger_words(entries), "foo style, bar, baz")

    def test_trims_drops_empty_and_dedupes_keeping_first(self):
        entries = parse_payload(
            payload(
                entry(trigger_words="  bar ,, foo "),
                entry(trigger_words=""),
                entry(trigger_words="foo, qux, bar"),
            )
        )
        self.assertEqual(join_trigger_words(entries), "bar, foo, qux")

    def test_dedupe_is_case_sensitive(self):
        entries = parse_payload(payload(entry(trigger_words="Foo"), entry(trigger_words="foo")))
        self.assertEqual(join_trigger_words(entries), "Foo, foo")

    def test_empty(self):
        self.assertEqual(join_trigger_words([]), "")


if __name__ == "__main__":
    unittest.main()
