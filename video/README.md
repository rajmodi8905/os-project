# Viva video

Two videos, both with narration and on-screen captions. After `git pull` they are in this folder; just play them.

| File | Length | Use it for |
| --- | --- | --- |
| **`viva_full.mp4`** | 23:35 | The complete walkthrough: every file we wrote, the whole test suite, the demo program, the runner and CI, a step-by-step **how to prove it live** chapter, four modification examples with real results, and 12 viva questions |
| `viva.mp4` | 12:23 | A quick revision version: the main code, the demo, three modification examples and 6 questions |

## `viva_full.mp4` chapters

| Time | Chapter |
| --- | --- |
| 0:00 | Problem statement |
| 1:11 | Background: paging, PTE bits, TLB, `CR0.WP`, the fault path |
| 3:01 | Solution: wiring (`user.h`, `defs.h`, `Makefile`), `setuvmwrite`, overflow, two passes, fork, kernel buffers, one call end to end |
| 9:07 | Tests and demo: every `vmtest` group, `vmdemo`, the runner (`smoke.py`, `scripts/xv6`, CI) and the evidence |
| 14:25 | **Live proof**: checklist, `git log`, `git diff --stat`, `check`, boot, `ls`, the demo with the examiner's numbers, breaking it live, a live change, troubleshooting, your opening 30 seconds |
| 18:02 | Modify it: `getprot`, bytes instead of pages, a clearer fault message, refuse page 0 + cap the length (all tested in the guest) |
| 20:23 | Viva Q&A: 12 questions, each with a pause to answer aloud |

`viva.mp4` has the same chapters minus "Live proof": Problem 0:00, Background 0:59, Solution 2:49, Tests & demo 6:56, Modify it 8:44, Viva Q&A 10:34.

Every code view is read from the real source files, and the terminal scenes use
real output captured from the xv6 guest (`assets/`). Green bars mark lines we
added; grey bars mark existing xv6 code. The voice is a local offline voice (RHVoice "slt"), so
it is still synthetic; captions are shown on screen. `narration.md` and
`narration_full.md` have the scripts if you want to re-record in your own voice.

## Rebuild it (optional)

Only needed if you change the script or the code. Needs Python 3, `pygments`,
FFmpeg, `rhvoice` + `rhvoice-english` (the voice), `espeak-ng` (fallback), and Node with
Playwright. No internet is needed while building.

```bash
pip install pygments
sudo apt install ffmpeg rhvoice rhvoice-english espeak-ng   # Pop!_OS / Ubuntu
python3 video/make_video.py --long     # writes video/out/viva_full.mp4 (about 22 min)
python3 video/make_video.py            # writes video/out/viva.mp4 (about 11 min)
python3 video/make_video.py --long --frames   # quick check: frames only, no audio
```

The script text, slides and line ranges are all in `make_video.py`. It stops
with an error if a line range no longer matches the source file, so after
editing `vm.c` and friends, update the numbers there. 
### Choosing the voice

```bash
python3 video/make_video.py --voices      # writes video/out/voice_samples.mp3 (5 voices, same sentence)
VOICE=rh:clb python3 video/make_video.py --long   # rebuild with another voice: rh:slt (default), rh:clb, rh:bdl, rh:alan
```

### If the audio seems to break up

`viva_full_audio.mp3` is the same narration as audio only. If it plays smoothly but the
video does not, the problem is your video player: try VLC, or copy the file to your
computer instead of playing it inside a chat or browser preview. The video is
25 fps H.264 (High profile) with a keyframe every 4 seconds, which plays everywhere.
The voice speed is `RATE` (default 85, where 100 is RHVoice's fast default); a
different pace is `RATE=75 python3 video/make_video.py --long`.

### How the audio is made smooth

Each sentence is synthesised separately so it stays in step with its slide. Each
clip then gets stray silence trimmed, fade-in/out on the edges (no clicks), is
levelled to the same loudness, and is followed by a short fixed pause (0.28 s). The whole track
then gets light EQ and compression, loudness normalisation to -16 LUFS with a
-1.5 dB peak limit, and a very quiet room-tone bed so pauses are not dead silence.
Encoded as 48 kHz mono AAC at 96 kbps. If your player is quiet, raise its volume;
the level is a standard -16 LUFS.

| Folder | Content |
| --- | --- |
| `assets/guest_output.txt` | Real `vmdemo 7 3` + `vmtest` output from the xv6 guest |
| `assets/check_output.txt`, `git_log.txt`, `git_diff_stat.txt`, `live_session.txt` | Real `check` lines, git history and diff, and a real boot + `ls` + `vmdemo 1000 4` session |
| `assets/modify_output.txt`, `limits_output.txt` | Real guest output after applying the four example modifications to a scratch copy |
| `examples/` | The four worked answers shown in "Modify it" (illustration only, not built into xv6) |
