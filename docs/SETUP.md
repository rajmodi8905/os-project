# Development setup

## Host and guest

The host runs normal development tools. QEMU runs a separate x86 xv6 guest using
only `fs.img` and `xv6.img` in this repository. The helper uses one emulated CPU,
512 MiB of guest RAM and no guest network. Run it as your normal user; no host
kernel changes, bootloader changes or physical-disk access are needed.

## Pop!_OS / Ubuntu on an x86-64 machine

```sh
sudo apt update
sudo apt install build-essential gcc-multilib binutils qemu-system-x86 python3 perl git
git clone https://github.com/rajmodi8905/os-project.git
cd os-project
./scripts/xv6 doctor
./scripts/xv6 smoke
./scripts/xv6 run
```

The native GCC/binutils toolchain is used on x86 Linux; check `uname -m` first.
On the Pop!_OS 24.04 laptop the build and all checks passed without
`gcc-multilib` installed (xv6 uses neither host headers nor the host C library);
it remains in the list because the CI image installs it.

## macOS, including Apple Silicon

With Homebrew and Apple's command-line developer tools installed:

```sh
brew install qemu i686-elf-gcc
./scripts/xv6 doctor
./scripts/xv6 smoke
./scripts/xv6 run
```

The cross-compiler produces x86 ELF binaries; macOS compiles the host-side `mkfs`
utility. No Docker service is required. Override tool discovery if necessary:

```sh
TOOLPREFIX=i686-elf- QEMU=qemu-system-i386 ./scripts/xv6 build
```

## Commands and baseline checks

| Command | Purpose |
| --- | --- |
| `./scripts/xv6 doctor` | Inspect required tools and check 32-bit compilation |
| `./scripts/xv6 build` | Build the kernel and filesystem images |
| `./scripts/xv6 run` | Open the xv6 shell in QEMU |
| `./scripts/xv6 smoke` | Build, boot, execute a shell command and run `forktest` |
| `./scripts/xv6 check` | Also run upstream `usertests` |
| `./scripts/xv6 clean` | Remove generated binaries/images; resets guest data |

Each scripted check terminates its own QEMU process, including on failure.
Logs are local in `artifacts/` and ignored by Git. Upstream `usertests` creates a
sentinel file and must start with a fresh guest filesystem on repeat runs:
run `./scripts/xv6 clean` before another `./scripts/xv6 check`.
The image files must not be used by two QEMU processes at once.

## Compatibility changes

The kernel build uses `-std=gnu99` so newer compiler defaults do not change the
language expected by this older code. `-Werror` stays enabled. Only `mp.o`
disables `-Warray-bounds`, which recent GCC raises for xv6's intentional high
virtual mapping of low physical BIOS memory. Only `sh.o` disables the supported
`-Winfinite-recursion` warning for the original recursive shell executor.
`usertests.o` disables `-Wunused-but-set-variable` for an upstream test counter
diagnosed by GCC 16. These are baseline build accommodations, not
memory-management feature changes.

Recent binutils may report legacy xv6 ELF layout warnings about executable
stacks and RWX segments. They are not evidence that the proposed page-protection
feature exists. No kernel C or assembly behavior was changed for this setup.

## Reading before implementation

1. OSTEP chapters 18 and 19: paging and TLBs.
2. `mmu.h`: `PTE_P`, `PTE_U`, `PTE_W`, page size/alignment.
3. `vm.c`: page lookup, copying page tables and copying to user memory.
4. `syscall.c`, `sysproc.c`, `usys.S`, `user.h`: trace an existing system call.
5. `trap.c`: follow an illegal access from user mode to process termination.
