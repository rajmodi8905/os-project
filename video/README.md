# Viva video

Two videos, both with narration and on-screen captions. After `git pull` they are in this folder; just play them.

| File | Length | Use it for |
| --- | --- | --- |
| **`viva_full.mp4`** | 21:38 | The complete walkthrough: every file we wrote, the whole test suite, the demo program, the runner and CI, a step-by-step **how to prove it live** chapter, four modification examples with real results, and 12 viva questions |
| `viva.mp4` | 11:17 | A quick revision version: the main code, the demo, three modification examples and 6 questions |

## `viva_full.mp4` chapters

| Time | Chapter |
| --- | --- |
| 0:00 | Problem statement |
| 1:05 | Background: paging, PTE bits, TLB, `CR0.WP`, the fault path |
| 2:45 | Solution: wiring (`user.h`, `defs.h`, `Makefile`), `setuvmwrite`, overflow, two passes, fork, kernel buffers, one call end to end |
| 7:33 | Tests and demo: every `vmtest` group, `vmdemo`, the runner (`smoke.py`, `scripts/xv6`, CI) and the evidence |
| 13:09 | **Live proof**: checklist, `git log`, `git diff --stat`, `check`, boot, `ls`, the demo with the examiner's numbers, breaking it live, a live change, troubleshooting, your opening 30 seconds |
| 16:29 | Modify it: `getprot`, bytes instead of pages, a clearer fault message, refuse page 0 + cap the length (all tested in the guest) |
| 18:36 | Viva Q&A: 12 questions, each with a pause to answer aloud |

`viva.mp4` has the same chapters minus "Live proof": Problem 0:00, Background 0:54, Solution 2:34, Tests & demo 6:16, Modify it 7:56, Viva Q&A 9:35.

Every code view is read from the real source files, and the terminal scenes use
real output captured from the xv6 guest (`assets/`). Green bars mark lines we
added; grey bars mark existing xv6 code. The voice is a local offline voice, so
it sounds robotic; captions are shown on screen. `narration.md` and
`narration_full.md` have the scripts if you want to re-record in your own voice.

## Rebuild it (optional)

Only needed if you change the script or the code. Needs Python 3, `pygments`,
FFmpeg, `espeak-ng` (+ `mbrola` voices for a smoother voice), and Node with
Playwright. No internet is needed while building.

```bash
pip install pygments
sudo apt install ffmpeg espeak-ng mbrola mbrola-us2   # Pop!_OS / Ubuntu
python3 video/make_video.py --long     # writes video/out/viva_full.mp4 (about 22 min)
python3 video/make_video.py            # writes video/out/viva.mp4 (about 11 min)
python3 video/make_video.py --long --frames   # quick check: frames only, no audio
```

The script text, slides and line ranges are all in `make_video.py`. It stops
with an error if a line range no longer matches the source file, so after
editing `vm.c` and friends, update the numbers there. Set `VOICE=en-us` if the
mbrola voice is missing, or `SPEED=140` to talk slower.

| Folder | Content |
| --- | --- |
| `assets/guest_output.txt` | Real `vmdemo 7 3` + `vmtest` output from the xv6 guest |
| `assets/check_output.txt`, `git_log.txt`, `git_diff_stat.txt`, `live_session.txt` | Real `check` lines, git history and diff, and a real boot + `ls` + `vmdemo 1000 4` session |
| `assets/modify_output.txt`, `limits_output.txt` | Real guest output after applying the four example modifications to a scratch copy |
| `examples/` | The four worked answers shown in "Modify it" (illustration only, not built into xv6) |
