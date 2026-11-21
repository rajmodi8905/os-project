# Viva video

**`video/viva.mp4`** is the finished video (about 11 minutes, with narration and
captions). Play it directly; no setup needed. After `git pull` it is in this folder.

| Time | Chapter |
| --- | --- |
| 0:00 | Problem statement |
| 0:54 | Background: paging, PTE bits, TLB, `CR0.WP`, the fault path |
| 2:34 | Solution: syscall wiring, `setuvmwrite`, overflow, two passes, fork, kernel buffers |
| 6:16 | Tests and the live demo (real output from the xv6 guest), evidence |
| 7:56 | Modify it: three worked "change this snippet" examples, ideas, experiments |
| 9:35 | Viva Q&A: six rapid-fire questions, with a pause to answer aloud |

Every code view is read from the real source files, and the terminal scenes use
real output captured from the guest (`assets/`). Green bars mark lines we added;
grey bars mark existing xv6 code. The voice is a local offline voice, so it
sounds robotic; captions are shown on screen. `narration.md` has the full script
if you want to re-record it in your own voice.

## Rebuild it (optional)

Only needed if you change the script or the code. Needs Python 3, `pygments`,
FFmpeg, `espeak-ng` (+ `mbrola` voices for a smoother voice), and Node with
Playwright. No internet is needed while building.

```bash
pip install pygments
sudo apt install ffmpeg espeak-ng mbrola mbrola-us2   # Pop!_OS / Ubuntu
python3 video/make_video.py            # writes video/out/viva.mp4
python3 video/make_video.py --frames   # quick check: frames only, no audio
```

The script text, slides and line ranges are all in `make_video.py`. It stops
with an error if a line range no longer matches the source file, so after
editing `vm.c` and friends, update the numbers there. Set `VOICE=en-us` if the
mbrola voice is missing, or `SPEED=140` to talk slower.

| Folder | Content |
| --- | --- |
| `assets/guest_output.txt` | Real `vmdemo 7 3` + `vmtest` output from the xv6 guest |
| `assets/check_output.txt` | Real `./scripts/xv6 check` result lines |
| `examples/` | The three worked answers shown in "Modify it" (illustration only, not built into xv6) |
