# ComfyUI-SimpleUI-Nodes

Optional ComfyUI custom nodes that complement [ComfyUI SimpleUI](https://github.com/MisterChief95/ComfyUI-SimpleUI). Add them to a workflow in the ComfyUI canvas, export the workflow as API JSON, and SimpleUI renders richer controls for them. Every node also works in plain ComfyUI without SimpleUI.

- Pack: `comfyui-simpleui-nodes`, version `2.0.0` (`PACK_VERSION`)
- Contract: `2` (the node names, input names, and payload shape below). Contract 2 changed `loras` on LoRA Stack from a required text widget to an optional socket-only input; see the changelog below.
- Category: `SimpleUI`. Every class type starts with `SimpleUI`.
- No dependencies beyond ComfyUI. No front-end JavaScript.

## Install

Clone into `ComfyUI/custom_nodes/` and restart ComfyUI:

```sh
cd ComfyUI/custom_nodes
git clone https://github.com/MisterChief95/ComfyUI-SimpleUI-Nodes comfyui-simpleui-nodes
```

## Nodes

### LoRA Stack (`SimpleUILoraStack`)

Replaces chains of `LoraLoader`.

| Inputs | Outputs |
|---|---|
| `model` MODEL, `clip` CLIP, optional `loras` STRING (socket only, no widget) | `MODEL`, `CLIP`, `trigger_words` STRING |

`loras` has no widget on the canvas, so a workflow exported from ComfyUI has no `loras` key on this node. SimpleUI adds `"loras": "<payload>"` to the node's `inputs` in the API JSON at submission. In plain ComfyUI you can wire any STRING output (for example Chain Input (Text)) into the socket, or leave it unconnected. Unconnected, absent, or blank `loras` passes `model` and `clip` through unchanged with empty `trigger_words`.

The payload is UTF-8 JSON (payload `schema` 1, which is separate from the contract number):

```json
{
  "schema": 1,
  "loras": [
    {
      "name": "styles/foo.safetensors",
      "strength_model": 1.0,
      "strength_clip": 1.0,
      "enabled": true,
      "trigger_words": "foo style, bar"
    }
  ]
}
```

- Entries are applied in array order. Entries with `enabled: false` are skipped and never touch the disk.
- `name`, `strength_model`, `strength_clip`, and `enabled` are required on every entry. `trigger_words` is optional.
- `name` is the forward-slash name relative to the `loras` folder, exactly as ComfyUI lists it (on Windows the pack maps `/` to ComfyUI's `\` names).
- Strengths are applied as written, including both being `0`. The stock `LoraLoader` skips that case. This node does not.
- `trigger_words` output: each enabled entry's `trigger_words` is split on commas, trimmed, empty phrases dropped, and duplicates removed (case-sensitive, first occurrence wins), then joined with `", "`. It is informational only; the node never edits prompts.
- Unknown keys anywhere in the payload are ignored, so SimpleUI can store its own fields.
- Empty or all-disabled list: `model` and `clip` pass through unchanged.

Errors are raised at prompt validation (`VALIDATE_INPUTS`) when `loras` is a literal string in the API JSON, for malformed JSON, a missing or unsupported `schema` (anything above `1` asks you to update the pack), missing fields, non-numeric or non-finite strengths, non-boolean `enabled`, and an enabled `name` that is not installed. When `loras` comes from a link, the same checks run at execution instead. Messages use ComfyUI-relative names only, never host paths.

LoRA application uses ComfyUI's own `comfy.utils.load_torch_file` and `comfy.sd.load_lora_for_models`.

### Chain Output (Image) / Chain Output (Text)

`SimpleUIChainOutput`: `image` IMAGE, `name` STRING (default `""`) → `IMAGE`.
`SimpleUIChainOutputText`: optional `text` STRING (multiline, default `""`, still connectable as a socket), `name` STRING (default `""`) → `STRING`. Type the text directly or wire it from another node; unconnected and empty passes `""`.

Pure passthroughs that mark "this is the stage result for the next stage". They are not output nodes and save nothing; wire the image into a normal `SaveImage` or `PreviewImage`. `name` is the reference other workflows use. An empty name means unnamed.

### Chain Input (Image) / Chain Input (Text)

`SimpleUIChainInputImage`: `image` (the stock Load Image combo, uploads allowed), `name` STRING → `IMAGE`, `MASK`. It subclasses ComfyUI's `LoadImage`, so loading, validation, and change detection are LoadImage's own.
`SimpleUIChainInputText`: `text` STRING (multiline), `name` STRING → `STRING`.

Standalone they use their own widget value. SimpleUI overwrites `image` (with a staged input file name) or `text` at submission when the node is bound in a chain.

### Chain matching (done by SimpleUI, not the pack)

1. An explicit reference chosen in the app wins.
2. Otherwise an input auto-matches an output with the same `name` from the nearest earlier stage.
3. No valid reference, or duplicate output names in one workflow, is an error and the chain pauses before submission.
4. Names are case-sensitive, trimmed, and compared exactly. Empty names never auto-match.

## Detection route

```
GET /simpleui/pack  ->  {"pack": "comfyui-simpleui-nodes", "version": "2.0.0", "contract": 2}
```

SimpleUI falls back to looking for `SimpleUI*` class types in `/object_info` when the route is missing.

## Development

Unit tests use the standard library only and stub `folder_paths`, `comfy`, and `nodes`:

```sh
python -m unittest discover -s tests -t .
```

`tests/live/` holds the scripts used for live verification against a running ComfyUI with the pack installed. They are not part of the unit test run; see the docstrings for the environment variables they take.

## Live verification record

Run on 2026-10-05 against contract 2 (2.0.0) in a Linux container, CPU only (`--cpu`, no GPU available).

- ComfyUI 0.38.0 (commit `5c460d8`), comfyui-frontend-package 1.53.10, torch 2.14.1, Python 3.11.
- Model: HuggingFace was not reachable from the container, so the checkpoint was a random-weight SD1.5 checkpoint with real SD1.5 architecture and key names (ComfyUI detected it as `SD15`), plus two random rank-4 LoRAs in kohya format (`styles/test_a.safetensors`, `test_b.safetensors`) covering UNet attention and text-encoder projections. Images are noise, but every step runs through ComfyUI's normal loader, LoRA patching, sampler, VAE, and save path. ComfyUI logged no "lora key not loaded" warnings.

`tests/live/live_check.py`: 23/23 passed.

- LoRA Stack with two LoRAs, the second disabled, generated a 128×128 image (2 Euler steps). The enabled LoRA changed the image versus an empty stack. The image was bit-identical to a run with the disabled entry removed. Enabling the second LoRA changed the image. `trigger_words` was `alpha style, shared` (disabled entry's words excluded), and with both enabled `alpha style, shared, beta` (deduplicated).
- An enabled entry with both strengths `0` ran and produced the same image as an empty stack.
- With `loras` absent from the API JSON, the node passed `model`/`clip` through (image identical to an empty stack). With the same payload wired from a Chain Input (Text) node instead of injected, the image and `trigger_words` matched the injected run. A wired payload naming a missing LoRA failed at execution with the same message.
- An identical back-to-back prompt was served entirely from ComfyUI's cache (every node reported in `execution_cached`).
- Unknown LoRA name, malformed JSON, `schema: 2`, a string strength, and a string `enabled` were each rejected with HTTP 400 at validation, with the messages above and no host paths. A disabled entry naming a missing file was accepted.
- Chain Output → SaveImage saved a pixel-identical copy of the directly saved image, and Chain Output produced no UI output of its own. Chain Input (Image) loaded that staged file back pixel-identical. Chain Input (Text) → Chain Output (Text) passed multi-line text through verbatim. Chain Input (Image) rejected a missing file at validation.
- `GET /simpleui/pack` returned `{"pack": "comfyui-simpleui-nodes", "version": "2.0.0", "contract": 2}`.
- `/object_info` listed all five `SimpleUI*` nodes in category `SimpleUI`, none as output nodes, with inputs `model, clip` + optional `loras` (`["STRING", {"forceInput": true}]`) / `image, name` / `text, name` / `image, name` / `text, name` and the outputs above.

`tests/live/frontend_check.js` (headless Chromium, frontend 1.53.10): LoRA Stack shows `model`, `clip`, and `loras` sockets and no widgets, both when loaded from API JSON and when created fresh. The exported API JSON for an unconnected LoRA Stack contains only `model` and `clip`. The other nodes' widgets are unchanged.

Not yet verified: generation with a real SD1.5 or SDXL checkpoint and real LoRAs, a GPU run, Windows paths, and a visible-browser check of the canvas.

## Open questions

1. **Does the frontend preserve a large multiline JSON widget value?** No longer applies since contract 2: `loras` has no widget, and SimpleUI injects it into API JSON. (Under contract 1, frontend 1.53.10 kept such a value byte-identical through export, save, and reload.)
2. **LoRA application call and caching.** Settled: `comfy.sd.load_lora_for_models` with files read by `comfy.utils.load_torch_file`. ComfyUI's output cache already skips the node when the stack is unchanged. Within one node instance, loaded LoRA files are kept for the LoRAs used in the latest run, so a strength-only edit does not re-read files; LoRAs dropped from the stack are released on the next run. Unlike stock `LoraLoader` (which keeps one file), this holds every LoRA in the stack in RAM.
3. **Registry `PublisherId` and license.** Unresolved. `[tool.comfy] PublisherId` is empty in `pyproject.toml` and must be set before publishing to the ComfyUI Registry. The repo name is `ComfyUI-SimpleUI-Nodes`. The repository was created with the AGPL-3.0 license, which this pack keeps; the handoff suggested MIT or similar, so confirm before release.
4. **Include `SimpleUIChainOutputText` in v1?** Yes, it is included.

## Changelog

- **2.0.0 (contract 2):** LoRA Stack's `loras` is an optional, socket-only STRING input (`forceInput`), no longer a required multiline widget. Absent or blank `loras` passes through. The payload format is unchanged.
- **1.0.0 (contract 1):** first release.

## License

AGPL-3.0. See [LICENSE](LICENSE).
