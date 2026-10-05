// Round-trip check of the LoRA Stack widget value in the real ComfyUI frontend.
// Usage: COMFY_URL=http://127.0.0.1:8188 CKPT=model.safetensors node tests/live/frontend_check.js
// Needs Playwright (npm i playwright) and a Chromium it can launch.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const URL = process.env.COMFY_URL || 'http://127.0.0.1:8188';
const CKPT = process.env.CKPT || 'random_sd15.safetensors';

const PAYLOAD = JSON.stringify({
  schema: 1,
  loras: [
    { name: 'styles/test_a.safetensors', strength_model: 1.0, strength_clip: 0.75, enabled: true,
      trigger_words: 'alpha style, ünïcode “quotes”', app_only: { thumb: 'x.png', n: 1e-7 } },
    { name: 'test_b.safetensors', strength_model: 0, strength_clip: 0, enabled: false, trigger_words: '' },
  ],
  app_state: null,
}, null, 2) + '\n\n';   // trailing whitespace and indentation must survive too

(async () => {
  const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
  const page = await browser.newPage();
  page.on('pageerror', e => console.log('pageerror', e.message));
  await page.goto(URL);
  await page.waitForFunction(() => window.app && window.app.graph, null, { timeout: 120000 });
  await page.waitForTimeout(3000);

  const api = {
    '1': { class_type: 'CheckpointLoaderSimple', inputs: { ckpt_name: CKPT } },
    '2': { class_type: 'SimpleUILoraStack', inputs: { model: ['1', 0], clip: ['1', 1], loras: PAYLOAD } },
    '3': { class_type: 'PreviewAny', inputs: { source: ['2', 2] } },
    '4': { class_type: 'SimpleUIChainInputText', inputs: { text: 'line one\nline two', name: 'p' } },
    '5': { class_type: 'SimpleUIChainOutputText', inputs: { text: ['4', 0], name: 'p_out' } },
    '6': { class_type: 'PreviewAny', inputs: { source: ['5', 0] } },
    '7': { class_type: 'SimpleUIChainInputImage', inputs: { image: 'example.png', name: 'stage1' } },
    '8': { class_type: 'SimpleUIChainOutput', inputs: { image: ['7', 0], name: 'stage2' } },
    '9': { class_type: 'PreviewImage', inputs: { images: ['8', 0] } },
  };

  const result = await page.evaluate(async ({ api, PAYLOAD }) => {
    const app = window.app;
    await app.loadApiJson(api, 'simpleui-check.json');
    await new Promise(r => setTimeout(r, 1000));
    const lora = app.graph._nodes.find(n => n.type === 'SimpleUILoraStack');
    const widgetTypes = Object.fromEntries(app.graph._nodes.filter(n => n.type.startsWith('SimpleUI'))
      .map(n => [n.type, (n.widgets || []).map(w => `${w.name}:${w.type}`)]));
    const first = (await app.graphToPrompt()).output;

    // Save the workflow as the UI would, then load it back.
    const saved = JSON.stringify(app.graph.serialize());
    await app.loadGraphData(JSON.parse(saved));
    await new Promise(r => setTimeout(r, 1000));
    const second = (await app.graphToPrompt()).output;

    const byType = (out, t) => Object.values(out).find(n => n.class_type === t);
    return {
      widgetTypes,
      widgetValueVerbatim: lora.widgets.find(w => w.name === 'loras').value === PAYLOAD,
      exportVerbatim: byType(first, 'SimpleUILoraStack').inputs.loras === PAYLOAD,
      workflowJsonContainsVerbatim: saved.includes(JSON.stringify(PAYLOAD)),
      reloadExportVerbatim: byType(second, 'SimpleUILoraStack').inputs.loras === PAYLOAD,
      version: window.__COMFYUI_FRONTEND_VERSION__,
    };
  }, { api, PAYLOAD });

  console.log(JSON.stringify(result, null, 2));
  await browser.close();
})();
