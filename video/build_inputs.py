#!/usr/bin/env python3
"""Generate the repo2video engine inputs (plan/scripts JSON) and a readable script.

Run from anywhere:  python3 video/build_inputs.py
Writes: video/plan.json, video/scripts.json, video/parts/*, video/narration.md
It also checks every code line range against the real files, so if you edit a
source file and the line numbers move, this script fails loudly instead of the
video showing the wrong lines.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "video"

# (id, title, type, part, narration, slides, mermaid, code blocks)
S = []


def sec(sid, title, typ, part, narration, slides=None, mermaid=None, code=None):
    S.append(dict(id=sid, title=title, type=typ, part=part, narration=narration.strip(),
                  slides=slides, mermaid=mermaid, code=code or []))


def blk(path, start, end, focus, hints, order=1):
    return dict(filePath=path, startLine=start, endLine=end, focusStart=focus,
                commentHints=[dict(insertAfterLine=a, comment=c) for a, c in hints],
                revealOrder=order)


# ---------------------------------------------------------------- PART 1
sec("intro", "Welcome: what this video covers", "overview", 1, """
Welcome. This video is your viva preparation for the read-only page protection project in x86 xv6.
It has four parts. First, the problem and the background you need. Second, our solution and a walkthrough of every block of code we added.
Third, the tests, the demo and the evidence. Fourth, the part your professor cares about most: how to change the code yourself.
We will look at three example modifications, then go through the likely viva questions with short answers.
One rule from your professor: AI help is allowed, but you must own every line. So pause the video often, and rewrite each function from memory.
""", slides=dict(description="Viva preparation: read-only page protection in x86 xv6", bullets=[
    "Part 1: the problem and the background",
    "Part 2: our solution, block by block",
    "Part 3: tests, demo and evidence",
    "Part 4: modify the code yourself, then viva questions",
    "Rule: you must own and explain every line"]))

sec("problem", "The problem statement", "overview", 1, """
The assignment comes from the O S T E P virtual memory project. We must add two system calls to xv6.
m protect takes a page-aligned address and a length in pages, and makes those pages read-only.
m unprotect does the reverse and restores write permission. Both return zero on success and minus one on an invalid request.
A program must still be able to read a protected page. Only writes must be stopped. A write to a protected page must kill that process, not the whole system.
Three extra requirements matter. A failed call must change nothing. The change must take effect immediately. And the permissions must survive fork, with parent and child independent afterwards.
Null pointer protection, swapping and copy on write are out of scope.
""", slides=dict(description="Read-only page protection in x86 xv6", bullets=[
    "`int mprotect(void *addr, int len)` makes `len` pages read-only",
    "`int munprotect(void *addr, int len)` restores write access",
    "`addr` is page-aligned and `len` counts pages, not bytes",
    "Reads still work; a write must kill only that process",
    "A failed call changes nothing; the change is immediate",
    "Permissions survive `fork()` and stay independent"]))

sec("paging", "Background: how a virtual address becomes a physical page", "architecture", 1, """
Before the solution, the hardware. A page is 4096 bytes. A 32-bit virtual address splits into three fields.
The top ten bits pick an entry in the page directory. The next ten bits pick an entry in a page table. The low twelve bits are the offset inside the page.
The register C R 3 holds the physical address of the page directory. The entry that finally names the physical page is the page table entry, or P T E.
Page number is the address divided by 4096. Offset is the address modulo 4096. A page-aligned address has offset zero.
Alongside the physical page number, the P T E stores permission bits. Our whole project is about changing one of them.
""", slides=dict(description="Two-level x86 paging", bullets=[
    "Page size is 4096 bytes: offset = address % 4096",
    "Top 10 bits: page directory index (`PDX`)",
    "Next 10 bits: page table index (`PTX`)",
    "`CR3` points to the page directory of the running process",
    "The PTE holds the physical page plus permission bits"]),
    mermaid="graph LR\n  VA[Virtual address] --> PD[Page directory via CR3]\n  PD -->|PDX| PT[Page table]\n  PT -->|PTX| PTE[PTE: physical page + flags]\n  PTE --> PA[Physical page + offset]")

sec("pteflags", "Background: the PTE permission bits", "code_walkthrough", 1, """
This is mmu dot h. Here are the constants we use all project long.
P G S I Z E is 4096. P G R O U N D D O W N rounds an address down to its page. P T E underscore P means present. P T E underscore W means writable. P T E underscore U means user accessible.
P T E underscore A D D R keeps the physical page. P T E underscore F L A G S keeps the low twelve bits, the permissions.
To clear a bit we AND with the inverse of the mask. To set a bit we OR with the mask. To test a bit we AND and compare with zero.
Remember these three bit operations. The viva will probe them.
""", code=[blk("mmu.h", 82, 101, 94, [
    (85, "`PGSIZE` is 4096 bytes"),
    (91, "`PGROUNDDOWN` clears the low 12 bits"),
    (94, "`PTE_P`: the page is mapped"),
    (95, "`PTE_W`: writes are allowed. Our project toggles this bit"),
    (96, "`PTE_U`: user mode may access the page"),
    (100, "`PTE_ADDR` keeps the physical page"),
    (101, "`PTE_FLAGS` keeps the low 12 permission bits")])])

sec("tlbwp", "Background: the TLB and the write-protect bit", "code_walkthrough", 1, """
Two hardware facts shape the design.
First, the T L B. The processor caches translations together with their permissions. If we change a P T E, the processor may keep using the old cached copy. Writing C R 3 flushes this cache. That is why our code reloads C R 3.
Second, look at entry dot S. It turns on paging and also sets C R 0 W P, the write-protect flag. With W P set, even the kernel obeys read-only pages.
That sounds safe, but it creates a trap for us: if the kernel itself writes into a protected user page, it page faults in kernel mode. We will meet that again in part two.
""", code=[blk("entry.S", 48, 56, 55, [
    (52, "`CR3` is loaded with the boot page directory"),
    (54, "read control register 0"),
    (55, "`CR0_PG` turns paging on; `CR0_WP` makes the kernel obey read-only pages")])])

sec("faultpath", "Background: what a protection fault looks like", "code_walkthrough", 1, """
This is the existing trap handler. When user code writes to a read-only page, the processor raises trap number fourteen, a page fault.
The default case checks the saved code segment. If the fault came from user mode, xv6 prints a message, marks the process killed, and exits it on the way back to user space.
Decode the message. Error code seven is one plus two plus four. One means the page was present. Two means the access was a write. Four means user mode.
So trap fourteen error seven is exactly: a user write to a present page without write permission. That is our protection firing.
If the fault came from kernel mode, the branch above calls panic, and the whole machine stops.
""", code=[blk("trap.c", 82, 95, 89, [
    (83, "kernel-mode fault: this is a kernel bug"),
    (87, "`panic` stops the whole system"),
    (89, "user mode: assume the process misbehaved"),
    (93, "`err` and `rcr2()` give the reason and the faulting address"),
    (94, "only this process is marked killed; the parent lives on")])])

# ---------------------------------------------------------------- PART 2
sec("solution", "Our solution at a glance", "architecture", 2, """
Here is the whole solution on one slide. A user program calls m protect. A tiny assembly stub raises a software interrupt. The kernel dispatches to sys m protect, which fetches the two arguments and calls one shared helper, set u v m write.
The helper validates the whole range first, then clears or sets only the writable bit, then reloads C R 3 to flush the T L B.
The same helper serves m unprotect, so the two calls cannot drift apart.
We then close a second door: system calls that write into user buffers must check the destination is writable, or the kernel itself would fault.
""", slides=dict(description="Seven steps from C call to protected page", bullets=[
    "`mprotect()` stub raises `int $T_SYSCALL`",
    "`sys_mprotect` fetches `addr` and `len`",
    "`setuvmwrite()` validates the whole range first",
    "Then it changes only `PTE_W` and reloads `CR3`",
    "`read`, `fstat`, `pipe` now check their output buffers"]),
    mermaid="graph TD\n  U[User: mprotect addr len] --> S[usys.S stub: int T_SYSCALL]\n  S --> D[syscall.c dispatch table]\n  D --> P[sysproc.c: changeprotection]\n  P --> H[vm.c: setuvmwrite]\n  H --> V[Pass 1: validate every page]\n  V --> W[Pass 2: change only PTE_W]\n  W --> F[lcr3 flushes the TLB]")

sec("wiring_user", "Wiring part 1: the user-side stubs", "code_walkthrough", 2, """
We copied the pattern of an existing call, uptime. In usys dot S, the S Y S C A L L macro defines a function that loads the system call number into E A X, executes int T underscore S Y S C A L L, and returns.
Our two additions are the last two lines: S Y S C A L L m protect and S Y S C A L L m unprotect.
The prototypes in user dot h let user programs compile against them. Nothing else is needed on the user side.
""", code=[blk("usys.S", 1, 33, 32, [
    (9, "number goes in `%eax`, trap into the kernel, then return"),
    (11, "existing calls follow the same one-line pattern"),
    (31, "`uptime` is the call we copied"),
    (32, "project: `mprotect` stub"),
    (33, "project: `munprotect` stub")])])

sec("wiring_kernel", "Wiring part 2: numbers and the dispatch table", "code_walkthrough", 2, """
On the kernel side, syscall dot h gives each call a unique number: twenty-two for m protect and twenty-three for m unprotect.
In syscall dot c, we declare the two handlers with extern, and add two entries to the dispatch table, indexed by those numbers.
When the trap arrives, the function syscall reads the number from E A X, looks it up in the table, calls the handler, and stores the return value back in E A X.
That return value is what the user program sees as the result of m protect.
""", code=[blk("syscall.c", 114, 159, 141, [
    (115, "`uptime` handler declared the same way"),
    (116, "project: handler for `mprotect`"),
    (117, "project: handler for `munprotect`"),
    (133, "existing table entries are indexed by call number"),
    (141, "project: slot 22"),
    (142, "project: slot 23"),
    (151, "the call number arrives in `eax`"),
    (153, "the handler's return value goes back to user space in `eax`")])])

sec("sysproc", "The syscall handlers and the shared helper call", "code_walkthrough", 2, """
In sysproc dot c, change protection is the common front end. It fetches the first and second arguments with arg int. Remember arg int reads the word at stack pointer plus four plus four times n, skipping the return address.
It then calls set u v m write with the current process's page directory, its size, the address, the length, and a flag: one for writable, zero for read-only.
sys m protect passes zero. sys m unprotect passes one. One helper, two thin wrappers.
Notice what is not here: no validation. The helper does all the checking, so the rules live in exactly one place.
""", code=[blk("sysproc.c", 93, 117, 104, [
    (95, "one page count, not bytes"),
    (97, "shared front end for both calls"),
    (102, "`argint` fetches the two user arguments"),
    (104, "all validation lives in `setuvmwrite`"),
    (110, "`mprotect` means writable = 0"),
    (116, "`munprotect` means writable = 1")])])

sec("setuv_a", "setuvmwrite part 1: validate the request", "code_walkthrough", 2, """
Now the heart of the project, set u v m write in vm dot c. It receives the page directory, the process size sz, the start address, the page count, and the desired state.
The first check rejects an unaligned address, a count of zero or less, and a start at or beyond the process size. Because the count is a signed integer, negatives are caught here too.
The second check is subtle. We do not compute address plus count times 4096 yet, because that product can overflow thirty-two bits. Instead we compare the count with how many whole pages fit between the start and the end of the process.
Only after that is the end address safe to compute.
Then pass one: for every page, walk the page table without allocating, and require the entry to exist, be present, and be a user page. The stack guard page has its user bit cleared, so it fails here.
""", code=[blk("vm.c", 313, 340, 325, [
    (318, "returns 0 on success, -1 on an invalid request"),
    (326, "aligned, positive, and starting inside the process"),
    (329, "compare page COUNTS so nothing can overflow"),
    (331, "now safe: this end is within `sz`"),
    (336, "`walkpgdir(..., 0)` never allocates page tables"),
    (337, "must be present and a user page; the guard page fails here")])])

sec("setuv_b", "setuvmwrite part 2: change only the write bit", "code_walkthrough", 2, """
Pass two runs only after pass one succeeded for every page, so it cannot fail halfway. That is how a bad page in the middle of a range never leaves a partial change.
For each page we either OR in the writable bit, or AND with its inverse. All other bits, including the physical address, are untouched.
Finally, lcr3 of V two P of the page directory reloads C R 3 and flushes this processor's T L B. We need V two P because C R 3 takes a physical address while the page directory pointer is a kernel virtual address.
Without this line, the processor could keep using a cached writable translation, and the next write would wrongly succeed.
""", code=[blk("vm.c", 333, 353, 342, [
    (335, "pass 1 loop ends: every page is valid"),
    (342, "pass 2: only now do we modify anything"),
    (345, "set the write bit"),
    (347, "clear the write bit; other bits are unchanged"),
    (350, "the TLB may cache the old permissions"),
    (351, "reloading `CR3` flushes it; `V2P` makes the address physical")])])

sec("overflow", "Why compare counts: the overflow example", "architecture", 2, """
Let us make the overflow concrete. Suppose the start address is 0x1000 and the count is 0x100000, which is two to the twentieth.
Multiply the count by 4096, which is two to the twelfth, and you get two to the thirty-second. In thirty-two bit arithmetic that wraps around to zero.
A naive check that computes start plus count times 4096 would see an end of 0x1000, which looks perfectly valid. Our check compares the count with the number of pages that actually fit, and correctly rejects it.
If your professor asks why we wrote the check that way, this is the answer.
""", slides=dict(description="32-bit wraparound", bullets=[
    "start = `0x1000`, count = `0x100000` (2^20 pages)",
    "`count * 4096` is 2^32, which wraps to 0 in 32 bits",
    "Naive end address = `0x1000`: looks valid, but is wrong",
    "Ours: `count > (sz - va) / PGSIZE` is rejected correctly",
    "Also catches negative counts and addresses that wrap"]))

sec("twopass", "Why two passes and why a TLB flush", "architecture", 2, """
Two design decisions deserve a clear answer.
Why two passes? The specification says a failed call must leave previous permissions unchanged. If we changed pages while validating, a bad page late in the range would leave the earlier pages already modified. Validating everything first makes the update pass unable to fail.
Why the T L B flush? Our own test proves it matters. A child first writes a page, so the processor caches a writable translation. It then calls m protect and writes again with no context switch. Only the C R 3 reload makes that second write fault.
Earlier tests missed this, because a freshly forked child reloads C R 3 anyway. So we added a dedicated test.
""", slides=dict(description="Two decisions you must defend", bullets=[
    "Two passes make a failed call change nothing",
    "Merging them left a program page read-only after a rejected range",
    "`lcr3` flushes cached permissions so protection is immediate",
    "A dedicated test fails if the flush is removed",
    "Fork hid the bug in the first version of the tests"]))

sec("fork", "Fork inherits protection: copyuvm", "code_walkthrough", 2, """
Fork needed no change. Look at the existing copy u v m. For every page of the parent, it reads the flags with P T E underscore F L A G S, allocates a fresh physical page, copies the contents, and maps the child's copy with the same flags.
So if the parent page is read-only, the child's copy is read-only too. That is inheritance.
The two copies are different physical pages with different P T Es. Later changes by one process cannot affect the other.
Our tests check both directions: a child unprotecting its copy leaves the parent protected, and a child protecting its copy leaves the parent writable.
""", code=[blk("vm.c", 380, 410, 398, [
    (383, "builds the child's page table"),
    (393, "find the parent's PTE; never allocates"),
    (397, "physical page of the parent"),
    (398, "all permission bits are remembered, including `PTE_W`"),
    (399, "the child gets its own physical page"),
    (401, "contents are copied"),
    (402, "mapped with the SAME flags, so read-only is inherited")])])

sec("kbuf_problem", "The second door: the kernel writing into user memory", "architecture", 2, """
Now the problem we found by testing. A user write to a protected page faults in user mode, and the process dies. But what if the kernel writes into a protected user page for the user?
The read system call copies data into a user buffer from inside the kernel. Because C R 0 W P is set, a kernel write to a read-only page faults in kernel mode. The trap handler treats any kernel fault as a kernel bug and calls panic.
We reproduced this: read from a pipe into a protected page crashed the guest with panic trap, before the fix.
The rule we adopted: if the kernel will write into a user buffer, check that every page of it is writable first, and return minus one if not. If the kernel only reads the buffer, as write does, a protected page is fine.
""", slides=dict(description="Reproduced before fixing", bullets=[
    "`read()` into a protected page: kernel-mode write fault",
    "`trap()` treats kernel-mode faults as bugs: `panic: trap`",
    "Fix: check output buffers are writable, return `-1` if not",
    "`write()` only READS the buffer, so protected sources are fine",
    "`copyout()` also honours `PTE_W`"]))

sec("checkuvm", "checkuvmwrite: is this buffer writable?", "code_walkthrough", 2, """
The new function check u v m write takes a page directory, a start address, and a length.
A length of zero is fine, nothing will be written. Otherwise it computes the last byte's page, and loops from the first page to the last, so buffers that span several pages are covered, including a writable page followed by a protected one.
For each page, all three bits must be set: present, user, and writable. The expression masks the entry with the three flags and compares with all three. Anything less returns minus one.
Like pass one of our main helper, it never allocates, so checking cannot change the page tables.
""", code=[blk("vm.c", 355, 378, 369, [
    (361, "returns 0 only if EVERY touched page is writable"),
    (367, "nothing to write means nothing to check"),
    (369, "last page touched by `[va, va+len)`"),
    (371, "no allocation while checking"),
    (372, "needs `PTE_P`, `PTE_U` and `PTE_W` all set"),
    (374, "the loop stops after the last page")])])

sec("argptrw", "argptrw: the bounds check plus the writable check", "code_walkthrough", 2, """
In syscall dot c, the existing arg ptr only checks that the buffer lies inside the process. Our arg ptr w builds on it.
It calls arg ptr first. If that fails, return minus one. Otherwise it calls check u v m write for the same range, so the buffer must also be writable.
Using one new function keeps the three callers identical. The size argument is the buffer length that the system call will write.
""", code=[blk("syscall.c", 55, 80, 77, [
    (58, "existing: checks the buffer is inside the process"),
    (66, "range check without any permission check"),
    (72, "project addition"),
    (77, "the old check still runs first"),
    (79, "then every page must be present, user and writable")])])

sec("callers", "The three callers: read, fstat and pipe", "code_walkthrough", 2, """
Three system calls write into user memory, and each changed by exactly one word: arg ptr became arg ptr w.
In sys read, the destination buffer p is checked before file read copies data into it.
In sys fstat, the struct stat that will be filled is checked. In sys pipe, the two-integer array that receives the file descriptors is checked.
Notice what did not change: sys write still uses plain arg ptr, because it only reads the user buffer. Our test confirms that writing from a protected page prints the data.
""", code=[blk("sysfile.c", 69, 115, 76, [
    (76, "destination of `read`: `argptrw` instead of `argptr`"),
    (78, "the kernel writes into `p` only after the check"),
    (82, "`sys_write` is untouched"),
    (112, "`fstat` fills a `struct stat` in user memory: checked too")])])

sec("copyout", "copyout: the backdoor through the kernel alias", "code_walkthrough", 2, """
One more door. Copy out writes through the kernel's own mapping of the physical page, which is always writable. It would silently bypass a read-only user mapping.
So after finding the kernel address, we also call check u v m write for that one page, and fail if it is not writable.
In today's xv6 the only caller is exec, which writes to a brand-new stack, so behaviour does not change. But the protection guarantee is now complete.
""", code=[blk("vm.c", 429, 455, 444, [
    (431, "only works for user pages"),
    (440, "one page at a time"),
    (441, "kernel alias of the physical page: always writable"),
    (444, "project: refuse read-only pages"),
    (449, "the actual copy happens only after both checks")])])

# ---------------------------------------------------------------- PART 3
sec("test_design", "Tests: how to detect a fault from user code", "code_walkthrough", 3, """
Part three: proving it works. In vmtest dot c, allocate pages uses sbrk to round the heap up to a page boundary and return fresh pages, so a test never protects the stack or malloc data.
The key helper is child write faults. xv6's wait returns no exit status, so we use a pipe as a marker. The child writes to the address, and only if that succeeds, writes one byte to the pipe.
The parent reads the pipe. End of file means the child died before the marker, so the write faulted. A byte means the write went through.
That is how a test distinguishes a blocked write from a successful one.
""", code=[blk("vmtest.c", 22, 68, 53, [
    (23, "fresh, page-aligned pages that nothing else uses"),
    (30, "`sbrk` grows the heap by the padding plus the pages"),
    (35, "returns 1 if the child was stopped by a fault"),
    (48, "a child, so the fault kills it and not the test"),
    (57, "the write under test"),
    (58, "marker: only reached if the write succeeded"),
    (62, "EOF means the child died before the marker"),
    (65, "count it; the runner checks this number later")])])

sec("test_basic", "The basic scenario", "code_walkthrough", 3, """
The basic test walks the story. Store a value and read it back. Protect the page. Read it again, still works. A child writing to it faults. The parent's value is unchanged.
Unprotect, write a new value, read it back. And a child writing now succeeds.
Each line is a check, and every check prints ok or FAIL, with a description, so a failure tells you exactly which behaviour broke.
""", code=[blk("vmtest.c", 70, 86, 78, [
    (75, "allocation works"),
    (77, "writable control"),
    (78, "protect"),
    (79, "reads still work"),
    (80, "writes fault"),
    (82, "restore"),
    (85, "writes work again")])])

sec("test_tlb", "The test that proves the TLB flush matters", "code_walkthrough", 3, """
This is the test I would highlight in a viva. The child writes the page first, which loads a writable translation into the T L B. Then it calls m protect and writes again immediately, with no context switch.
If m protect forgot to reload C R 3, the cached writable translation would let the second write succeed, and the marker byte would reach the parent. With the reload, the second write faults.
We checked this by deleting the reload line: the test failed with the message m protect takes effect immediately. Then we restored the line.
""", code=[blk("vmtest.c", 88, 125, 104, [
    (90, "explains the whole idea in two lines"),
    (98, "a fork gives the child its own address space"),
    (101, "first write: caches a writable translation"),
    (102, "protect, with no context switch afterwards"),
    (103, "this second write must fault"),
    (104, "marker: seeing it means the flush is missing")])])

sec("test_invalid", "Invalid arguments and atomic rejection", "code_walkthrough", 3, """
The invalid test lists every rejected request: an unaligned address, a zero length, a negative length, an overflowing length, an address that wraps, a page past the heap end, a kernel address, and the stack guard page.
It computes the guard page address from a local variable's stack page, minus one page.
Then comes atomicity: a range that starts with valid pages but ends in an invalid one must return minus one, and the earlier pages must stay exactly as they were. The suite checks that with a child write after each rejection.
This is the test that caught our merged-passes mutation.
""", code=[blk("vmtest.c", 206, 245, 214, [
    (208, "two valid pages from the heap"),
    (212, "the guard page sits just below the stack page"),
    (214, "unaligned address"),
    (216, "zero length"),
    (218, "overflowing length"),
    (220, "past the end of the process"),
    (221, "kernel address")])])

sec("runner", "The serial runner cross-checks the kernel", "code_walkthrough", 3, """
A printed PASS is not enough evidence, so the runner in smoke dot py cross-checks. It starts vmtest, waits for the prompt, and requires the success line and no FAIL line.
Then it counts the faulting children that vmtest reported and the kernel diagnostics that say trap fourteen error seven. These two numbers must be equal, and not zero.
Finally it sends an echo command and checks the shell still answers. That proves each killed child did not take the shell down.
In our runs, the number was ten.
""", code=[blk("scripts/smoke.py", 16, 33, 24, [
    (18, "start the suite in the guest shell"),
    (22, "any FAIL line, or no success line, fails the run"),
    (24, "faults that vmtest counted in user space"),
    (25, "fault diagnostics the kernel printed"),
    (26, "these two numbers must match"),
    (29, "the shell must still answer afterwards")])])

sec("demo_code", "The demo program", "code_walkthrough", 3, """
For the live demo, vm demo wraps the same idea in friendly output. Try write forks a child that writes, and the parent prints whether it succeeded or was stopped by a page fault.
The program takes an optional value and page count, so the examiner can choose them. Run it as vm demo, or vm demo seven three.
It shows five scenes: a writable control, protection with a faulting child, fork inheritance, rejected requests that change nothing, and the restored write.
""", code=[blk("vmdemo.c", 20, 40, 30, [
    (22, "who is writing, which address, which value"),
    (28, "a child, so a fault kills only the child"),
    (30, "the write under test"),
    (35, "parent waits for a marker byte"),
    (38, "prints SUCCEEDED or STOPPED by page fault")])])

sec("demo_run", "Running the demo and what to say", "overview", 3, """
To present, open the project on Pop O S or your Mac. Run the clean command, then check, and confirm three PASS lines. Then start the guest with the run command.
At the prompt, type vm demo. Walk through each numbered scene and point at the kernel line saying trap fourteen error seven. Then let the examiner pick numbers, for example vm demo seven three.
Finish with vm test and an echo command, showing the shell is alive. Exit QEMU with control A, then X.
Keep a recording of a passing run as a backup.
""", slides=dict(description="Details are in docs/DEMO.md", bullets=[
    "`./scripts/xv6 clean` then `./scripts/xv6 check`: three PASS lines",
    "`./scripts/xv6 run` starts the guest; exit with Ctrl-A, then X",
    "`vmdemo` then `vmdemo 7 3` (examiner picks the numbers)",
    "Point at `trap 14 err 7`: page fault, write, user mode",
    "`vmtest` then `echo alive` shows the shell survived"]))

sec("evidence", "The evidence we collected", "overview", 3, """
What can you honestly claim? The full check passed in three places: a Linux cloud container, GitHub Actions, and your Pop O S laptop with its own fresh clone.
Each check includes the boot test, the vm test suite with ten expected faults, and the original xv6 user tests.
We also broke the code on purpose. Removing the T L B flush made the immediate-effect test fail. Merging the two passes made the atomic-rejection tests fail. And swapping arg ptr w back to arg ptr crashes the kernel.
The macOS Mac passed only the baseline setup so far, so run check there once before relying on it.
""", slides=dict(description="Everything is recorded in docs/VALIDATION.md", bullets=[
    "Linux container, GitHub Actions and Pop!_OS: all three PASS lines",
    "10 write faults seen by `vmtest` = 10 kernel fault messages",
    "Removing `lcr3` makes the immediate-effect test fail",
    "Merging the two passes makes the atomic tests fail",
    "Mac: baseline only so far; run `check` there before using it"]))

# ---------------------------------------------------------------- PART 4
sec("mod_intro", "If the examiner says: change this code", "overview", 4, """
Part four. Your professor said you must be able to modify the code without AI. So here are three realistic requests, with worked answers. Each answer was tested in a scratch copy.
The method is always the same. Find which files control the behaviour. Make the smallest change. Rebuild with the build command. Test in the guest. Then explain why it works.
Keep a calm order: first say which function you will edit, then edit, then run.
Do the exercises yourself first. Use the video only to check your answer.
""", slides=dict(description="Method for every modification question", bullets=[
    "Name the files and function that control the behaviour",
    "Make the smallest possible change",
    "`./scripts/xv6 build`, then `./scripts/xv6 run` and test",
    "Explain why it works and what else it affects",
    "Undo practice edits with `git checkout -- .`"]))

sec("mod_getprot", "Example 1: add a getprot system call", "code_walkthrough", 4, """
Request one: add a system call get prot that reports whether a page is writable. Return one if writable, zero if read-only, minus one if invalid.
Start with the helper in vm dot c: reject addresses outside the process, walk the page table without allocating, require present and user, and return whether the writable bit is set.
Then the wrapper in sysproc dot c fetches one argument and calls the helper.
Then the wiring, exactly like m protect: a number, twenty-four, in syscall dot h, the extern and table entry in syscall dot c, a stub in usys dot S, the prototype in user dot h and the helper prototype in defs dot h.
Test it by printing get prot before and after m protect: one, then zero.
""", code=[blk("video/examples/getprot_solution.c", 1, 35, 11, [
    (5, "this file is an illustration; the real edit goes in the kernel files"),
    (13, "reject addresses outside the process"),
    (15, "same walk as in `setuvmwrite`; 0 means never allocate"),
    (17, "must be a present user page"),
    (19, "test only the write bit"),
    (28, "wrapper: fetch one argument, call the helper"),
    (33, "list every file that needs a line")])])

sec("mod_bytes", "Example 2: make len a count of bytes", "code_walkthrough", 4, """
Request two: let len be a number of bytes, rounded up to whole pages. So m protect with five thousand bytes protects two pages.
Only change protection in sysproc dot c changes. Reject zero and negative lengths first. Then convert: len minus one, divided by the page size, plus one.
Why that form? Adding four thousand ninety-five before dividing could overflow for huge lengths. Subtracting first cannot.
Then the same helper does the work. Mention the side effect: some vm test cases assume page counts, and would need updating. That shows you understand the consequences.
""", code=[blk("video/examples/bytes_solution.c", 1, 23, 12, [
    (7, "only this function changes"),
    (13, "zero and negative lengths are still invalid"),
    (15, "round up: (len - 1) / PGSIZE + 1"),
    (18, "the validating helper is unchanged"),
    (21, "5000 bytes protects two pages")])])

sec("mod_message", "Example 3: print a clearer fault message", "code_walkthrough", 4, """
Request three: when a process writes to a read-only page, print a clear message.
The place is the default case in trap dot c, the user-space branch. Check that the trap is a page fault, and that the error code masked with seven equals seven: present, write, user.
Print the process id, its name, and the faulting page, using P G R O U N D D O W N of the value that rcr two returns.
Put the new print before the existing generic message. P G R O U N D D O W N is already available because trap dot c includes mmu dot h.
Run vm demo and you will see both lines for each blocked write.
""", code=[blk("video/examples/fault_message_solution.c", 1, 18, 7, [
    (6, "new lines go before the existing message"),
    (7, "page fault, and error bits present + write + user"),
    (9, "`rcr2()` is the faulting address; round to its page"),
    (11, "existing generic message stays"),
    (17, "bits of err: 1 present, 2 write, 4 user")])])

sec("mod_more", "Other changes you might be asked", "overview", 4, """
Here are other likely requests, with the idea only. Think through each one on paper.
Kill instead of returning an error: in sys read, if the destination is protected, set the killed flag, then return minus one.
Refuse page zero: add a check for address zero to the first condition of the helper.
Limit the number of pages: add a maximum to the count check.
Return how many pages changed: count in pass two and return it instead of zero.
Protect from the current address to the end of the heap: compute the page count from the process size.
For each, say which file, which line, and what test you would run.
""", slides=dict(description="Say: which file, which line, which test", bullets=[
    "Kill instead of error: set `killed = 1` in `sys_read`",
    "Refuse page 0: add `va == 0` to the first check in the helper",
    "Cap the length: add a maximum to the count check",
    "Return the page count: count in pass 2 and return it",
    "Protect to end of heap: derive the count from `sz`"]))

sec("mod_experiments", "Break it on purpose and predict the failure", "overview", 4, """
Examiners love prediction questions. Here are four experiments, and their outcomes.
Delete the lcr three line: the immediate-effect test fails.
Merge the update into pass one: a rejected range leaves a program page read-only, and the test program gets killed.
Remove the user-bit check from pass one: the stack guard page test fails, because the guard page is accepted.
Change arg ptr w back to arg ptr in sys read: the kernel panics, a trap in kernel mode.
Predict each result before you run it, then restore with git checkout.
""", slides=dict(description="Run `./scripts/xv6 smoke` after each", bullets=[
    "Delete `lcr3(...)`: `mprotect takes effect immediately` fails",
    "Merge the passes: a rejected range leaves a page read-only",
    "Drop the `PTE_U` check: the guard-page checks fail",
    "`argptrw` back to `argptr`: kernel `panic: trap`",
    "Restore with `git checkout -- vm.c sysfile.c`"]))

sec("qa1", "Viva questions, round 1: design", "overview", 4, """
Rapid fire. Answer each aloud before listening.
Why must the address be page aligned? Because permissions apply to whole pages, so a mid-page address has no meaning. And length is in pages for the same reason.
What does and-equals not W do? It clears only the write bit and leaves every other bit alone.
Why two passes? So a failed call changes nothing.
Why walk page directory with allocate zero? Validation must not create page tables, and a bad address must not allocate memory.
What happens without the C R 3 reload? The processor may keep a cached writable translation, so a write could still succeed.
Why V two P? C R 3 holds a physical address.
""", slides=dict(description="Pause and answer before you listen", bullets=[
    "Why page-aligned address and length in pages?",
    "What does `*pte &= ~PTE_W` do to other bits?",
    "Why two passes? Why `alloc = 0`?",
    "What if `lcr3` is missing?",
    "Why `V2P(pgdir)` inside `lcr3`?"]))

sec("qa2", "Viva questions, round 2: faults and fork", "overview", 4, """
Why does the child die but not the parent? The fault happens in the child's user mode, so the trap handler marks only that process killed.
Decode trap fourteen error seven. Page fault; present, write, user.
What would error six mean? A user write to a page that is not present.
Why does fork keep protection? Copy u v m copies the flag bits into the child's new page. The two pages are independent copies.
Is the stack guard page protectable? No. Its user bit is cleared by exec, so our validation rejects it.
Can a process protect its own code at address zero? Yes, it is a user page. The project does not change null pointer behaviour.
""", slides=dict(description="Pause and answer before you listen", bullets=[
    "Why does only the child die?",
    "Decode `trap 14 err 7`; what would `err 6` mean?",
    "Why does `fork()` keep protection? Shared or copied pages?",
    "Why is the guard page rejected? Which bit?",
    "Can a process protect its code at address 0?"]))

sec("qa3", "Viva questions, round 3: kernel buffers and limits", "overview", 4, """
Why did read into a protected buffer panic the kernel? C R 0 W P makes kernel writes obey read-only pages, and a kernel-mode fault calls panic.
How is it fixed? The output buffers of read, fstat and pipe are checked first, and the call returns minus one.
Why is write from a protected buffer still allowed? The kernel only reads it.
What happens to protected pages after exec, or after sbrk shrinks the heap? Exec builds a fresh address space. Shrinking frees the pages normally. New pages are writable.
Is the check-then-write safe on a multi-processor kernel with threads? No, you would need locking or fault handling. On one processor with no threads, nothing can change the page between check and write.
Why use a pipe in the tests? Because wait returns no exit status in xv6.
""", slides=dict(description="Pause and answer before you listen", bullets=[
    "Why did `read()` into a protected buffer panic the kernel?",
    "How is it fixed? Why is `write()` still allowed?",
    "What happens after `exec()` or `sbrk(-n)`?",
    "Is check-then-write safe with several CPUs?",
    "Why does the test use a pipe instead of `wait()`?"]))

sec("summary", "Summary and how to own this", "summary", 4, """
To close. The project in one sentence: a process can switch the write bit of its own pages off and on, safely, the hardware enforces it, and the kernel cannot crash or bypass it.
Your remaining work: do the three exercises in docs slash viva dot m d without any assistant, answer the question bank aloud, and rehearse the demo on the machine you will present on.
The deadline is the end semester exam plus three days.
When you can rewrite set u v m write from memory and explain each line, you own it. Good luck.
""", slides=dict(description="docs/VIVA.md and docs/DEMO.md have everything", bullets=[
    "One sentence: toggle `PTE_W` safely; kernel cannot bypass it",
    "Rewrite `setuvmwrite` from memory",
    "Do VIVA.md exercises 1-3 with no AI help",
    "Rehearse `DEMO.md` on the real presentation machine",
    "Deadline: end-sem exam + 3 days"]))


# ---------------------------------------------------------------- build
def tts(text):
    """Make the narration friendlier for text-to-speech."""
    t = " ".join(text.split())
    for a, b in [("xv6", "x v 6"), ("munprotect", "m unprotect"), ("mprotect", "m protect")]:
        t = t.replace(a, b)
    return t


def validate():
    errs = []
    for s in S:
        for b in s["code"]:
            p = ROOT / b["filePath"]
            if not p.is_file():
                errs.append(f"{s['id']}: missing file {b['filePath']}")
                continue
            n = len(p.read_text().split("\n"))
            if not (1 <= b["startLine"] <= b["endLine"] <= n):
                errs.append(f"{s['id']}: lines {b['startLine']}-{b['endLine']} outside {b['filePath']} ({n})")
            for h in b["commentHints"]:
                if not (b["startLine"] <= h["insertAfterLine"] <= b["endLine"]):
                    errs.append(f"{s['id']}: hint line {h['insertAfterLine']} outside block")
        if s["slides"]:
            for bl in s["slides"]["bullets"]:
                if len(bl) > 80:
                    errs.append(f"{s['id']}: bullet over 80 chars: {bl}")
    if errs:
        print("\n".join(errs))
        sys.exit(1)


def sections_json(items):
    plan = dict(title="Read-only page protection in xv6: viva preparation", sections=[
        dict(id=s["id"], title=s["title"], type=s["type"], targetDurationSec=60,
             filePaths=sorted({b["filePath"] for b in s["code"]}), keyPoints=[s["title"]])
        for s in items])
    scripts = []
    for s in items:
        words = len(tts(s["narration"]).split())
        d = dict(sectionId=s["id"], narration=tts(s["narration"]), codeBlocks=s["code"],
                 estimatedDurationSec=round(words / 2.6))
        if s["slides"]:
            d["slides"] = s["slides"]
        if s["mermaid"]:
            d["mermaidDiagram"] = s["mermaid"]
        scripts.append(d)
    return plan, scripts


def main():
    validate()
    plan, scripts = sections_json(S)
    (OUT / "plan.json").write_text(json.dumps(plan, indent=1))
    (OUT / "scripts.json").write_text(json.dumps(scripts, indent=1))
    parts = OUT / "parts"
    parts.mkdir(exist_ok=True)
    total = 0
    for n in sorted({s["part"] for s in S}):
        items = [s for s in S if s["part"] == n]
        p, sc = sections_json(items)
        p["title"] = f"Read-only page protection in xv6: viva part {n}"
        (parts / f"plan_{n}.json").write_text(json.dumps(p, indent=1))
        (parts / f"scripts_{n}.json").write_text(json.dumps(sc, indent=1))
        w = sum(len(tts(s['narration']).split()) for s in items)
        total += w
        print(f"part {n}: {len(items)} sections, {w} words, about {w / 2.6 / 60:.1f} min")
    print(f"total: {len(S)} sections, {total} words, about {total / 2.6 / 60:.1f} min of narration")
    md = ["# Narration script (also what the voice reads)\n",
          "Re-record this in your own voice if you like. Line numbers shown in the video come from",
          "the committed source files; run `python3 video/build_inputs.py` to re-check them.\n"]
    part_names = {1: "Part 1: the problem and the background", 2: "Part 2: our solution, block by block",
                  3: "Part 3: tests, demo and evidence", 4: "Part 4: modify the code, then viva questions"}
    cur = 0
    for s in S:
        if s["part"] != cur:
            cur = s["part"]
            md.append(f"\n## {part_names[cur]}\n")
        md.append(f"### {s['title']}\n")
        if s["code"]:
            md.append("Shows: " + ", ".join(f"`{b['filePath']}` lines {b['startLine']}-{b['endLine']}" for b in s["code"]) + "\n")
        md.append(s["narration"] + "\n")
    (OUT / "narration.md").write_text("\n".join(md))


if __name__ == "__main__":
    main()
