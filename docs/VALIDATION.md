# Baseline validation

## 7 November 2026 — initial setup

Validated on macOS / Apple Silicon with i686-elf GCC 16.2.0,
binutils 2.47.20260726 and QEMU 11.1.3. The guest uses one emulated x86 CPU.
This is validation of the existing xv6 baseline and setup, not of the proposed
page-protection feature.

| Command | Actual result |
| --- | --- |
| `./scripts/xv6 doctor` | Tool discovery and 32-bit compilation probe passed |
| `./scripts/xv6 clean` then `./scripts/xv6 check` | Clean build, boot, shell, upstream forktest and usertests passed |
| `./scripts/xv6 smoke` | Boot, shell echo and upstream forktest passed |
| `bash -n scripts/xv6` | Shell syntax check passed |
| `python3 -m py_compile scripts/smoke.py` | Python syntax check passed |
| `git diff --check` | No whitespace errors |

The full guest serial log reached `ALL TESTS PASSED` and returned to the shell.
Expected user-fault diagnostics occur during upstream tests, including `uio`;
these are not guest kernel panics. Generated logs remain local in
`artifacts/usertests.log`, `artifacts/smoke.log` and
`artifacts/baseline-check.log`. GitHub Actions separately runs the full baseline
check and uploads its own serial log.

The first raw build exposed GCC 16 warnings in the upstream BIOS mapping,
recursive shell and an unused test counter. Target-specific build settings
address those warnings; `-Werror` remains enabled elsewhere. No kernel C or
assembly behavior was changed. A macOS Bash 3.2 empty-array issue in the setup
wrapper was corrected before publication and the smoke command was rerun.

The spare Pop!_OS machine has not been tested. Remote CI results are reported
by the actual workflow run, not inferred from the successful local build.

## 7 November 2026 — checkpoint 3: syscalls and minimal test

Validated in a Linux x86-64 cloud container (Ubuntu 24.04, host GCC 13.3.0
with `-m32`, QEMU from Ubuntu `qemu-system-x86`), one emulated CPU.

| Command | Actual result |
| --- | --- |
| `./scripts/xv6 smoke` (before changes) | Baseline boot, shell and forktest passed in this environment |
| `make TOOLPREFIX= xv6.img fs.img` | Kernel and `_vmtest` built with `-Werror` |
| `vmtest` typed at the guest shell | All 9 basic checks printed `ok`, then `vmtest: ALL PASSED` |

The protected-write child produced the kernel diagnostic
`pid 4 vmtest: trap 14 err 7 on cpu 0 eip 0x1fb addr 0x3000--kill proc`
(trap 14 = page fault; error code 7 = page present, write access, user mode),
and the parent continued. The parent's value was unchanged and a write after
`munprotect` succeeded.
