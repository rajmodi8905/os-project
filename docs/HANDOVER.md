# Handover: current state for the next person or AI assistant

Read this first, then `AGENTS.md`, `plan.md` and `docs/VALIDATION.md`.
This is the public, shareable project history. Private notes (accounts, other
coursework, email drafts) never belong in this repository.

## Current checkpoint (15 November 2026)

- **Project:** read-only page protection (`mprotect` / `munprotect`) in x86
  xv6, following the OSTEP `vm-xv6-intro` read-only section. Null-page
  protection is out of scope.
- **Status:** the feature, tests, demo program and documentation are complete
  and pass on three Linux platforms (see below). macOS was validated for the
  baseline only; the feature has not yet been run on the Mac.
- **Branch:** `main` is the up-to-date branch; study and demo from it. The
  working branch `claude/hopeful-hamilton-x2oed7` was fast-forwarded into
  `main` on 15 November 2026, so the commit hashes below are the same on both.
- **Viva video:** `video/viva.mp4` (about 11 minutes, narrated, with captions) is
  built and committed. It is made by `video/make_video.py` (HTML slides drawn with
  Playwright, real code and real guest output, offline espeak-ng voice, FFmpeg).
  An earlier attempt with the repo2video skill was dropped: it needs online
  services and silently produced a silent, plain video. See `video/README.md`.
- **Phase now:** the student is preparing for the demo and viva. The deadline
  is the end-semester exam date + 3 days. The professor allows AI help, but the
  student must own the code: explain any block, and modify it without AI.
- **What remains (the student's work):** the `docs/VIVA.md` exercises done
  unaided, the question bank, rehearsal on the presentation machine
  (`docs/DEMO.md`), the demo and the viva.

## Guidance for an AI assistant helping from here

- Do not add or redesign features unless the student explicitly asks. The
  student has to defend every line, so prefer explaining, quizzing and
  reviewing the student's own changes over writing new code.
- When the student practises the exercises in `docs/VIVA.md`, give hints
  before solutions. Practice edits are reverted with `git checkout -- .` and
  are not committed.
- Any behaviour change must update `vmtest.c`, `docs/VALIDATION.md` (with real
  commands and results) and the relevant docs, and `./scripts/xv6 clean &&
  ./scripts/xv6 check` must pass.
- Git commits use the student's identity, with no AI author or co-author
  lines (see `AGENTS.md`). AI assistance is disclosed in `README.md`.

## Map of the work

| Commit | What |
| --- | --- |
| `49798d1` | Baseline setup: `scripts/xv6`, `scripts/smoke.py`, CI, setup docs (upstream base tagged `xv6-baseline`) |
| `c723780` | `plan.md`: checkpoints, test matrix, demo plan |
| `fd757a1` | Checkpoint 3: syscalls 22/23, `setuvmwrite()` in `vm.c`, first `vmtest` |
| `8c21a17` | Checkpoint 4: `checkuvmwrite()`, `argptrw()`; `read`/`fstat`/`pipe` reject read-only destinations; `copyout` honours `PTE_W` |
| `ae30160` | Checkpoint 5: full `vmtest` suite; runner integration and fault correlation |
| `2c04dd5` | Checkpoint 6: `vmdemo`, `docs/WALKTHROUGH.md` |
| `1bfe935` | Pop!_OS and CI results recorded |
| `12fad3d` | `docs/DEMO.md` (runbook), `docs/VIVA.md` (study guide, exercises) |

Key files: `vm.c` (`setuvmwrite`, `checkuvmwrite`, `copyout`), `sysproc.c`
(`changeprotection`, `sys_mprotect`, `sys_munprotect`), `syscall.c`
(`argptrw`, dispatch table), `sysfile.c` (`sys_read`, `sys_fstat`, `sys_pipe`),
`vmtest.c`, `vmdemo.c`, `scripts/smoke.py` (`run_vmtest`).

## Key decisions and why

1. **One helper for both calls**, with a validation pass and then an update
   pass, so a bad page later in a range never leaves a partial change.
2. **Overflow-safe bounds**: compare `npages` with `(sz - va) / PGSIZE`
   instead of computing the end address first.
3. **`walkpgdir(..., 0)`**: never allocate page tables while validating. The
   stack guard page (with `PTE_U` cleared) is rejected.
4. **`lcr3()` after changes** to flush the TLB. A dedicated test proves it
   matters, because forked children reload CR3 and would hide its absence.
5. **Kernel-buffer checks (checkpoint 4)**: xv6 sets `CR0.WP`, so `read()`
   into a protected page panicked the kernel. That was reproduced, then fixed by
   validating writable destinations. `write()` still accepts protected sources.
6. **`copyuvm()` unchanged**: it already copies PTE flags, and tests confirm
   fork inherits protection with independent copies.
7. **Tests use a pipe marker** because xv6's `wait()` has no exit status. The
   runner requires the number of faulting children to equal the number of
   kernel `trap 14 err 7` lines.

## Validation record (details in `docs/VALIDATION.md`)

| Where | Toolchain | Result |
| --- | --- | --- |
| Linux cloud container (Ubuntu 24.04) | GCC 13.3, QEMU from Ubuntu | `clean` + `check`: all 3 PASS; two mutation tests caught |
| GitHub Actions (Ubuntu 22.04), run 4 | apt toolchain | success |
| Pop!_OS 24.04 laptop, Intel Core Ultra 7 165H | GCC 13.3.0, ld 2.42, QEMU 8.2.2 | `clean` + `check`: all 3 PASS |
| macOS / Apple Silicon | i686-elf-gcc 16.2, QEMU 11.1.3 | baseline only (7 Nov); feature not yet run |

## Pitfalls

- Run only one QEMU guest at a time; both use the same `fs.img` / `xv6.img`.
- `usertests` leaves a file behind: run `./scripts/xv6 clean` before every
  `check`. Cleaning erases files created inside the guest.
- Exit QEMU with Ctrl-A, then X.
- Linker warnings about `.note.GNU-stack` and RWX segments are harmless.
- Never run QEMU as root, and never touch host disks or boot configuration.

## Session history

- **7 Nov 2026:** baseline setup and plan (on the Mac). In a cloud session the
  same day: checkpoints 3–6 implemented and validated, with commits pushed.
- **7 Nov 2026:** CI run 4 succeeded.
- **11 Nov 2026:** fresh-clone validation on the Pop!_OS laptop (run by an
  assistant session on the laptop).
- **15 Nov 2026:** professor's requirements recorded; `DEMO.md`, `VIVA.md`
  and this handover added; all work fast-forwarded into `main`.
- **21 Nov 2026:** viva video built (`video/make_video.py`, `video/viva.mp4`,
  11:17). Checked in the container: audio track present at about -17 dB, audio and
  video lengths equal, frames inspected. The first repo2video attempt was removed.
