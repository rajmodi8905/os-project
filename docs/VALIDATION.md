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
