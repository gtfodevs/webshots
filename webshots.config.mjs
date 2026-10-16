import { defineConfig, engines } from '@argo-video/cli';

// Rendering settings for every shot. `npm run render -- <name>` sets WEBSHOT.
const shot = process.env.WEBSHOT;
if (!shot) throw new Error('WEBSHOT is not set. Render with: npm run render -- <name>');

// Voice engine: local Kokoro by default (free, no key). Set WEBSHOTS_TTS=openai
// (needs OPENAI_API_KEY) or WEBSHOTS_TTS=elevenlabs (needs ELEVENLABS_API_KEY)
// for a cloud voice, and WEBSHOTS_VOICE to pick the voice.
const tts = process.env.WEBSHOTS_TTS;
const engine =
  tts === 'openai' ? engines.openai({ model: process.env.WEBSHOTS_OPENAI_MODEL || 'gpt-4o-mini-tts' }) :
  tts === 'elevenlabs' ? engines.elevenlabs() :
  undefined;
const defaultVoice = process.env.WEBSHOTS_VOICE || (tts === 'openai' ? 'alloy' : 'am_michael');

// Output format: landscape 1280x720 (default) or vertical 720x1280 (x1.5 = 1080x1920 for Shorts).
// `npm run render -- <name> --format vertical` sets WEBSHOTS_FORMAT.
const vertical = process.env.WEBSHOTS_FORMAT === 'vertical';

export default defineConfig({
  baseURL: 'http://webshot.local',
  demosDir: `shots/${shot}`,
  outputDir: 'out/.argo',
  tts: { defaultVoice, defaultSpeed: 1.0, ...(engine ? { engine } : {}) },
  video: {
    width: vertical ? 720 : 1280,
    height: vertical ? 1280 : 720,
    fps: 30,
    browser: 'chromium',
    captureMode: 'jpeg-stitch',
    deviceScaleFactor: vertical ? 1.5 : 2,
  },
  export: { encoder: 'cpu', preset: 'slow', crf: 18, audio: { loudnorm: true } },
});
