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

export default defineConfig({
  baseURL: 'http://webshot.local',
  demosDir: `shots/${shot}`,
  outputDir: 'out/.argo',
  tts: { defaultVoice, defaultSpeed: 1.0, ...(engine ? { engine } : {}) },
  video: {
    width: 1280,
    height: 720,
    fps: 30,
    browser: 'chromium',
    captureMode: 'jpeg-stitch',
    deviceScaleFactor: 2,
  },
  export: { encoder: 'cpu', preset: 'slow', crf: 18, audio: { loudnorm: true } },
});
