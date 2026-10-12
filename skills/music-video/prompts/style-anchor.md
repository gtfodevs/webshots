# Style anchor (generate first, get approval)
References: the channel `style.json` (rules, leads, palette) + its approved anchor (`references`), and the song cover for the setting.

Build the prompt from the channel brand, then the song's setting. ProgressiveSlop example:

> Character style sheet, glossy hyper-detailed chrome 3D illustration, neon purple, magenta and cyan lighting, reflective floor. Everything is a robot, no living creatures. <lead description from style.json, e.g. Uno: big heroic chrome robot, smooth round bald chrome head, glowing red eyes, headphones for ears, purple fur cloak, gold chain with a "1" pendant> <setting from the song, e.g. a chrome fantasy kingdom>. Six poses in a 3x2 grid: <poses>. Plain solid light gray background, no text.

Record the approved wording in the manifest as `style_anchor.description`. Older channels without brand rules: derive the look from the cover art.
