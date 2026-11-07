// Project test program for mprotect()/munprotect().
#include "types.h"
#include "stat.h"
#include "user.h"

#define PAGE 4096

static int failures;

static void
check(int ok, char *what)
{
  if(ok)
    printf(1, "vmtest: ok   %s\n", what);
  else {
    printf(1, "vmtest: FAIL %s\n", what);
    failures++;
  }
}

// Grow the heap and return the start of n whole, page-aligned pages
// that nothing else in this program uses.
static char*
allocpages(int n)
{
  char *p = sbrk(0);
  uint pad = (PAGE - (uint)p % PAGE) % PAGE;

  if(sbrk(pad + n * PAGE) == (char*)-1)
    return 0;
  return p + pad;
}

// Run a child that stores value at addr. Returns 1 if the child was
// stopped before its post-write marker (expected for a protected page),
// 0 if the write completed.
static int
childwritefaults(char *addr, char value)
{
  int fds[2], pid, n;
  char marker;

  if(pipe(fds) < 0){
    printf(1, "vmtest: pipe failed\n");
    exit();
  }
  pid = fork();
  if(pid < 0){
    printf(1, "vmtest: fork failed\n");
    exit();
  }
  if(pid == 0){
    close(fds[0]);
    printf(1, "vmtest: child writing 0x%x (a fault is expected if protected)\n",
           (uint)addr);
    *addr = value;
    write(fds[1], "W", 1);   // only reached if the write succeeded
    exit();
  }
  close(fds[1]);
  n = read(fds[0], &marker, 1);
  close(fds[0]);
  wait();
  return n == 0;
}

static void
basic(void)
{
  char *p = allocpages(1);

  check(p != 0, "allocate an aligned page");
  p[0] = 'A';
  check(p[0] == 'A', "writable control store/load");
  check(mprotect(p, 1) == 0, "mprotect one page returns 0");
  check(p[0] == 'A', "protected page is still readable");
  check(childwritefaults(p, 'B'), "write to protected page faults in child");
  check(p[0] == 'A', "parent value unchanged after child fault");
  check(munprotect(p, 1) == 0, "munprotect one page returns 0");
  p[0] = 'C';
  check(p[0] == 'C', "write after munprotect succeeds");
  check(!childwritefaults(p, 'D'), "child write to unprotected page succeeds");
}

int
main(int argc, char *argv[])
{
  basic();
  if(failures == 0)
    printf(1, "vmtest: ALL PASSED\n");
  else
    printf(1, "vmtest: %d FAILED\n", failures);
  exit();
}
