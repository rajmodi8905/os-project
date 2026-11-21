// EXAMPLE ANSWER for a viva question:
// "refuse page 0, and allow at most 16 pages per call".
// Illustration only. This file is NOT part of the kernel build.

// ---- vm.c, setuvmwrite(): only the FIRST check changes ----
  if(va % PGSIZE != 0 || npages <= 0 || va >= sz)        // before
    return -1;

  if(va % PGSIZE != 0 || npages <= 0 || npages > 16      // cap: at most 16 pages
     || va == 0 || va >= sz)                             // refuse page 0
    return -1;

// Both rules apply to mprotect AND munprotect, because they share this helper.
// The range always starts at va, so va == 0 is the only way to include page 0.
