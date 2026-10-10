# webshots

**Describe a video. Get a narrated, animated MP4.**

![Every scene of "Why do farts stink?", a 95-second explainer made with webshots](docs/why-farts-stink-scenes.png)

<sub>Every scene of <b>Why do farts stink?</b>, a narrated 95-second explainer made from one sentence. The source is in <code>shots/why-farts-stink/</code>.</sub>

## How to use it

1. Open this folder in an AI coding assistant that can run commands: **ChatGPT (Codex)**, **Claude Code**, **Cursor**, **Gemini CLI**, or similar.
2. Tell it what you want:

   > Make a 60-second video explaining why the sky is blue.

3. Wait a few minutes. Your video appears in `out/`.

That's it. The assistant writes the script, draws and animates every scene, checks them, records them with an AI voice, and hands you the file. The first time, it also installs what it needs, which takes a few minutes.

Ideas to try:
- "A funny 45-second explainer on why cats knock things off tables"
- "Explain how a refund request flows through our support system, for new hires"
- "Same video, but with a British female voice"

### See it move

![Why do farts stink? (excerpt)](docs/why-farts-stink.gif)

## 🤖 If you're the AI assistant

Read **[`AGENTS.md`](AGENTS.md)** and follow it step by step. It covers setup, writing the narration, building the animation, the visual check, rendering and the hand-off. Keep the user out of the details: do the work, then give them the finished file.

<details>
<summary>How it works (for the curious)</summary>

Each video is a folder in `shots/<name>/` with two hand-made parts:

- **`<name>.scenes.json`:** what the narrator says in each scene.
- **`stage/index.html`:** a 1280×720 web page of SVG drawings, animated with [GSAP](https://gsap.com).

[Argo](https://github.com/shreyaskarnik/argo) then turns those into a video:

1. It generates each line of narration with the [Kokoro](https://github.com/hexgrad/kokoro) voice, locally and for free.
2. Playwright plays each scene in Chromium and holds it until its line ends.
3. ffmpeg mixes the voice in and exports the MP4.

```
narration ──► voice clips ──► clip lengths
                                  │
animation ──► recorded scene by scene, timed to each clip ──► MP4
```

Commands, if you want to drive it by hand:

```bash
npm run setup                          # once
npm run new -- my-video --title "My Video"
npm run check -- my-video              # screenshots of every scene
npm run render -- my-video             # -> out/my-video.mp4
```

**Voices cost nothing by default.** Kokoro is an open-source voice model that runs on your machine, with no account or key. Claude can't speak (its API is text only). If you want a ChatGPT or ElevenLabs voice instead, those are paid APIs that need a key; ask the assistant to switch, and see `AGENTS.md`.

**Requires:** Node 20+ and ffmpeg. The assistant installs them if they're missing and it's allowed to.

</details>

## Credits

[Argo](https://github.com/shreyaskarnik/argo) (MIT) · [GSAP](https://gsap.com) ([standard license](https://gsap.com/standard-license)) · [Kokoro](https://github.com/hexgrad/kokoro) (Apache-2.0) · Playwright · ffmpeg
