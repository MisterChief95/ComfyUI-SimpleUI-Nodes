# ComfyUI-SimpleUI-Nodes

Optional ComfyUI custom nodes that complement [ComfyUI SimpleUI](https://github.com/MisterChief95/ComfyUI-SimpleUI). Add them to a workflow in the ComfyUI canvas, export the workflow as API JSON, and SimpleUI renders richer controls for them. Every node also works in plain ComfyUI without SimpleUI.

- Pack: `comfyui-simpleui-nodes`, version `1.0.0` (`PACK_VERSION`)
- Contract: `1` (the node names, input names, and payload shape below)
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
| `model` MODEL, `clip` CLIP, `loras` STRING (multiline, default `{"schema":1,"loras":[]}`) | `MODEL`, `CLIP`, `trigger_words` STRING |

`loras` is UTF-8 JSON:

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

Errors are raised at prompt validation (`VALIDATE_INPUTS`) for malformed JSON, a missing or unsupported `schema` (anything above `1` asks you to update the pack), missing fields, non-numeric or non-finite strengths, non-boolean `enabled`, and an enabled `name` that is not installed. The same checks run again at execution in case `loras` comes from a link. Messages use ComfyUI-relative names only, never host paths.

LoRA application uses ComfyUI's own `comfy.utils.load_torch_file` and `comfy.sd.load_lora_for_models`.

### Chain Output (Image) / Chain Output (Text)

`SimpleUIChainOutput`: `image` IMAGE, `name` STRING (default `""`) → `IMAGE`.
`SimpleUIChainOutputText`: `text` STRING (socket), `name` STRING (default `""`) → `STRING`.

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
GET /simpleui/pack  ->  {"pack": "comfyui-simpleui-nodes", "version": "1.0.0", "contract": 1}
```

SimpleUI falls back to looking for `SimpleUI*` class types in `/object_info` when the route is missing.

## Development

Unit tests use the standard library only and stub `folder_paths`, `comfy`, and `nodes`:

```sh
python -m unittest discover -s tests -t .
```

`tests/live/` holds the scripts used for live verification against a running ComfyUI with the pack installed. They are not part of the unit test run; see the docstrings for the environment variables they take.

## Live verification record

Run on 2026-10-05 in a Linux container, CPU only (`--cpu`, no GPU available).

- ComfyUI 0.38.0 (commit `5c460d8`), comfyui-frontend-package 1.53.10, torch 2.14.1, Python 3.11.
- Model: HuggingFace was not reachable from the container, so the checkpoint was a random-weight SD1.5 checkpoint with real SD1.5 architecture and key names (ComfyUI detected it as `SD15`), plus two random rank-4 LoRAs in kohya format (`styles/test_a.safetensors`, `test_b.safetensors`) covering UNet attention and text-encoder projections. Images are noise, but every step runs through ComfyUI's normal loader, LoRA patching, sampler, VAE, and save path. ComfyUI logged no "lora key not loaded" warnings.

`tests/live/live_check.py`: 20/20 passed.

- LoRA Stack with two LoRAs, the second disabled, generated a 128×128 image (2 Euler steps). The enabled LoRA changed the image versus an empty stack. The image was bit-identical to a run with the disabled entry removed. Enabling the second LoRA changed the image. `trigger_words` was `alpha style, shared` (disabled entry's words excluded), and with both enabled `alpha style, shared, beta` (deduplicated).
- An enabled entry with both strengths `0` ran and produced the same image as an empty stack.
- An identical back-to-back prompt was served entirely from ComfyUI's cache (every node reported in `execution_cached`).
- Unknown LoRA name, malformed JSON, `schema: 2`, a string strength, and a string `enabled` were each rejected with HTTP 400 at validation, with the messages above and no host paths. A disabled entry naming a missing file was accepted.
- Chain Output → SaveImage saved a pixel-identical copy of the directly saved image, and Chain Output produced no UI output of its own. Chain Input (Image) loaded that staged file back pixel-identical. Chain Input (Text) → Chain Output (Text) passed multi-line text through verbatim. Chain Input (Image) rejected a missing file at validation.
- `GET /simpleui/pack` returned `{"pack": "comfyui-simpleui-nodes", "version": "1.0.0", "contract": 1}`.
- `/object_info` listed all five `SimpleUI*` nodes in category `SimpleUI`, none as output nodes, with inputs `model, clip, loras` / `image, name` / `text, name` / `image, name` / `text, name` and the outputs above.

`tests/live/frontend_check.js` (headless Chromium, frontend 1.53.10): see open question 1 below.

Not yet verified: generation with a real SD1.5 or SDXL checkpoint and real LoRAs, a GPU run, Windows paths, and hand-editing the `loras` text box in a visible browser.

## Open questions

1. **Does the frontend preserve a large multiline JSON widget value?** Yes for frontend 1.53.10: a pretty-printed payload with Unicode, typographic quotes, nested unknown keys, `1e-7`, and trailing blank lines stayed byte-identical in the widget, in the exported API JSON (`graphToPrompt`), in the saved workflow JSON, and in the API JSON exported again after reloading that workflow. The `loras` widget renders as a multiline text box. Other frontend versions are not checked.
2. **LoRA application call and caching.** Settled: `comfy.sd.load_lora_for_models` with files read by `comfy.utils.load_torch_file`. ComfyUI's output cache already skips the node when the stack is unchanged. Within one node instance, loaded LoRA files are kept for the LoRAs used in the latest run, so a strength-only edit does not re-read files; LoRAs dropped from the stack are released on the next run. Unlike stock `LoraLoader` (which keeps one file), this holds every LoRA in the stack in RAM.
3. **Registry `PublisherId` and license.** Unresolved. `[tool.comfy] PublisherId` is empty in `pyproject.toml` and must be set before publishing to the ComfyUI Registry. The repo name is `ComfyUI-SimpleUI-Nodes`. The repository was created with the AGPL-3.0 license, which this pack keeps; the handoff suggested MIT or similar, so confirm before release.
4. **Include `SimpleUIChainOutputText` in v1?** Yes, it is included.

## License

AGPL-3.0. See [LICENSE](LICENSE).
