# Viva preparation: owning the code

The professor's condition: AI use is allowed, but you must take complete
ownership of the code, explain any block correctly, and modify it to change
its behaviour **without AI help**. This guide is built for that. Work through
it with only the code, a terminal and these notes, and do the exercises
yourself before opening the hidden solutions.

How to run the demo: [DEMO.md](DEMO.md). Diagrams: [WALKTHROUGH.md](WALKTHROUGH.md).

## 0. Study plan

| Day | Goal | Done when you can… |
| --- | --- | --- |
| 1 | Background (section 1) and the syscall path (2.1) | Trace `mprotect()` from `user.h` to `sys_mprotect` on paper |
| 2 | `setuvmwrite()` (2.2), line by line | Rewrite it from memory and explain each `if` |
| 3 | Kernel buffers (2.3) and the tests (2.4) | Explain why `read()` used to panic the kernel |
| 4 | Exercises 1–3 (section 4), no AI | All three work and `./scripts/xv6 check` still passes |
| 5 | Experiments (section 5) and the question bank (section 3) | Answer every question aloud in under a minute |
| 6 | Full rehearsal on the demo machine ([DEMO.md](DEMO.md)) | Clean `check` + `vmdemo` + 5-minute code walkthrough |

After each exercise, put the code back to normal with `git checkout -- .`
(this discards your local edits) or `git stash`.

## 1. Background you must know

**Pages.** A page is 4096 bytes (`PGSIZE`, `mmu.h`).
For an address `va`: page number = `va / 4096` = `va >> 12`, and offset =
`va % 4096` = `va & 0xFFF`. A page-aligned address has offset 0.

**Two-level x86 page table.** A 32-bit address splits into
`PDX` (top 10 bits) | `PTX` (next 10 bits) | offset (low 12 bits).
`CR3` holds the physical address of the page directory. The directory entry
`pgdir[PDX(va)]` points to a page table, and entry `PTX(va)` of that table is
the PTE: the physical page number plus flag bits.

**PTE flags used here** (`mmu.h`): `PTE_P` 0x001 present, `PTE_W` 0x002
writable, `PTE_U` 0x004 user-accessible. `PTE_ADDR(pte)` gives the physical
page; `PTE_FLAGS(pte)` gives the low 12 bits.

**Bit operations.** Clear a bit with `*pte &= ~PTE_W`, set it with
`*pte |= PTE_W`, and test it with `(*pte & PTE_W) != 0`.

**TLB.** The CPU caches translations *and their permissions*. If you change a
PTE, the CPU can keep using the old cached copy. Writing `CR3` (`lcr3()`)
flushes the non-global TLB entries of this CPU. (`invlpg` would flush one page.)

**`CR0.WP`.** It is set in `entry.S`. With WP set, even kernel-mode (ring 0)
writes obey read-only PTEs. That is why a kernel `memmove` into a protected
user buffer page-faults.

**Page-fault error code** (`tf->err` for trap 14): bit 0 = page was present
(protection violation, not a missing page), bit 1 = write, bit 2 = user mode.
`err 7` = 1+2+4 = a user write to a present, read-only page. `CR2` holds the
faulting address (`rcr2()`).

**xv6 user address space** (`exec.c`): text and data from 0, then a guard
page (with `PTE_U` cleared by `clearpteu`), then a one-page stack, then the
heap grown by `sbrk()`. `p->sz` is the end of user memory. Everything below
`sz` is mapped; everything at or above `KERNBASE` (0x80000000) is kernel.

## 2. Every project block, explained

See exactly what changed with:
`git fetch --tags && git diff xv6-baseline -- '*.c' '*.h' '*.S' Makefile`.

### 2.1 Syscall wiring (pattern copied from `uptime`)

| File | Line | Meaning |
| --- | --- | --- |
| `user.h` | `int mprotect(void*, int);` | Prototype that user programs compile against |
| `usys.S` | `SYSCALL(mprotect)` | Macro expands to `movl $SYS_mprotect, %eax; int $T_SYSCALL; ret` |
| `syscall.h` | `#define SYS_mprotect 22`, `SYS_munprotect 23` | Numbers that must be unique and match on both sides |
| `syscall.c` | `extern int sys_mprotect(void);` and `[SYS_mprotect] sys_mprotect,` | Table entry: `syscall()` reads `eax`, calls `syscalls[num]()`, puts the return value back in `tf->eax` |
| `Makefile` | `_vmtest\`, `_vmdemo\` in `UPROGS` | Builds the programs and copies them into `fs.img` |

Arguments: user code pushes `len` then `addr`, then calls the stub. `argint(n)`
reads the word at `esp + 4 + 4*n` (the `+4` skips the return address), using
`fetchint`, which checks it lies inside `sz`.

### 2.2 `sysproc.c: changeprotection()` and `vm.c: setuvmwrite()`

`changeprotection(writable)` fetches `addr` and `len`, then calls
`setuvmwrite(curproc->pgdir, curproc->sz, addr, len, writable)`.
`sys_mprotect` passes 0 and `sys_munprotect` passes 1, so one helper serves both
calls and they cannot drift apart.

`setuvmwrite(pgdir, sz, va, npages, writable)` works in five steps:

1. `if(va % PGSIZE != 0 || npages <= 0 || va >= sz) return -1;`
   The address must be page-aligned, there must be at least one page, and the
   start must be inside the process. `npages` is a signed `int`, so this
   also rejects negative values.
2. `if((uint)npages > (sz - va) / PGSIZE) return -1;`
   `(sz - va) / PGSIZE` is how many whole pages fit between `va` and the end.
   Comparing *counts* avoids computing `va + npages*4096` first. That product
   can overflow 32 bits and wrap to a small number that would pass a naive
   `end <= sz` check. Kernel addresses fail too, because `sz < KERNBASE`.
3. `end = va + npages * PGSIZE;` This is safe now, because it is known to be ≤ `sz`.
4. **Pass 1 (validate):** for each page, `walkpgdir(pgdir, a, 0)`. The `0`
   means "do not allocate a page table". The page is rejected if it has no
   PTE, is not present, or is not a user page. The stack guard page fails the
   `PTE_U` test.
5. **Pass 2 (update):** for the same pages, set or clear only `PTE_W`.
   Because pass 1 checked every page, pass 2 cannot fail half-way, so there is
   never a partial change. Then `lcr3(V2P(pgdir))` reloads CR3 to flush the TLB.
   `V2P` is needed because CR3 takes a *physical* address and `pgdir` is a
   kernel virtual address.

**Fork (unchanged code):** `copyuvm()` does `flags = PTE_FLAGS(*pte)` and
maps the child's new copy with the same flags, so read-only survives fork.
Parent and child have different physical pages and different PTEs, so later
changes are independent.

### 2.3 Kernel writes into user memory (`checkuvmwrite`, `argptrw`, `sysfile.c`, `copyout`)

- **Problem:** `read()` copies data into the user buffer from inside the
  kernel. With `CR0.WP` on and the page read-only, this faults in kernel
  mode. `trap()` treats every kernel-mode fault as a kernel bug, so the
  result was `panic: trap`. This was reproduced before the fix.
- **`checkuvmwrite(pgdir, va, len)`:** for every page from `PGROUNDDOWN(va)`
  to `PGROUNDDOWN(va+len-1)`, all of `PTE_P|PTE_U|PTE_W` must be set. It
  covers buffers that span pages (a writable page followed by a read-only one).
  `len == 0` is allowed, because nothing will be written.
- **`argptrw(n, pp, size)`:** calls the existing `argptr` (bounds check), then
  `checkuvmwrite`.
- **Callers:** `sys_read` (destination buffer), `sys_fstat` (`struct stat`
  output) and `sys_pipe` (`int fd[2]` output) use `argptrw`. `sys_write` still
  uses `argptr`, because it only *reads* the user buffer, so a protected page
  is a valid source.
- **`copyout()`:** writes through the kernel's own alias of the physical page,
  which is always writable, so it would silently bypass `PTE_W`. A
  `checkuvmwrite(..., 1)` per page closes that hole. Its only caller is `exec`,
  writing to a brand-new stack, so its behaviour is unchanged today.
- **Why check-then-write is safe here:** one CPU, no threads, and the process
  is busy in this syscall, so nothing can call `mprotect` between the check
  and the write.

### 2.4 Tests (`vmtest.c`) and the runner (`scripts/smoke.py`)

- `allocpages(n)` uses `sbrk` to round the heap up to a page boundary and
  return `n` fresh pages, so the tests never protect the stack or `malloc` data.
- `childwritefaults(addr, v)` forks a child that writes `v` to `addr` and then
  writes a marker byte into a pipe. The parent `read()`s the pipe. If it gets
  EOF (`n == 0`), the child died before the marker, so the write faulted.
  xv6's `wait()` returns no exit status, which is why a pipe is used instead.
- `childwritesafterprotect` makes the child write first (caching a writable TLB
  entry), then call `mprotect`, then write again with no context switch in
  between. Only the `lcr3` flush makes this fault.
- The `faults` counter is printed at the end. `smoke.py` checks that it equals
  the number of kernel `trap 14 err 7` lines, then checks that the shell
  answers an `echo`.
- Test groups: `basic`, `immediate`, `repeated`, `multiple` (three pages, with
  neighbours untouched), `forking` (inheritance and independence both ways),
  `invalid` (alignment, length, overflow, heap end, kernel, guard page,
  atomicity), and `kernelbuffers` (read/fstat/pipe rejected, write allowed).

### 2.5 Existing xv6 code you must also be able to explain

- `walkpgdir()` (`vm.c`): finds the PTE. With `alloc=1` it creates a page table.
- `trap()` default case (`trap.c`): a user-mode fault prints the
  `pid ... trap 14 err 7 ... addr ...` message, sets `killed = 1`, and calls
  `exit()` on the way back to user space. A kernel-mode fault calls `panic`.
- `exec()` guard page: `clearpteu(pgdir, sz - 2*PGSIZE)`.

## 3. Question bank (answer aloud, then check above)

1. Why must `addr` be page-aligned? Why is `len` in pages, not bytes?
2. What exactly does `*pte &= ~PTE_W` do to the other bits?
3. Why two passes over the PTEs instead of one?
4. Why `walkpgdir(..., 0)` and not `alloc = 1`? What would `1` do on a bad address?
5. Show an overflow that a naive `va + len*4096 <= sz` check misses.
   (Example: `va = 0x1000`, `len = 0x100000`: `len*4096 = 2^32`, which wraps to 0.)
6. What happens without `lcr3`? Why did the suite need a special test to notice?
7. Why `V2P(pgdir)` inside `lcr3`?
8. Why does the child die but not the parent? Who prints the `trap 14` line?
9. Decode `trap 14 err 7`. What would `err 6` mean? (A write in user mode to a
   page that is not present.)
10. Why does `fork()` keep the protection? Are parent and child sharing a page?
11. Why did `read()` into a protected buffer panic the kernel, and how is it fixed?
12. Why is `write()` from a protected buffer still allowed?
13. Why is the guard page rejected, and which bit makes it fail?
14. Can a process protect its own code at address 0? (Yes: text is a user page.
    The project does not change null-pointer behaviour.)
15. What happens to protected pages after `exec()`, and after `sbrk(-n)`?
16. Is the check-then-write in `argptrw` safe on a multi-CPU, multithreaded
    kernel? Why is it safe here?
17. What would you change to support more than one CPU? (Every CPU running this
    process would need a TLB shootdown. xv6 processes run on one CPU at a time,
    and other CPUs reload CR3 on a context switch.)
18. Why use a pipe in the tests instead of `wait()`'s exit status?
19. What do `mprotect` and `munprotect` return, and when?
20. Walk me from `mprotect(p, 2)` in C to the PTE change, naming every file.

## 4. Modification exercises (do these without AI)

For each exercise, make the change, run `./scripts/xv6 build`, test it in
`./scripts/xv6 run`, then put the code back with `git checkout -- .`. Each
solution was checked in a scratch copy of the project.

### Exercise 1: add `getprot(addr)` (very likely in a viva)

Return `1` if the page containing `addr` is writable, `0` if it is read-only,
and `-1` if it is not a valid user page. Touch the same files as `mprotect`,
use number 24, and write a tiny user program that prints `getprot` before and
after `mprotect`.

<details><summary>Solution sketch</summary>

- `syscall.h`: `#define SYS_getprot 24`; `syscall.c`: `extern int sys_getprot(void);`
  and `[SYS_getprot] sys_getprot,`; `usys.S`: `SYSCALL(getprot)`;
  `user.h`: `int getprot(void*);`; `defs.h`: `int getuvmprot(pde_t*, uint, uint);`
- `vm.c`:
  ```c
  int
  getuvmprot(pde_t *pgdir, uint sz, uint va)
  {
    pte_t *pte;
    if(va >= sz)
      return -1;
    pte = walkpgdir(pgdir, (void*)va, 0);
    if(pte == 0 || (*pte & PTE_P) == 0 || (*pte & PTE_U) == 0)
      return -1;
    return (*pte & PTE_W) ? 1 : 0;
  }
  ```
- `sysproc.c`: `argint(0, &addr)`, then
  `return getuvmprot(myproc()->pgdir, myproc()->sz, (uint)addr);`
- Add `_yourprog\` to `UPROGS`. Expected: `1` before, `0` after `mprotect`,
  `-1` for `0x80000000`, `1` for address 0 (code is a writable user page).
</details>

### Exercise 2: make `len` a byte count instead of a page count

`mprotect(p, 5000)` should protect two pages (round up). `len <= 0` is still an error.

<details><summary>Solution sketch</summary>

In `changeprotection()`, before calling `setuvmwrite`:
```c
if(len <= 0)
  return -1;
len = (len - 1) / PGSIZE + 1;   // round up without overflowing len + 4095
```
`mprotect(p, 5000)` then protects `p` and `p+4096`, and `munprotect(p, 1)`
unprotects only `p`. Some `vmtest` cases assume page counts and will now fail.
Explain why if asked.
</details>

### Exercise 3: a clearer kernel message on protection faults

When a user process writes to a read-only page, print
`pid N name: write to read-only page 0x...` before the usual trap line.

<details><summary>Solution sketch</summary>

In `trap.c`, in the user-space branch of `default:` (before the existing `cprintf`):
```c
if(tf->trapno == T_PGFLT && (tf->err & 7) == 7)
  cprintf("pid %d %s: write to read-only page 0x%x\n",
          myproc()->pid, myproc()->name, PGROUNDDOWN(rcr2()));
```
`PGROUNDDOWN` comes from `mmu.h`, which `trap.c` already includes.
</details>

### Exercise 4: make `read()` kill the caller instead of returning -1

If the destination buffer is protected, behave as if the process had written
to it from user mode: kill it.

<details><summary>Hint</summary>

In `sys_read`, separate the `argptr` check from `checkuvmwrite`. On failure, set
`myproc()->killed = 1` and return `-1`; `trap()` calls `exit()` after the
syscall returns. Update the related `vmtest` case to run inside a child and
expect it to die.
</details>

### Exercise 5: refuse to protect the text page at address 0

Make `mprotect` reject any range that includes page 0.

<details><summary>Hint</summary>

Add `va == 0` (meaning the range starts at page 0) to the first check in
`setuvmwrite`. Since ranges are contiguous and start at `va`, that is the only
way a range can include page 0. Consider whether `munprotect` should get the
same rule.
</details>

## 5. Experiments that prove your understanding

Run each one, observe the result, and restore with `git checkout -- vm.c`.

| Change in `vm.c: setuvmwrite` | Run | Expected result |
| --- | --- | --- |
| Delete the `lcr3(V2P(pgdir));` line | `./scripts/xv6 smoke` | `vmtest: FAIL mprotect takes effect immediately (TLB refreshed)` |
| Move the PTE update into pass 1 (one pass) | `./scripts/xv6 smoke` | The rejected guard-page range leaves a program page read-only; vmtest is killed and the runner fails |
| Remove `|| (*pte & PTE_U) == 0` | `vmtest` | The "stack guard page rejected" checks fail |
| In `sysfile.c`, change `argptrw` back to `argptr` in `sys_read` | `vmtest` | `panic: trap` (the kernel-mode page fault) |

Being able to predict these results before running them is good evidence of ownership.

## 6. Honest disclosure for the viva

An AI assistant drafted the checkpoint 3–6 code and documentation, as stated in
the README. You are expected to own it: be able to rewrite `setuvmwrite`
from memory, complete exercises 1–3 unaided, and explain every row of
section 2.
