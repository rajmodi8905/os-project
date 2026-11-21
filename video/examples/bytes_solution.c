// EXAMPLE ANSWER for a viva question:
// "make len a number of BYTES instead of pages, rounding up".
// Illustration only. This file is NOT part of the kernel build.

// ---- sysproc.c: only changeprotection() changes ----
static int
changeprotection(int writable)
{
  int addr, len;
  struct proc *curproc = myproc();

  if(argint(0, &addr) < 0 || argint(1, &len) < 0)
    return -1;
  if(len <= 0)                    // still reject zero and negative
    return -1;
  len = (len - 1) / PGSIZE + 1;   // bytes -> pages, rounded up
                                  // (never computes len + 4095, so no overflow)
  return setuvmwrite(curproc->pgdir, curproc->sz, (uint)addr, len, writable);
}

// Results: mprotect(p, 5000) protects two pages (p and p+4096),
// munprotect(p, 1) unprotects only the page at p.
// Some vmtest cases assume page counts, so they would now fail.
