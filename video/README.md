# Viva video: inputs and how to render

A narrated video (about 26 minutes, under the 30 minute cap) that explains the
whole project for the viva: the problem, the solution, a block-by-block code
walkthrough with the **real code on screen**, the tests and demo, three worked
"change this snippet" examples, and the viva questions with answers.

It is produced by [repo2video](https://github.com/kuncevichandrew2/repo2video)
(a Claude Code skill; its renderer lives in
[repotutor](https://github.com/kuncevichandrew2/repotutor)). The script and
slides were written ahead of time and are committed here, so no AI session is
needed to render it.

**Status:** the inputs (this folder) are validated against the real source
files. The final render has **not** been run yet: the cloud container used to
write this blocks the network access that Remotion and the Edge TTS voice need.
Render it on your laptop with the steps below. If it fails, paste the error to
an assistant (point it at `docs/HANDOVER.md`).

## Render it (Mac or Pop!_OS)

Prerequisites: Node 18+, FFmpeg with libmp3lame, Git, Python 3, internet access.

```bash
# Pop!_OS / Ubuntu
sudo apt install nodejs npm ffmpeg git python3
# macOS
brew install node ffmpeg git
```

Then, from the project root on `main`:

```bash
./video/render.sh
```

The first run downloads the engine to `~/.repo2video` and a headless Chromium
(about 90 MB). The finished file is `video/out/viva.mp4` (ignored by Git).

If one big render runs out of memory or time, render the four parts and join
them automatically, or render one part at a time:

```bash
PART=parts ./video/render.sh
PART=2 ./video/render.sh      # only part 2 -> video/out/viva_part2.mp4
```

## What is in this folder

| File | Purpose |
| --- | --- |
| `build_inputs.py` | Source of truth for the script and slides. Writes the JSON files below and **fails if a line range no longer matches the source files** |
| `plan.json`, `scripts.json` | Engine inputs for the full video (generated) |
| `parts/` | The same, split into the four parts (generated) |
| `narration.md` | The full spoken script in readable form; re-record it in your own voice if you prefer |
| `examples/` | Worked answers shown in part 4 (illustration only, not built into xv6) |
| `render.sh` | One-command render helper |

## Chapters

| Part | Content | About |
| --- | --- | --- |
| 1 | Problem statement, paging, PTE bits, TLB and `CR0.WP`, the fault path | 5 min |
| 2 | Solution overview, syscall wiring, `setuvmwrite`, overflow, fork, kernel buffers, `checkuvmwrite`, `argptrw`, `copyout` | 10 min |
| 3 | Test design, the TLB test, invalid and atomic tests, runner, demo, evidence | 5 min |
| 4 | Three modification examples, more ideas, break-it experiments, three rounds of viva questions, summary | 7 min |

## Editing the video

1. Edit the text in `build_inputs.py` (narration, slide bullets, code ranges).
2. Run `python3 video/build_inputs.py`. It prints the length of each part and
   stops with an error if any line range is wrong.
3. Commit, then run `./video/render.sh`. The renderer works from the committed
   files (`git archive HEAD`), so commit your edits first.

If you change a source file such as `vm.c`, line numbers move. Update the ranges
in `build_inputs.py`; the check will tell you if you forget.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `Chromium not found` | `cd ~/.repo2video && npx remotion browser ensure` |
| Silent video | The Edge TTS voice could not connect; check the network and rerun |
| `Cannot find module` | `cd ~/.repo2video && npm install` |
| Slides show only plain titles | Remotion failed and the engine used its simple FFmpeg fallback; read the warning near the top of the output |
| Narration over 30 minutes | Slow voice: set `EDGE_TTS_VOICE` to a faster one or shorten narration in `build_inputs.py` |
