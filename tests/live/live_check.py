"""Live checks of comfyui-simpleui-nodes against a running ComfyUI.

Needs the pack installed, an SD1.5 checkpoint and two LoRAs. Configure with
environment variables, then run with ComfyUI's Python (needs numpy, Pillow):

    COMFY_DIR=/path/to/ComfyUI CKPT=model.safetensors LORA_A=a.safetensors \
    LORA_B=b.safetensors python tests/live/live_check.py
"""
import json
import os
import shutil
import time
import urllib.error
import urllib.request

import numpy as np
from PIL import Image

URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188")
COMFY_DIR = os.environ["COMFY_DIR"]
OUT = os.path.join(COMFY_DIR, "output")
INPUT = os.path.join(COMFY_DIR, "input")
CKPT = os.environ.get("CKPT", "random_sd15.safetensors")
A = os.environ.get("LORA_A", "styles/test_a.safetensors")
B = os.environ.get("LORA_B", "test_b.safetensors")
results = []


def record(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("PASS" if ok else "FAIL"), name, detail)


def post(prompt):
    req = urllib.request.Request(URL + "/prompt", data=json.dumps({"prompt": prompt}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return 200, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def run(prompt):
    code, body = post(prompt)
    assert code == 200, body
    pid = body["prompt_id"]
    for _ in range(600):
        with urllib.request.urlopen(f"{URL}/history/{pid}") as r:
            h = json.load(r)
        if pid in h and h[pid]["status"].get("completed") is not None:
            entry = h[pid]
            if entry["status"]["status_str"] != "success":
                raise RuntimeError(json.dumps(entry["status"], indent=1))
            return entry
        time.sleep(1)
    raise TimeoutError(pid)


def images(entry, node):
    return [np.asarray(Image.open(f"{OUT}/{i.get('subfolder') and i['subfolder'] + '/'}{i['filename']}"))
            for i in entry["outputs"][node]["images"]]


def lora_entry(name, sm=1.0, sc=1.0, enabled=True, tw=""):
    return {"name": name, "strength_model": sm, "strength_clip": sc, "enabled": enabled, "trigger_words": tw,
            "app_only_field": {"kept": True}}


def stack_json(*entries):
    return json.dumps({"schema": 1, "loras": list(entries), "app_state": "ignored"}, indent=2)


def graph(loras, prefix, seed=42):
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
        "2": {"class_type": "SimpleUILoraStack", "inputs": {"model": ["1", 0], "clip": ["1", 1], "loras": loras}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 1], "text": "a cat"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 1], "text": ""}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 128, "height": 128, "batch_size": 1}},
        "6": {"class_type": "KSampler", "inputs": {"model": ["2", 0], "seed": seed, "steps": 2, "cfg": 7.0,
              "sampler_name": "euler", "scheduler": "normal", "positive": ["3", 0], "negative": ["4", 0],
              "latent_image": ["5", 0], "denoise": 1.0}},
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["1", 2]}},
        "8": {"class_type": "SaveImage", "inputs": {"images": ["7", 0], "filename_prefix": prefix}},
        "9": {"class_type": "PreviewAny", "inputs": {"source": ["2", 2]}},
    }


# --- LoRA Stack -----------------------------------------------------------
r_none = run(graph('{"schema":1,"loras":[]}', "lora_none"))
img_none = images(r_none, "8")[0]

r_ab_off = run(graph(stack_json(lora_entry(A, tw="alpha style, shared"), lora_entry(B, enabled=False, tw="beta")), "lora_a_boff"))
img_ab_off = images(r_ab_off, "8")[0]
trig = r_ab_off["outputs"]["9"]["text"][0]
record("two LoRAs, second disabled: image generated", img_ab_off.shape == (128, 128, 3), str(img_ab_off.shape))
record("enabled LoRA changes the image vs empty stack", not np.array_equal(img_none, img_ab_off))
record("trigger_words output = enabled entries only", trig == "alpha style, shared", repr(trig))

r_a = run(graph(stack_json(lora_entry(A, tw="alpha style, shared")), "lora_a_only"))
record("disabled entry == entry absent (bit-identical image)", np.array_equal(images(r_a, "8")[0], img_ab_off))

r_ab = run(graph(stack_json(lora_entry(A, tw="alpha style, shared"), lora_entry(B, tw="shared, beta")), "lora_a_b"))
img_ab = images(r_ab, "8")[0]
record("enabling the second LoRA changes the image", not np.array_equal(img_ab, img_ab_off))
record("trigger_words dedupe across entries", r_ab["outputs"]["9"]["text"][0] == "alpha style, shared, beta",
       repr(r_ab["outputs"]["9"]["text"][0]))

r_ba = run(graph(stack_json(lora_entry(B, 0.8, 0.3), lora_entry(A, 0.5, 1.2)), "lora_order"))
record("non-trivial strengths run", images(r_ba, "8")[0].shape == (128, 128, 3))

r_zero = run(graph(stack_json(lora_entry(A, 0, 0)), "lora_zero"))
record("enabled entry with both strengths 0 runs (applied as written)", True,
       "image equal to empty stack: %s" % np.array_equal(images(r_zero, "8")[0], img_none))

# Back-to-back identical prompt: ComfyUI's output cache should skip every node.
r_cached = run(graph(stack_json(lora_entry(A, 0, 0)), "lora_zero"))
cached = [m[1]["nodes"] for m in r_cached["status"]["messages"] if m[0] == "execution_cached"]
record("identical stack rerun served from ComfyUI cache", bool(cached) and "2" in cached[0], str(cached))

# --- loras is an optional socket: absent, injected literal, or wired -----------
g_absent = graph("", "lora_absent")
del g_absent["2"]["inputs"]["loras"]
r_absent = run(g_absent)
record("loras absent: model/clip pass through (same image as empty stack)",
       np.array_equal(images(r_absent, "8")[0], img_none) and r_absent["outputs"]["9"]["text"][0] == "")

g_wired = graph(["20", 0], "lora_wired")
g_wired["20"] = {"class_type": "SimpleUIChainInputText",
                 "inputs": {"text": stack_json(lora_entry(A, tw="alpha style, shared"), lora_entry(B, enabled=False, tw="beta")), "name": ""}}
r_wired = run(g_wired)
record("loras wired from a text node == injected literal",
       np.array_equal(images(r_wired, "8")[0], img_ab_off), r_wired["outputs"]["9"]["text"][0])

g_wired_bad = graph(["20", 0], "never")
g_wired_bad["20"] = {"class_type": "SimpleUIChainInputText", "inputs": {"text": stack_json(lora_entry("missing/nope.safetensors")), "name": ""}}
try:
    run(g_wired_bad)
    record("wired invalid payload fails at execution", False)
except RuntimeError as e:
    record("wired invalid payload fails at execution", "LoRA file not found: 'missing/nope.safetensors'" in str(e))

# --- Validation errors --------------------------------------------------------
for label, payload, fragment in [
    ("unknown LoRA name", stack_json(lora_entry("missing/nope.safetensors")), "LoRA file not found: 'missing/nope.safetensors'"),
    ("malformed JSON", '{"schema":1,"loras":[', "not valid JSON"),
    ("future schema", '{"schema":2,"loras":[]}', "schema 2"),
    ("non-numeric strength", stack_json(lora_entry(A, sm="1")), "strength_model must be a number"),
    ("non-boolean enabled", stack_json(lora_entry(A, enabled="yes")), "enabled must be true or false"),
]:
    code, body = post(graph(payload, "never"))
    details = json.dumps(body.get("node_errors", {}))
    record(f"rejected at validation: {label}", code == 400 and fragment in details and COMFY_DIR not in details,
           f"HTTP {code}: " + body.get("node_errors", {}).get("2", {}).get("errors", [{}])[0].get("details", ""))

r_dis_missing = run(graph(stack_json(lora_entry(A), lora_entry("missing/nope.safetensors", enabled=False)), "lora_dis_missing"))
record("disabled entry naming a missing file is accepted", True)

# --- Chain Output -> SaveImage --------------------------------------------------
chain = graph('{"schema":1,"loras":[]}', "chain_direct")
chain["10"] = {"class_type": "SimpleUIChainOutput", "inputs": {"image": ["7", 0], "name": "stage1"}}
chain["11"] = {"class_type": "SaveImage", "inputs": {"images": ["10", 0], "filename_prefix": "chain_out"}}
r_chain = run(chain)
direct, via = images(r_chain, "8")[0], images(r_chain, "11")[0]
record("Chain Output -> SaveImage saves the identical image", np.array_equal(direct, via))
record("Chain Output itself produces no UI output", "10" not in r_chain["outputs"])

# --- Chain Input (Image) / text nodes ------------------------------------------
src = r_chain["outputs"]["11"]["images"][0]["filename"]
shutil.copy(f"{OUT}/{src}", f"{INPUT}/staged_stage1.png")
p = {
    "1": {"class_type": "SimpleUIChainInputImage", "inputs": {"image": "staged_stage1.png", "name": "stage1"}},
    "2": {"class_type": "SimpleUIChainOutput", "inputs": {"image": ["1", 0], "name": "stage2"}},
    "3": {"class_type": "SaveImage", "inputs": {"images": ["2", 0], "filename_prefix": "chain_in"}},
    "4": {"class_type": "SimpleUIChainInputText", "inputs": {"text": "a prompt, with commas\nand lines", "name": "p"}},
    "5": {"class_type": "SimpleUIChainOutputText", "inputs": {"text": ["4", 0], "name": "p_out"}},
    "6": {"class_type": "PreviewAny", "inputs": {"source": ["5", 0]}},
    "7": {"class_type": "PreviewAny", "inputs": {"source": ["1", 1]}},
}
r_in = run(p)
record("Chain Input (Image) loads the staged file unchanged", np.array_equal(images(r_in, "3")[0], via))
record("Chain Input/Output (Text) pass text through verbatim",
       r_in["outputs"]["6"]["text"][0] == "a prompt, with commas\nand lines", repr(r_in["outputs"]["6"]["text"][0]))
code, body = post({"1": p["1"] | {"inputs": {"image": "does_not_exist.png", "name": ""}},
                   "3": {"class_type": "SaveImage", "inputs": {"images": ["1", 0], "filename_prefix": "x"}}})
record("Chain Input (Image) rejects a missing file at validation", code == 400, f"HTTP {code}")

print("\n%d/%d passed" % (sum(ok for _, ok, _ in results), len(results)))
