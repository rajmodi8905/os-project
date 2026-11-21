#!/usr/bin/env bash
# Render the viva video with the repo2video engine (Remotion + Edge TTS).
# Run this on your own laptop (it needs internet for the voice and for Remotion).
#
#   ./video/render.sh            # one video, about 26 minutes
#   PART=1 ./video/render.sh     # only part 1 (also 2, 3, 4)
#   PART=parts ./video/render.sh # render parts 1-4 separately, then join them
#
# Output: video/out/viva.mp4 (or viva_part1.mp4 ... for single parts)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENGINE="${REPO2VIDEO_ENGINE:-$HOME/.repo2video}"
PART="${PART:-all}"

for tool in node ffmpeg git python3; do
  command -v "$tool" >/dev/null || { echo "Missing $tool. See video/README.md." >&2; exit 1; }
done
node -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 18 ? 0 : 1)' \
  || { echo "Node 18 or newer is required." >&2; exit 1; }

if [[ ! -f "$ENGINE/render-cli.ts" ]]; then
  echo "Installing the rendering engine into $ENGINE (one time)..."
  git clone https://github.com/kuncevichandrew2/repotutor.git "$ENGINE"
fi
(cd "$ENGINE" && npm install --no-audit --no-fund)
(cd "$ENGINE" && npx remotion browser ensure) || echo "Could not pre-download the browser; Remotion will try again."

# Use a clean copy of the committed files so build products never leak into the
# analysis and the line numbers in the script match what is shown on screen.
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
git -C "$ROOT" archive HEAD | tar -x -C "$WORK"
python3 "$WORK/video/build_inputs.py"
(cd "$ENGINE" && npx tsx analyze-cli.ts "$WORK") > "$WORK/analysis.json"

mkdir -p "$ROOT/video/out"

render() {  # render <plan> <scripts> <output name>
  local last
  last="$(cd "$ENGINE" && npx tsx render-cli.ts --analysis "$WORK/analysis.json" \
      --plan "$1" --scripts "$2" --repo "$WORK" | tail -n 1)"
  [[ -f "$last" ]] || { echo "Render failed; scroll up for the error." >&2; exit 1; }
  cp "$last" "$ROOT/video/out/$3"
  echo "Wrote video/out/$3"
}

case "$PART" in
  all)
    render "$WORK/video/plan.json" "$WORK/video/scripts.json" viva.mp4 ;;
  1|2|3|4)
    render "$WORK/video/parts/plan_$PART.json" "$WORK/video/parts/scripts_$PART.json" "viva_part$PART.mp4" ;;
  parts)
    : > "$ROOT/video/out/list.txt"
    for n in 1 2 3 4; do
      render "$WORK/video/parts/plan_$n.json" "$WORK/video/parts/scripts_$n.json" "viva_part$n.mp4"
      echo "file 'viva_part$n.mp4'" >> "$ROOT/video/out/list.txt"
    done
    (cd "$ROOT/video/out" && ffmpeg -y -f concat -safe 0 -i list.txt -c copy viva.mp4)
    echo "Wrote video/out/viva.mp4" ;;
  *) echo "PART must be all, 1, 2, 3, 4 or parts" >&2; exit 2 ;;
esac
