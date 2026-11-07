// Project test program for mprotect()/munprotect().
#include "types.h"
#include "stat.h"
#include "user.h"

#define PAGE 4096

static int failures;
static int faults;   // children stopped before their post-write marker

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
  if(n == 0)
    faults++;
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

// The child first writes the page so the CPU caches a writable
// translation, then protects it and writes again with no context switch
// in between. Without a TLB refresh in mprotect this write would succeed.
static int
childwritesafterprotect(char *addr)
{
  int fds[2], pid, n;
  char marker;

  pipe(fds);
  pid = fork();
  if(pid == 0){
    close(fds[0]);
    *addr = 'a';
    if(mprotect(addr, 1) == 0){
      *addr = 'b';           // must fault here
      write(fds[1], "W", 1);
    }
    exit();
  }
  close(fds[1]);
  n = read(fds[0], &marker, 1);
  close(fds[0]);
  wait();
  if(n == 0)
    faults++;
  return n == 0;
}

static void
immediate(void)
{
  char *p = allocpages(1);

  check(childwritesafterprotect(p), "mprotect takes effect immediately (TLB refreshed)");
}

static void
repeated(void)
{
  char *p = allocpages(1);

  p[0] = 'R';
  check(mprotect(p, 1) == 0 && mprotect(p, 1) == 0, "mprotect twice returns 0");
  check(childwritefaults(p, 'x'), "still protected after repeated mprotect");
  check(munprotect(p, 1) == 0 && munprotect(p, 1) == 0, "munprotect twice returns 0");
  check(!childwritefaults(p, 'x'), "writable after repeated munprotect");
  p[0] = 'S';
  check(p[0] == 'S', "parent write after repeated munprotect");
}

// Protect the middle three of five pages; neighbours must stay writable.
static void
multiple(void)
{
  char *p = allocpages(5);
  int i, allfault = 1;

  for(i = 0; i < 5; i++)
    p[i * PAGE] = '0' + i;
  check(mprotect(p + PAGE, 3) == 0, "mprotect three pages returns 0");
  for(i = 1; i <= 3; i++)
    if(!childwritefaults(p + i * PAGE + 100, 'x'))
      allfault = 0;
  check(allfault, "every page in the range is protected");
  check(!childwritefaults(p, 'x'), "page before the range still writable");
  check(!childwritefaults(p + 4 * PAGE, 'x'), "page after the range still writable");
  check(p[2 * PAGE] == '2', "protected pages still readable");
  check(munprotect(p + PAGE, 3) == 0, "munprotect three pages returns 0");
  for(i = 1; i <= 3; i++)
    p[i * PAGE] = 'w';
  check(p[PAGE] == 'w' && p[3 * PAGE] == 'w', "all three pages writable again");
}

static void
forking(void)
{
  char *p = allocpages(1);
  int fds[2], pid;
  char result = 0;

  p[0] = 'F';
  check(mprotect(p, 1) == 0, "protect page before fork");
  check(childwritefaults(p, 'x'), "fork child inherits protection");

  // A child unprotects and writes its own copy; the parent must stay protected.
  pipe(fds);
  pid = fork();
  if(pid == 0){
    close(fds[0]);
    if(munprotect(p, 1) == 0){
      p[0] = 'c';
      if(p[0] == 'c')
        write(fds[1], "1", 1);
    }
    exit();
  }
  close(fds[1]);
  read(fds[0], &result, 1);
  close(fds[0]);
  wait();
  check(result == '1', "child can munprotect and write its copy");
  check(p[0] == 'F', "parent copy not changed by child");
  check(childwritefaults(p, 'x'), "parent page still protected after child munprotect");

  // And the reverse: a child protecting its copy does not protect the parent.
  check(munprotect(p, 1) == 0, "parent munprotects");
  pid = fork();
  if(pid == 0){
    mprotect(p, 1);
    exit();
  }
  wait();
  p[0] = 'G';
  check(p[0] == 'G', "parent writable after child mprotect");
}

static void
invalid(void)
{
  char *p = allocpages(2);
  char *top = sbrk(0);
  char local;
  char *stack = (char*)((uint)&local & ~(PAGE - 1));
  char *guard = stack - PAGE;

  check(mprotect(p + 1, 1) == -1, "unaligned address rejected");
  check(munprotect(p + 1, 1) == -1, "unaligned munprotect rejected");
  check(mprotect(p, 0) == -1, "zero length rejected");
  check(mprotect(p, -1) == -1, "negative length rejected");
  check(mprotect(p, 0x7fffffff) == -1, "overflowing length rejected");
  check(mprotect((char*)0xfffff000, 2) == -1, "wrapping address rejected");
  check(mprotect(top, 1) == -1, "page past the heap end rejected");
  check(mprotect((char*)0x80000000, 1) == -1, "kernel address rejected");
  check(munprotect((char*)0x80100000, 1) == -1, "kernel munprotect rejected");
  check(mprotect(guard, 1) == -1, "stack guard page rejected");
  check(munprotect(guard, 1) == -1, "stack guard page munprotect rejected");

  // Atomicity: valid pages followed by an invalid one change nothing.
  check(mprotect(p, 3) == -1, "range running past the heap end rejected");
  check(!childwritefaults(p, 'x') && !childwritefaults(p + PAGE, 'x'),
        "earlier pages left writable after rejected range");
  check(mprotect(guard - PAGE, 2) == -1, "range ending in the guard page rejected");
  check(!childwritefaults(guard - PAGE, 'x'),
        "page before the guard left writable after rejected range");
  check(mprotect(p, 2) == 0 && munprotect(p, 3) == -1,
        "munprotect range past the heap end rejected");
  check(childwritefaults(p, 'x') && childwritefaults(p + PAGE, 'x'),
        "earlier pages left protected after rejected munprotect");
  munprotect(p, 2);
  p[0] = 'I';
  check(p[0] == 'I', "valid range still works afterwards");
}

// Syscalls that write to user memory must not write to, or panic on,
// a protected destination. Readable protected sources stay usable.
static void
kernelbuffers(void)
{
  char *p = allocpages(2);
  int fds[2], fd, n;
  struct stat st;

  check(p != 0, "allocate two aligned pages");
  p[0] = 'K';
  p[PAGE] = 'L';
  check(mprotect(p, 1) == 0, "protect first page for kernel-buffer tests");

  // read() destination
  check(pipe(fds) == 0, "create pipe");
  check(write(fds[1], "xy", 2) == 2, "fill pipe");
  check(read(fds[0], p, 2) == -1, "read() into protected page rejected");
  check(p[0] == 'K', "protected page not modified by read()");
  // a range that starts writable and runs into the protected page
  check(munprotect(p, 1) == 0 && mprotect(p + PAGE, 1) == 0,
        "switch protection to second page");
  check(read(fds[0], p + PAGE - 1, 2) == -1,
        "read() spanning writable then protected page rejected");
  check(p[PAGE - 1] == 0 && p[PAGE] == 'L', "neither page modified");
  check(read(fds[0], p, 2) == 2 && p[0] == 'x' && p[1] == 'y',
        "read() into writable page still works");
  close(fds[0]);
  close(fds[1]);

  // write() source: kernel only reads a protected page
  check(mprotect(p, 1) == 0, "protect first page again");
  fd = open("console", 1);
  if(fd < 0)
    fd = 1;
  printf(1, "vmtest: protected bytes via write(): ");
  n = write(fd, p, 2);
  printf(1, "\n");
  check(n == 2, "write() from protected page allowed");
  if(fd != 1)
    close(fd);

  // fstat() and pipe() destinations
  fd = open("vmtest", 0);
  check(fd >= 0, "open vmtest for fstat");
  check(fstat(fd, (struct stat*)p) == -1, "fstat() into protected page rejected");
  check(fstat(fd, &st) == 0, "fstat() into writable buffer works");
  close(fd);
  check(pipe((int*)p) == -1, "pipe() into protected page rejected");
  check(p[0] == 'x', "protected page unchanged");
  check(munprotect(p, 2) == 0, "unprotect both pages");
}

int
main(int argc, char *argv[])
{
  basic();
  immediate();
  repeated();
  multiple();
  forking();
  invalid();
  kernelbuffers();
  printf(1, "vmtest: %d child write faults observed\n", faults);
  if(failures == 0)
    printf(1, "vmtest: ALL PASSED\n");
  else
    printf(1, "vmtest: %d FAILED\n", failures);
  exit();
}
