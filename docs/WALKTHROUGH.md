# Walkthrough and demonstration guide

This explains how read-only page protection works in this xv6 tree and how to
demonstrate it. It is study material for checkpoint 2 and the checkpoint 6
explanation; reading it does not replace tracing the code yourself.

## Live demonstration

```sh
./scripts/xv6 build
./scripts/xv6 run
```

Inside the guest shell:

```
vmdemo            # value 42, 2 pages
vmdemo 7 3        # examiner chooses the value and page count (1-16)
vmtest            # full suite; ends with "vmtest: ALL PASSED"
echo still alive  # the shell survives every faulting child
```

`vmdemo` shows: (1) a writable control, (2) `mprotect`, a protected read and a
child's write stopped by a page fault while the parent continues, (3) fork
inheritance, (4) rejected requests that change nothing, and (5) `munprotect`
followed by successful writes. Each stopped write is matched by a kernel line
such as `pid 5 vmdemo: trap 14 err 7 ... addr 0x4000--kill proc`.
Exit QEMU with **Ctrl-A, then X**.

## From a virtual address to a permission check

```
 user store to va = 0x00004010
        |
        v
 +-------------------+  PDX(va) = va >> 22 = 0          (mmu.h)
 | page directory    |---> PDE: physical address of a page table
 +-------------------+
        |  PTX(va) = (va >> 12) & 0x3FF = 4
        v
 +-------------------+
 | page table        |---> PTE = physical page | PTE_P | PTE_U | [PTE_W]
 +-------------------+
        |
        v
  CPU checks: present? user page? write allowed?   (TLB caches the result)
        |  PTE_W clear  ->  page fault, trap 14, error code 7
        v                   (bit 0 present, bit 1 write, bit 2 user mode)
  trap.c default case: user mode -> print "trap 14 err 7 ... --kill proc",
  set killed = 1 -> exit() at return to user space; parent's wait() returns.
```

Page number = address / 4096, offset = address % 4096. A page-aligned address
has offset 0. `PTE_ADDR(pte)` keeps the physical page; `PTE_FLAGS(pte)` keeps
the low 12 permission bits.

## Existing xv6 code versus project additions

| Location | Existing xv6 behaviour used | Project addition |
| --- | --- | --- |
| `syscall.h`, `syscall.c`, `usys.S`, `user.h` | Syscall numbers, dispatch table, `int $T_SYSCALL` stubs | `SYS_mprotect` 22, `SYS_munprotect` 23 |
| `sysproc.c` | `argint()` to fetch arguments | `sys_mprotect`, `sys_munprotect`, shared `changeprotection()` |
| `vm.c` | `walkpgdir()` finds a PTE; `alloc = 0` never allocates | `setuvmwrite()`: validate range, then change only `PTE_W`, then `lcr3()` |
| `vm.c` | `copyuvm()` copies `PTE_FLAGS` into the child | Unchanged; tests show fork keeps protection |
| `vm.c` | `copyout()` writes via the kernel's alias of the page | Also refuses non-writable pages |
| `syscall.c`, `sysfile.c` | `argptr()` checks only `0 <= addr < sz` | `argptrw()` + `checkuvmwrite()` for `read`, `fstat`, `pipe` destinations |
| `trap.c` | Kills a faulting user process; panics on a kernel-mode fault | Unchanged |
| `entry.S` | Sets `CR0.WP`, so the kernel also obeys read-only PTEs | Unchanged; this is why checkpoint 4 was needed |
| `vmtest.c`, `vmdemo.c`, `scripts/smoke.py` | — | Tests, demo and serial runner integration |

## `setuvmwrite()` step by step (`vm.c`)

1. Reject an unaligned `va`, `npages <= 0`, or `va >= sz`.
2. Reject `npages > (sz - va) / PGSIZE`. Comparing page counts avoids computing
   `va + npages * 4096`, which could overflow 32 bits and wrap to a small,
   apparently valid address. Since `sz` is below `KERNBASE`, kernel addresses
   are rejected here too.
3. **Validation pass:** every page must have a PTE with `PTE_P` and `PTE_U`.
   The stack guard page created by `exec()` has `PTE_U` cleared, so it fails.
4. **Update pass:** set or clear only `PTE_W`; the physical address and other
   bits are untouched. Because pass 3 succeeded for every page, a bad page can
   no longer cause a partial change.
5. `lcr3(V2P(pgdir))` reloads the page-directory register, which flushes this
   CPU's TLB. Without it the CPU may keep using a cached writable translation;
   `vmtest`'s immediate-effect test fails when this line is removed.

## Why each behaviour happens

- **The offending process dies, the parent lives:** the fault occurs in user
  mode, so `trap()` marks only that process killed. The parent is a separate
  address space and learns the outcome via a pipe and `wait()`.
- **Fork preserves protection:** `copyuvm()` copies each page's contents and
  its flags, so the child gets its own physical page that is also read-only.
  Since the pages are separate copies, later changes are independent.
- **Kernel writes:** xv6 sets `CR0.WP`, so a kernel store into a read-only
  user page faults in kernel mode, which `trap()` treats as a kernel bug and
  panics. Before checkpoint 4, `read()` into a protected buffer did exactly
  that. Output buffers are now checked first and the syscall returns `-1`.
  `write()` only reads the buffer, so protected sources still work.
- **Check-then-write is safe here:** one CPU target, no threads, and a process
  cannot run `mprotect` while it is inside another syscall.

## Limitations

New heap pages from `sbrk()` are writable; `exec()` starts a fresh address
space. Null-pointer protection, copy-on-write, demand paging, swapping and
threads are outside the project scope.
