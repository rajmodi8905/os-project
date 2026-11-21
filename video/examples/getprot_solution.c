// EXAMPLE ANSWER for a viva question: "add a getprot(addr) system call".
// Illustration only. This file is NOT part of the kernel build.
// Returns 1 if the page holding addr is writable, 0 if read-only, -1 if invalid.

// ---- vm.c: the helper that inspects the PTE ----
int
getuvmprot(pde_t *pgdir, uint sz, uint va)
{
  pte_t *pte;

  if(va >= sz)                       // outside the process
    return -1;
  pte = walkpgdir(pgdir, (void*)va, 0);   // 0 = never allocate
  if(pte == 0 || (*pte & PTE_P) == 0 || (*pte & PTE_U) == 0)
    return -1;                       // missing, not present, or kernel page
  return (*pte & PTE_W) ? 1 : 0;     // test the write bit only
}

// ---- sysproc.c: the syscall wrapper ----
int
sys_getprot(void)
{
  int addr;

  if(argint(0, &addr) < 0)
    return -1;
  return getuvmprot(myproc()->pgdir, myproc()->sz, (uint)addr);
}

// ---- the wiring, same pattern as mprotect ----
// syscall.h : #define SYS_getprot 24
// syscall.c : extern int sys_getprot(void);   and   [SYS_getprot] sys_getprot,
// usys.S    : SYSCALL(getprot)
// user.h    : int getprot(void*);
// defs.h    : int getuvmprot(pde_t*, uint, uint);
