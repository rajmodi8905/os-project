# os-project

An individual operating-systems course project: **Read-Only Page Protection in xv6**,
based on the [OSTEP virtual-memory project, read-only section](https://github.com/remzi-arpacidusseau/ostep-projects/tree/master/vm-xv6-intro#read-only-code).

**Current stage: baseline setup.** The proposed `mprotect()` and `munprotect()`
system calls are not implemented. Professor suitability confirmation has not yet
been recorded.

## Build and run

Install the dependencies in [docs/SETUP.md](docs/SETUP.md), then run:

```sh
./scripts/xv6 doctor
./scripts/xv6 build
./scripts/xv6 smoke
./scripts/xv6 run
```

Inside the xv6 shell, try `ls`, `echo hello`, or `forktest`.
Exit interactive QEMU with **Ctrl-A, then X**.
`./scripts/xv6 check` also runs upstream `usertests` and saves the serial log in
`artifacts/`. Run only one guest at a time: they use the same project disk images.
`./scripts/xv6 clean` removes generated xv6 binaries and disk images, including
files created inside the guest. Save any needed guest data before cleaning.

## Project scope

- `mprotect(addr, len)`: make `len` existing user pages read-only.
- `munprotect(addr, len)`: restore write permission.
- Validate the complete range before changing any permissions.
- Refresh cached translations and preserve permissions through `fork()`.
- Demonstrate readable protected pages, rejected writes, restored writes,
  inherited permissions, and invalid arguments.

`len` is a count of pages, not bytes. Null-pointer detection and changing the
user-program load address are outside this reduced scope.
See [docs/PLAN.md](docs/PLAN.md) for milestones and the intended demonstration.

## Source and attribution

This repository preserves the history and MIT license of
[mit-pdos/xv6-public](https://github.com/mit-pdos/xv6-public), the x86 xv6 version
matching the OSTEP specification. The upstream base is pinned at
`eeb7b415dbcb12cc362d0783e41c3d1f44066b17` and tagged `xv6-baseline`.
MIT now develops the RISC-V version; using x86 here is a deliberate course-scope
choice. The original upstream overview remains in [README](README).

Setup changes retain GNU C99 and make narrow compiler-warning accommodations
for legacy BIOS mapping code and the recursive shell executor; these do not
implement page protection. Details are in [docs/SETUP.md](docs/SETUP.md).

An AI assistant helped prepare repository setup, scripts and documentation.
Feature implementation and experimental results will be recorded as they occur.
