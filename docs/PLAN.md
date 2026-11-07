# Read-only page-protection plan

## Status

Repository setup only. `mprotect`/`munprotect` and their tests are not yet
implemented. Suitability confirmation from the professor remains unverified.

## Checkpoints

1. **Baseline setup:** pin upstream x86 xv6, document tooling, build and boot,
   exercise the shell and existing fork/regression tests.
2. **Understand the code:** trace one syscall, a page-table lookup, a user fault,
   and `copyuvm`. Explain these before changing behavior.
3. **Implement protection:** add both syscalls using a shared helper. Validate
   alignment, positive page count, arithmetic overflow, user bounds, mappings
   and user permission for the entire range before changing any PTE. Refresh
   cached translations after changes.
4. **Verify behavior:** reads succeed; user writes to protected pages fault;
   unprotect restores writes; permissions survive fork. Check invalid ranges
   leave all pages unchanged. Examine kernel-to-user write paths so the exact
   protection guarantee is explicit and tested.
5. **Rehearse delivery:** a short terminal demonstration, source walkthrough,
   test evidence and explanation of page permissions, faults and the TLB.

## Intended demonstration

Use a page-aligned allocated data page, with faulting writes isolated in a child
process. Show the operation attempted, actual fault evidence and whether the
child reached its success marker. Do not treat a printed PASS label as proof.
Keep a nonfaulting control and check that the shell/parent remains usable.

The final demonstration should cover:

- Writable page: write and read back a known value.
- Protected page: read back the value; a child write faults.
- Unprotected page: a fresh write and read-back succeeds.
- Fork: the child inherits protection; its later permission changes do not
  incorrectly alter its parent's permissions.
- Invalid input: unaligned address, zero/negative length, overflowing range,
  kernel/unmapped/guard page and mixed valid-invalid ranges.

The existing fork implementation already copies PTE flags. Preserve and test
this behavior rather than inventing an unnecessary replacement.

## Scope boundaries

This implements the read-only part of the
[OSTEP VM project](https://github.com/remzi-arpacidusseau/ostep-projects/tree/master/vm-xv6-intro#read-only-code).
It does not add null-page detection, demand paging, swapping, COW or threads.
The initial execution target is a single QEMU CPU and ordinary xv6 processes.
