# Demo runbook

Everything needed to set up, check and present the project. The deadline set
by the professor is the end-semester exam date + 3 days, for both the demo and
the viva. For explaining and modifying the code, see [VIVA.md](VIVA.md).

## 1. One-time setup

### Pop!_OS / Ubuntu (x86-64), tested on Pop!_OS 24.04

```sh
sudo apt update
sudo apt install build-essential binutils qemu-system-x86 python3 perl git
git clone https://github.com/rajmodi8905/os-project.git
cd os-project
git checkout claude/hopeful-hamilton-x2oed7   # skip once merged into main
./scripts/xv6 doctor
```

`gcc-multilib` is optional on Pop!_OS (the build worked without it).

### macOS (Intel or Apple Silicon)

Follow the macOS section of [SETUP.md](SETUP.md) (Homebrew `qemu` and
`i686-elf-gcc`), then clone and run `./scripts/xv6 doctor` as above. On Apple
Silicon, QEMU emulates the x86 CPU in software, so boot and `check` are slower
but work. The Mac passed the baseline checks on 7 November; run section 2 on it
once before relying on it for the demo, since the feature itself has so far
been run on Linux only.

## 2. Pre-flight check (do this on the demo machine, the day before and again on the day)

```sh
cd os-project
git pull
./scripts/xv6 clean
./scripts/xv6 check
```

Expect exactly these three lines near the end (about 1–3 minutes):

```
PASS: xv6 boot, shell command and upstream forktest
PASS: vmtest page protection (10 expected user write faults, shell still alive)
PASS: upstream usertests
```

The serial log is saved to `artifacts/usertests.log`. Run only one QEMU guest
at a time; close any old `xv6 run` window first.

## 3. The live demo (about 5 minutes)

Start the guest:

```sh
./scripts/xv6 run
```

Wait for the `$ ` prompt. Exit any time with **Ctrl-A, then X**.

### Step A: the demo program

```
$ vmdemo
```

What to point at, section by section:

| Output section | What it shows | One sentence to say |
| --- | --- | --- |
| `[1] ... writable control` | Normal heap pages store and return values | "Baseline: these pages are ordinary writable heap memory." |
| `[2] mprotect(...) = 0` | Syscall succeeded | "This clears `PTE_W` in each page's PTE and reloads CR3." |
| `protected read still works` | `PTE_P` and `PTE_U` still set | "Only the write bit changed; the page is still mapped." |
| `pid N vmdemo: trap 14 err 7 ...` | Kernel's page-fault diagnostic | "Trap 14 is a page fault; error 7 = present + write + user mode." |
| `STOPPED by page fault (child killed)` | The writing child died | "`trap()` kills only the faulting process; the parent learns via a pipe." |
| `parent still alive, value unchanged` | Isolation | "The parent never wrote; its copy is intact." |
| `[3] fork inheritance` | New child also faults | "`copyuvm()` copies PTE flags, so read-only survives fork." |
| `[4] ... = -1` | Bad requests rejected | "Validation runs before any change, so nothing is partially applied." |
| `child (after rejected munprotect) ... STOPPED` | Atomicity | "The rejected munprotect left the protection unchanged." |
| `[5] munprotect ... = 0`, `SUCCEEDED` | Restored write | "Setting `PTE_W` again makes the page writable." |

### Step B: let the examiner choose the numbers

```
$ vmdemo 7 3
$ vmdemo 1000 16
```

Arguments are `[value] [pages]`; pages must be 1–16.

### Step C: the full suite and shell survival

```
$ vmtest
$ echo still alive
```

`vmtest` ends with `vmtest: 10 child write faults observed` and
`vmtest: ALL PASSED`. There are exactly 10 `trap 14 err 7` lines; each matches
one child that was expected to fault.

### Step D (if asked): the kernel-buffer case

Point to the `read() into protected page rejected` lines in the `vmtest`
output. Explain that before checkpoint 4 this exact case caused
`panic: trap` in the kernel, as recorded in [VALIDATION.md](VALIDATION.md).

## 4. Showing the code

Show exactly what you added on top of upstream xv6:

```sh
git fetch --tags
git diff --stat xv6-baseline -- '*.c' '*.h' '*.S'
git diff xv6-baseline -- vm.c sysproc.c syscall.c sysfile.c
```

Suggested order: `user.h`/`usys.S` → `syscall.h`/`syscall.c` →
`sysproc.c: changeprotection` → `vm.c: setuvmwrite` →
`vm.c: checkuvmwrite` + `syscall.c: argptrw` + `sysfile.c` → `vmtest.c`.
Diagrams and explanations: [WALKTHROUGH.md](WALKTHROUGH.md).

## 5. If something goes wrong

| Symptom | Fix |
| --- | --- |
| `Missing tool` / `QEMU missing` from `doctor` | Install the packages in section 1 |
| `gcc: error: unrecognized ... -m32` or missing `crt` files | `sudo apt install gcc-multilib` |
| Guest hangs at boot or `check` times out | Another QEMU is running: close it, then `./scripts/xv6 clean` and retry |
| `vmdemo: not found` in the guest | Old disk image: exit, `./scripts/xv6 clean`, `./scripts/xv6 run` |
| Linker warnings about `.note.GNU-stack` or RWX segments | Harmless; they also appear in upstream xv6 with modern binutils |
| Need to quit QEMU | Ctrl-A, then X |

Have a backup: a laptop recording or terminal screenshot of a passing `check`
and a `vmdemo` run, in case the presentation machine misbehaves.
