// EXAMPLE ANSWER for a viva question:
// "print a clearer message when a user process writes to a read-only page".
// Illustration only. This file is NOT part of the kernel build.

// ---- trap.c: inside the default case, user-space branch ----
    // New lines go BEFORE the existing cprintf of the generic message.
    if(tf->trapno == T_PGFLT && (tf->err & 7) == 7)   // present + write + user
      cprintf("pid %d %s: write to read-only page 0x%x\n",
              myproc()->pid, myproc()->name, PGROUNDDOWN(rcr2()));
    // In user space, assume process misbehaved.
    cprintf("pid %d %s: trap %d err %d on cpu %d "
            "eip 0x%x addr 0x%x--kill proc\n",
            myproc()->pid, myproc()->name, tf->trapno,
            tf->err, cpuid(), tf->eip, rcr2());
    myproc()->killed = 1;

// rcr2() returns the faulting address. PGROUNDDOWN comes from mmu.h.
// Bits of err: 1 = page was present, 2 = it was a write, 4 = user mode.
