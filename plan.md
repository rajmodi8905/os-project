# Implementation plan: Read-Only Page Protection in xv6

## Goal and current status

Implement the read-only protection part of the
[OSTEP virtual-memory project](https://github.com/remzi-arpacidusseau/ostep-projects/tree/master/vm-xv6-intro#read-only-code)
in x86 xv6. A user program should be able to remove write permission from its
pages, keep reading them, and restore write permission later.

The baseline setup is complete at commit `49798d1`: build/run helpers, local
boot and regression checks, and a successful Linux CI run are available.
See [baseline evidence](docs/VALIDATION.md). Checkpoint 3 (both syscalls and a
minimal `vmtest`), checkpoint 4 (kernel output buffers), checkpoint 5 (the
correctness suite) and the checkpoint 6 demo materials are implemented; see the
dated entries in
[validation](docs/VALIDATION.md) for what has actually been run. Professor suitability confirmation
and the exact submission deadline remain unverified.

This plan describes future work; publishing it does not mark those steps done.

## Scope and API

```c
int mprotect(void *addr, int len);
int munprotect(void *addr, int len);
```

- `addr` must be aligned to a page boundary; `len` is a positive number of
  pages, not bytes. An x86 xv6 page is 4096 bytes.
- `mprotect` clears write permission on existing user pages; `munprotect`
  restores it. Both return `0` on success and `-1` on an invalid request.
- Check the entire requested range before changing any page permissions.
  A failed call must leave the previous permissions unchanged.
- Preserve the physical mapping and all unrelated page-table bits.
- Refresh the current process's cached translations after a successful change.
- Permissions must survive `fork()`; parent and child permission changes must
  remain independent after the fork.

The initial target is one emulated x86 CPU in QEMU. Keep the existing program
load addresses and null-page behavior. Null-pointer detection, swapping,
demand paging, copy-on-write and threads are outside this project.

## Checkpoint 1: establish the baseline — complete

- [x] Preserve upstream xv6 history, license and original README.
- [x] Pin base `eeb7b415dbcb12cc362d0783e41c3d1f44066b17` as `xv6-baseline`.
- [x] Provide setup instructions for macOS and x86-64 Pop!_OS/Ubuntu.
- [x] Build and boot locally; run shell, `forktest` and upstream `usertests`.
- [x] Publish the repository and verify the Linux baseline CI run.

The Pop!_OS laptop passed a fresh-clone `clean` + `check` on 11 November 2026
(see [validation](docs/VALIDATION.md)). See [setup commands](docs/SETUP.md). Run QEMU as an ordinary user with project disk
images; leave host disks, kernel and boot configuration alone.

## Checkpoint 2: understand the code before changing it

- [ ] Review C pointers, hexadecimal addresses, structs and bit operations.
- [ ] Review OSTEP chapters 18–19: pages, page tables, permissions and TLBs.
- [ ] Trace `getpid()` from `user.h` / `usys.S` through `syscall.h`, `syscall.c`
  and `sysproc.c`.
- [ ] Read `mmu.h`: `PGSIZE`, page alignment, `PTE_P`, `PTE_U`, `PTE_W`.
- [ ] Trace `walkpgdir()` and `copyuvm()` in `vm.c`.
- [ ] Trace a user protection fault through `trap.c` to process termination.
- [ ] Inspect `sysfile.c` and `copyout()` to distinguish kernel reads from
  kernel writes to user memory.

**Exit criterion:** explain how a virtual address reaches a physical page,
where write permission is checked, and why changing a PTE may require a TLB
refresh. The mathematics needed is page number = address / 4096 and page
offset = address % 4096, plus alignment and overflow checks.

## Checkpoint 3: implement both syscalls with one permission helper — complete

Implemented as `setuvmwrite()` in `vm.c`, wired through `sys_mprotect` /
`sys_munprotect` in `sysproc.c` (syscall numbers 22 and 23). `copyuvm()` already
copies `PTE_FLAGS`, so no change was needed for fork; this is tested in
checkpoint 5.

- [x] Add unused syscall numbers, dispatch entries, wrappers, user prototypes
  and assembly stubs following an existing syscall.
- [x] Implement a shared VM helper taking the range and desired write state.
- [x] Validate alignment, positive length and multiplication/addition overflow
  before deriving the end address.
- [x] Require the full page span to be within the process's user bounds.
- [x] Walk every requested PTE without allocating missing page tables. Reject
  absent mappings, non-user pages, guard pages and kernel addresses.
- [x] Use a validation pass followed by an update pass so a bad later page
  cannot leave earlier pages partially protected or unprotected.
- [x] Clear or set only `PTE_W`, then refresh translations using the x86
  mechanism described in the specification.
- [x] Verify existing `copyuvm()` preserves the flags; change it only if an
  actual failing test shows that an adjustment is needed.

**Likely files:** `vm.c`, `defs.h`, `sysproc.c`, `syscall.c`, `syscall.h`,
`user.h` and `usys.S`. Keep changes small and explain each one.

**Exit criterion:** a minimal user program can protect and unprotect a full
allocated data page, with successful return values and correct read/write
behavior. No unrelated kernel behavior changes.

## Checkpoint 4: handle kernel writes to protected user buffers — complete

Before the fix, `read()` from a pipe into a protected page panicked the guest
kernel (`unexpected trap 14 ... panic: trap`), because xv6 sets `CR0.WP`.
`sys_read`, `sys_fstat` and `sys_pipe` now use `argptrw()`, which adds
`checkuvmwrite()` (every touched page present, user and writable) to the
existing bounds check; they return `-1` instead. `copyout()` also refuses
non-writable pages; its only callers (`exec`) target a fresh, writable stack.
`write()` keeps using `argptr()`, so protected pages remain valid sources.

**Guarantee and limitations.** After `mprotect`, neither user code nor these
syscalls can modify the page. The check-then-write is safe because the target
is one CPU, there are no threads and a process cannot change its own page
table while it is inside another syscall; a multithreaded kernel would need to
hold a lock or fault-handle instead. `exec()` replaces the whole address space
and `sbrk()` shrink frees protected pages normally; new pages are writable.

A user-mode write fault is only part of the behavior to verify. In this xv6
base, some syscalls write directly to user buffers; an unchecked protected
destination can fault in kernel mode. Other copy paths use a writable kernel
alias of the physical page and can bypass user PTE write permission.

- [x] Audit `read()`, `fstat()` and `pipe()` output buffers and `copyout()`.
- [x] Validate writable user destinations before attempting the write. Invalid
  or read-only output buffers should be rejected without a kernel panic.
- [x] Keep input-buffer checks separate: reading a protected page through
  `write()` must still be allowed.
- [x] Check ranges spanning more than one page, including a writable page
  followed by a protected page.
- [x] Document the exact protection guarantee and any remaining limitations.

**Exit criterion:** protected destination buffers cannot crash the guest
kernel or silently bypass the intended protection; readable buffers remain
usable. No general syscall or memory-management redesign is needed.

## Checkpoint 5: build a focused correctness suite — complete locally

`vmtest.c` implements every row below plus an immediate-effect row: a child
writes a page (caching a writable translation), protects it and writes again
with no context switch; this fails if the CR3 reload in `setuvmwrite()` is
removed. `scripts/smoke.py` now runs `vmtest` in both `smoke` and `check`,
fails on any `FAIL` line or if vmtest is killed, requires its count of faulting
children to equal the kernel's `trap 14 err 7` diagnostics, and confirms the
shell still answers. Linux CI run 4 (commit `2c04dd5`) succeeded, and the same `check` passed on
the Pop!_OS laptop.

Add a user test program, tentatively `vmtest.c`, and register it in `UPROGS`.
Allocate extra heap space and align a full data page; do not accidentally
protect the test program's active stack, allocator metadata or control data.

| Test | Required observation |
| --- | --- |
| Writable control | Store a known value and read it back |
| Protected read | Read the same value successfully |
| Protected user write | Faulting child does not reach its post-write marker |
| Restored write | Unprotect, write a new value and read it back |
| Repeated calls | Protect/protect and unprotect/unprotect behave consistently |
| Multiple pages | Every page in the requested range receives the new permission |
| Fork inheritance | Child receives the parent's protected mapping |
| Fork independence | Child unprotecting its copy does not unprotect the parent |
| Invalid arguments | Reject unaligned addresses, nonpositive length and overflow |
| Invalid mappings | Reject out-of-bounds, kernel and guard-page ranges |
| Atomic rejection | A mixed valid-invalid range changes no earlier permissions |
| Kernel output buffer | Protected destinations are rejected without kernel panic |
| Kernel input buffer | A readable protected source remains valid for `write()` |
| Shell survival | Parent and shell continue after each faulting child |

Use child processes and a pipe/marker protocol to distinguish a write that
incorrectly succeeds from one stopped by a fault. The legacy `wait()` API has
no exit-status argument, so do not assume modern `waitpid()` behavior. Correlate
the child outcome with the actual fault diagnostic; a printed PASS alone is
not sufficient evidence. Check that adjacent pages remain unaffected.

Extend the serial runner only after these tests exist. Finish with a fresh
filesystem and the existing upstream regression suite:

```sh
./scripts/xv6 clean
./scripts/xv6 check
```

Cleaning deletes the guest filesystem, so preserve needed guest data first.
Run only one guest at a time. `smoke` and `check` now include `vmtest`.

**Exit criterion:** feature tests and upstream regression tests pass locally
and in Linux CI, with serial logs retained and any failures explained.

## Checkpoint 6: prepare the live demonstration and submission — materials ready

`vmdemo [value] [pages]` and [docs/WALKTHROUGH.md](docs/WALKTHROUGH.md) (path
diagram, code map, explanations) are in place. Rehearsal on the presentation
machine, the submission itself and the in-person explanation remain for the
student. Checkpoint 2 study items stay unticked: they record the student's own
understanding, which documentation cannot complete on their behalf.

- [x] Prepare a short terminal demo, tentatively `vmdemo.c`, showing a writable
  control, protected read, faulting child write and restored write.
- [x] Show fork inheritance and one rejected range; keep the shell usable.
- [x] Let the examiner choose a value or page count to vary the demonstration.
- [x] Draw the virtual address → PTE → permission check → fault-handler path.
- [x] Walk through the syscall wiring, shared helper, validation passes, TLB
  refresh and tests. Explain existing xv6 behavior versus project additions.
- [x] Explain why the CPU terminates the offending process, why a parent stays
  alive, why fork preserves flags and why cached permissions must be refreshed.
- [ ] Rehearse on the actual presentation machine with dependencies installed.
- [ ] Submit source, exact run instructions, test evidence and a short report
  before the confirmed course deadline; explain the implementation in person.

**Done means:** a reproducible demonstration supported by tests, a code change
the student can explain, and evidence of actual outcomes. Record assistance
and source attribution factually in project documentation.

## Work order and checkpoint records

Follow the checkpoints in order. After each meaningful step, record the changed
files, decisions, exact commands, actual results and remaining work. Keep
private continuation notes and generated logs out of the public commit.

This is a planning/documentation checkpoint. The next implementation milestone
begins when requested; professor suitability confirmation is still a separate
course requirement. Do not silently expand the agreed project scope.
