// Project demonstration of mprotect()/munprotect().
// Usage: vmdemo [value] [pages]   (defaults: 42 and 2 pages, max 16)
#include "types.h"
#include "stat.h"
#include "user.h"

#define PAGE 4096

static char*
allocpages(int n)
{
  char *p = sbrk(0);
  uint pad = (PAGE - (uint)p % PAGE) % PAGE;

  if(sbrk(pad + n * PAGE) == (char*)-1)
    return 0;
  return p + pad;
}

// A child tries to write; the parent reports what happened.
static void
trywrite(char *who, int *addr, int value)
{
  int fds[2], n;
  char ok;

  pipe(fds);
  if(fork() == 0){
    close(fds[0]);
    *addr = value;
    write(fds[1], "1", 1);
    exit();
  }
  close(fds[1]);
  n = read(fds[0], &ok, 1);
  close(fds[0]);
  wait();
  printf(1, "      %s write of %d to 0x%x: %s\n", who, value, (uint)addr,
         n == 1 ? "SUCCEEDED" : "STOPPED by page fault (child killed)");
}

int
main(int argc, char *argv[])
{
  int value = 42, pages = 2, i;
  int *p;

  if(argc > 1)
    value = atoi(argv[1]);
  if(argc > 2)
    pages = atoi(argv[2]);
  if(pages < 1 || pages > 16){
    printf(2, "usage: vmdemo [value] [pages 1-16]\n");
    exit();
  }
  if((p = (int*)allocpages(pages)) == 0){
    printf(2, "vmdemo: sbrk failed\n");
    exit();
  }

  printf(1, "\n[1] %d page(s) at 0x%x, writable control\n", pages, (uint)p);
  for(i = 0; i < pages; i++)
    p[i * PAGE / sizeof(int)] = value + i;
  printf(1, "      stored and read back %d ... %d\n", p[0],
         p[(pages - 1) * PAGE / sizeof(int)]);

  printf(1, "\n[2] mprotect(0x%x, %d) = %d\n", (uint)p, pages, mprotect(p, pages));
  printf(1, "      protected read still works: %d\n", p[0]);
  trywrite("child", &p[(pages - 1) * PAGE / sizeof(int)], value + 100);
  printf(1, "      parent still alive, value unchanged: %d\n",
         p[(pages - 1) * PAGE / sizeof(int)]);

  printf(1, "\n[3] fork inheritance: a new child inherits the read-only page\n");
  trywrite("inherited child", p, value + 200);

  printf(1, "\n[4] invalid requests are rejected and change nothing\n");
  printf(1, "      mprotect(0x%x, 1)  unaligned       = %d\n",
         (uint)p + 1, mprotect((char*)p + 1, 1));
  printf(1, "      mprotect(0x%x, 0)  zero length     = %d\n", (uint)p, mprotect(p, 0));
  printf(1, "      munprotect(0x%x, %d) past heap end = %d\n",
         (uint)p, pages + 1, munprotect(p, pages + 1));
  trywrite("child (after rejected munprotect)", p, value + 300);

  printf(1, "\n[5] munprotect(0x%x, %d) = %d\n", (uint)p, pages, munprotect(p, pages));
  p[0] = value + 400;
  printf(1, "      parent wrote and read back %d\n", p[0]);
  trywrite("child", p, value + 500);

  printf(1, "\nvmdemo done; the shell is still running.\n");
  exit();
}
