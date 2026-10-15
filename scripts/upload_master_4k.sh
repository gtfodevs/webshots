#!/usr/bin/env bash
# upload_master_4k.sh IN OUT  -- 4K upload master (YouTube gives 4K uploads a higher-bitrate encode).
# Landscape -> 3840x2160, portrait -> 2160x3840. Lanczos + light unsharp, H.264 High CRF16 (cap 60M),
# yuv420p, source fps, keyframes every 2s, +faststart, audio stream-copied (AAC 320k fallback).
# Env: PRESET (default medium), CRF (default 16).
set -euo pipefail
IN="${1:?usage: upload_master_4k.sh IN OUT}"; OUT="${2:?usage: upload_master_4k.sh IN OUT}"
PRESET="${PRESET:-medium}"; CRF="${CRF:-16}"
read -r W H FPS < <(ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate -of csv=p=0 "$IN" | tr ',' ' ')
if [ "$W" -ge "$H" ]; then TW=3840; TH=2160; else TW=2160; TH=3840; fi
GOP=$(python3 -c "from fractions import Fraction as F; print(round(2*F('$FPS')))")
mkdir -p "$(dirname "$OUT")"
VF="scale=${TW}:${TH}:flags=lanczos,unsharp=5:5:0.4:5:5:0.0,format=yuv420p"
venc=(-c:v libx264 -profile:v high -preset "$PRESET" -crf "$CRF" -maxrate 60M -bufsize 120M
      -pix_fmt yuv420p -r "$FPS" -g "$GOP" -keyint_min "$GOP" -sc_threshold 0
      -force_key_frames "expr:gte(t,n_forced*2)" -movflags +faststart)
if ! ffmpeg -hide_banner -y -i "$IN" -map 0:v:0 -map 0:a:0? -vf "$VF" "${venc[@]}" -c:a copy "$OUT"; then
  echo "audio copy failed; retrying with AAC 320k" >&2
  ffmpeg -hide_banner -y -i "$IN" -map 0:v:0 -map 0:a:0? -vf "$VF" "${venc[@]}" -c:a aac -b:a 320k "$OUT"
fi
ffprobe -v error -show_entries stream=codec_type,width,height:format=duration -of compact "$OUT"
