# Narration script and chapter times (full 30-minute version)

Spoken with a local offline voice; re-record in your own voice if you prefer.


## 0:00  Problem

- This video prepares you for the viva on read-only page protection in xv6.
- We go from the problem, through the background and our solution, to the code block by block, and then the tests and a live demo.
- At the end you get three example changes an examiner might ask for, and rapid-fire viva questions.
- This longer version also walks through every file we wrote, all the tests, the demo program and the runner, and ends with a step by step guide to proving it live in front of the examiner.
- Pause often, and try to rewrite each function yourself. You must own every line.
- The task, from the OSTEP virtual memory project: add two system calls to xv6.
- mprotect makes a range of pages read-only. munprotect makes them writable again.
- The address must be page aligned, and the length counts pages, not bytes.
- Reads must still work, but a write to a protected page must kill that process, and only that process.
- A failed call must change nothing. The change must be immediate. And fork must keep the protection.

## 1:05  Background

- Background. A page is four thousand ninety-six bytes, and a thirty-two bit address splits into three fields.
- The top ten bits index the page directory.
- The next ten bits index a page table.
- The low twelve bits are the offset inside the page.
- The register CR3 points at the directory, and the entry that names the physical page is the PTE.
- Page number is the address divided by 4096, and the offset is the remainder.
- The PTE stores the physical page and permission bits.
- PTE_P means present, PTE_W means writable, and PTE_U means user accessible.
- To clear the writable bit we AND with the inverse mask. To set it we OR. To test it we AND and compare.
- Two hardware facts matter. First, the TLB caches translations together with their permissions.
- If we clear the writable bit in the PTE, the cached copy may still say writable.
- Reloading CR3 flushes the cache, so the next write sees the real permission. That is why our code reloads CR3.
- Second, entry.S sets CR0 WP, so even the kernel obeys read-only pages. Remember this; it matters later.
- When user code writes a read-only page, the processor raises trap fourteen, a page fault, and this existing handler runs.
- If the fault came from user mode, only that process is marked killed. The parent carries on.
- Decode the message: error seven is one for present, two for write, and four for user mode. That is our protection firing.
- A fault from kernel mode is different. The branch above calls panic, and the whole machine stops.

## 2:45  Solution

- Our solution in one picture. The program calls mprotect.
- A tiny assembly stub traps into the kernel, and the dispatch table finds sys mprotect.
- That calls one shared helper, setuvmwrite, in vm.c.
- The helper validates every page first, then changes only the writable bit, then reloads CR3.
- A second part makes read, fstat and pipe check their output buffers, so the kernel can never fault on protected memory.
- On the user side we copied the pattern of uptime. Each call is one line in usys.S that loads the call number and traps.
- In syscall.h, our calls are numbered twenty-two and twenty-three.
- In syscall.c, an extern declaration and a table entry connect each number to its handler.
- In sysproc.c, changeprotection fetches the address and the length with argint, and passes them to setuvmwrite.
- mprotect passes writable equals zero, and munprotect passes one. One helper, two thin wrappers.
- Now the heart of the project, setuvmwrite in vm.c.
- The first check rejects an unaligned address, a count of zero or less, and a start outside the process.
- The second check compares the count with how many whole pages fit. We never multiply first, because the product could overflow.
- Only then is the end address safe to compute.
- Pass one walks every page without allocating. Each must be present and a user page, so the stack guard page is rejected here.
- Pass two runs only when pass one succeeded, so it cannot fail halfway. It sets or clears only the writable bit.
- Finally, reloading CR3 flushes the TLB, so the change takes effect immediately.
- Why compare counts? Take a start of hex one thousand and a count of hex one hundred thousand.
- Count times 4096 is two to the thirty-second, which wraps around to zero in thirty-two bit arithmetic.
- A naive check would see an end of 0x1000 and accept it. Ours compares counts, and correctly rejects it.
- Why two passes? The specification says a failed call must change nothing.
- If we changed pages while validating, an invalid third page would leave the first two already modified.
- With two passes, validation fails first, so nothing is touched. We tested this by merging the passes and watching the test fail.
- Fork needed no change. copyuvm reads each page's flags, allocates a new physical page, copies the contents, and maps it with the same flags.
- So a read-only page stays read-only in the child, yet the two are separate copies. A change in one never affects the other.
- Now the bug we found by testing. What if the kernel itself writes into a protected page, for example in read?
- Because CR0 WP is set, that is a page fault in kernel mode, and the trap handler panics. We reproduced exactly this crash.
- The rule: if the kernel will write into a user buffer, check that every page is writable first, and return minus one if not.
- But write only reads the buffer, so a protected page is perfectly fine there.
- checkuvmwrite loops over every page the buffer touches, so buffers that span several pages are covered.
- Each page needs present, user and writable all set. Anything less returns minus one.
- argptrw calls the old bounds check, then this check.
- In sys read, argptr became argptrw. sys fstat and sys pipe changed the same way, but sys write is untouched.
- copyout writes through the kernel's own always-writable mapping, so it got the same check.
- Now the rest of the code we wrote, file by file. In user.h, two prototypes let user programs call mprotect and munprotect.
- defs.h declares setuvmwrite and checkuvmwrite, and argptrw, so sysproc.c, syscall.c and sysfile.c can call them.
- The Makefile lists vmtest and vmdemo as user programs, so they are compiled and copied into the guest's disk image. Forget this, and the guest says: not found.
- Two existing pieces you must know. walkpgdir finds the directory entry, then the page table, and returns a pointer to the PTE. With alloc zero it gives up instead of building a page table, which both our helpers rely on.
- And exec allocates two pages and clears the user bit on the lower one. That is the guard page, and our validation rejects any page without the user bit.
- A good test of ownership: close the video and rewrite setuvmwrite from these five steps. Reject bad arguments. Compare counts. Validate every page. Change only the write bit. Then reload CR3.

## 7:33  Tests & demo

- To test this from user code, vmtest uses a child process, because a faulting write kills only its own process.
- The child writes, and only if the write succeeds does it write a marker byte into a pipe.
- The parent reads the pipe. End of file means the child died before the marker, so the write faulted.
- One test deserves special mention. The child writes the page first, caching a writable translation, then calls mprotect and writes again.
- Without the CR3 reload, that second write would succeed. We proved it by deleting the line: this test failed. Then we restored it.

## 2:45  Solution

- A very likely question: walk me from mprotect in C to the page table entry, naming every file. In the program, mprotect is declared in user.h.
- The stub in usys.S puts twenty-two in EAX and executes int T underscore SYSCALL.
- The trap handler calls syscall, which looks up slot twenty-two in the table in syscall.c.
- That slot is sys mprotect in sysproc.c, which calls change protection with writable equals zero.
- Which calls setuvmwrite in vm.c: validate, clear the write bit, and reload CR3.
- The result goes back in EAX, and that is what the program sees.

## 7:33  Tests & demo

- Now vmtest.c from top to bottom. check prints ok or FAIL and counts failures. The faults counter counts children stopped by a fault, and the runner compares it with the kernel.
- allocpages grows the heap with sbrk, rounds up to a page boundary, and returns whole fresh pages, so a test never protects the stack or malloc's own data.
- The repeated test calls mprotect twice, then munprotect twice. Doing the same thing again must be harmless.
- The multiple test protects the middle three of five pages. Every page in the range must fault, while the page before and the page after stay writable.
- The forking test first protects a page. A freshly forked child must fault when it writes, so protection is inherited.
- Then a child unprotects and writes its own copy, and reports back through a pipe. The parent checks that its copy is unchanged and still protected.
- And the reverse: a child that protects its copy must not protect the parent's. So the two are independent in both directions.
- The invalid test lists every bad request: unaligned, zero, negative, overflowing, wrapping, past the heap, a kernel address, and the guard page. Each must return minus one.
- Then the atomicity cases. A range that runs into an invalid page must fail, and the earlier pages must stay exactly as they were. A child write checks it after every rejection.
- The kernel buffer tests protect a page and ask read to fill it. Read must return minus one and leave the page alone. Before our fix, this exact test panicked the kernel.
- A buffer that starts in a writable page and runs into a protected one is also rejected, and neither page changes. And write from a protected page still works.
- The fstat and pipe destinations are rejected in the same way when the page is protected.
- main runs the groups in order, prints how many faults it saw, and prints ALL PASSED only if no check failed. That printed count is what the runner compares with the kernel messages.
- vmdemo is the friendly version of the same idea. trywrite forks a child that writes, and the parent prints whether the write succeeded or was stopped by a page fault.
- main reads an optional value and page count, so the examiner can choose them, from one to sixteen pages.
- Scene one is the writable control. Scene two protects the pages, shows a protected read still works, and a child write must be stopped.
- Scenes three to five: fork inheritance, invalid requests that change nothing, and munprotect followed by a successful write.
- Now the live demo. We run vmdemo with seven and three: three pages, value seven. First a writable control.
- After mprotect returns zero, reading still works.
- A child writes to the last page and dies. The kernel line says trap fourteen error seven, a page fault from a user write. The parent is alive and its value is unchanged.
- A fresh child inherits the read-only page, so it faults too.
- Invalid requests return minus one, and the rejected munprotect changed nothing: the next child still faults.
- After munprotect, writes work again, for the parent and for a child.
- The full check prints three pass lines. It passed in a Linux container, in GitHub Actions, and on your Pop O S laptop. The ten faults vmtest counted match ten kernel messages.
- We also broke the code on purpose. Deleting the CR3 reload, or merging the two passes, made tests fail. The Mac has passed only the baseline so far, so run check there first.
- The runner, scripts slash smoke dot py, starts vmtest and fails on any FAIL line. It also requires vmtest's fault count to equal the kernel's trap fourteen messages.
- Around that, it checks boot, an echo command, forktest, our vmtest, and for check, the original xv6 user tests.
- scripts slash x v 6 is the command you type: build, run, smoke, check, and clean. Check runs the whole sequence including the original tests.
- And GitHub Actions runs the same check on every push, so the evidence is repeatable and not just on your laptop.

## 13:09  Live proof

- Now the part most people forget: how to prove it live. The day before, charge the laptop and test it on the presentation machine. Pull the latest code, run clean and then check, and expect three pass lines. Close other QEMU windows, and keep a recording as a backup.
- Start by showing the work. git log shows each checkpoint as a commit, from the syscalls to the tests, the demo and the documentation.
- Then git diff stat against the xv6 baseline. Only these files differ from original xv6. The kernel part is vm.c, sysproc.c, syscall.c, sysfile.c, and a few wiring lines. Everything else is untouched.
- Now run clean and check. It takes about forty seconds. While it runs, explain the three pass lines: the boot test, our vm test suite with ten expected faults, and the original xv6 tests.
- Then run the project. The run command boots xv6 in QEMU. When you see the dollar prompt, you are inside the guest. Exit later with control A, then X.
- Type ls. Our two programs, vmtest and vmdemo, sit next to the original xv6 programs. That is how you know the Makefile change worked.
- Now the demo. Ask the examiner for a value and a page count. Here we use one thousand and four pages. Scene one shows the writable control with their numbers.
- Point at two things. The kernel line, trap fourteen error seven, and the word stopped. Then say: the parent is still alive and its value did not change.
- Finish with the last scene: after munprotect, writes work again, and the shell is still running. Then run vm test and an echo command to show the whole system survived.
- If you want a stronger proof, break it live. Delete the C R 3 reload line, run the smoke test, and watch the immediate effect test fail. Then restore the file with git checkout. This shows the tests really detect the bug.
- If the examiner asks for a change, make it, rebuild, run, and show it. This is real output with all three example changes applied to a scratch copy. getprot says one before. Then mprotect with five thousand bytes returns zero.
- Both pages now read as protected, because five thousand bytes rounds up to two pages. A kernel address gives minus one.
- Unprotecting one byte restores only the first page.
- And a write to a read-only page now prints our clearer message before the usual trap line, while the parent keeps running.
- For any live change: edit the one function that controls it, rebuild, run, show the result, and explain why it works. Restore with git checkout. Never edit something you cannot explain.
- If something goes wrong: a hang means another QEMU is running, so close it and clean. Not found means an old disk image, so clean and run again. A slow Mac is normal. Control A then X leaves QEMU. And if all fails, play your backup recording.
- Finally, your opening. Say: I added two system calls that clear or set one bit on a range of pages. The hardware enforces it. I validate first, change second, then flush the TLB, and I made the kernel's own writes respect it. Let me show it, and then I can walk through any block.

## 16:29  Modify it

- Part four. The examiner may ask you to change the code. The method is always the same.
- Name the files and the function. Make the smallest change. Rebuild and test. Then explain why it works.
- Example one: add a getprot call that reports whether a page is writable. The helper walks the page table without allocating, requires a present user page, and returns the writable bit.
- The wrapper fetches one argument and calls the helper. Then the wiring is exactly like mprotect: a number, an extern and table entry, a stub, and two prototypes.
- Example two: make the length a count of bytes. Only changeprotection changes. Reject non-positive lengths, then convert to pages, rounding up.
- Subtract one before dividing, so we never add four thousand ninety-five and overflow. Mention that some vmtest cases assume page counts.
- Example three: print a clearer message on a write fault. In trap.c, in the user branch, check for a page fault with the error bits present, write and user.
- Print the faulting page with PGROUNDDOWN of rcr2, before the existing message. PGROUNDDOWN is already included through mmu.h.
- Example four: refuse page zero and allow at most sixteen pages per call. It is one condition in the first check of the shared helper.
- Because mprotect and munprotect share the helper, both rules apply to both calls. Only a range that starts at zero can include page zero.
- We tested it in a scratch copy. Page zero is refused, sixteen pages work, seventeen returns minus one, and munprotect obeys the same cap.
- Other likely requests: kill the caller instead of returning an error, refuse page zero, cap the length, or return how many pages changed. For each, name the file, the line and the test.
- Predict before you run: deleting lcr3 fails the immediate-effect test. Merging the passes leaves a page read-only after a rejection. Dropping the user check accepts the guard page. And argptr in sys read panics the kernel.

## 18:36  Viva Q&A

- Now rapid-fire viva questions. Answer each one aloud before you listen to the answer.
- Why must the address be page-aligned, and the length in pages?
- Permissions apply to whole pages, so a mid-page address has no meaning.
- Why two passes?
- So a failed call changes nothing. Pass two cannot fail halfway.
- What happens without the CR3 reload?
- The TLB may keep a writable translation, so a write could still succeed.
- Why does only the child die, and what is trap 14 err 7?
- The fault is in the child's user mode, so only it is killed. Page fault: present, write, user.
- Why did read into a protected buffer panic, and why is write still allowed?
- CR0 WP makes kernel writes obey read-only pages, and a kernel fault panics. We check output buffers. Write only reads.
- Why does fork keep protection?
- copyuvm copies the flag bits into the child's own separate page.
- Can a process protect its own code at address 0?
- Yes, code is a user page. Our project does not change null-pointer behaviour.
- What happens to protected pages after exec, or after sbrk shrinks the heap?
- Exec builds a fresh address space. Shrinking frees the pages normally. New heap pages are writable.
- Is check-then-write safe with several CPUs and threads?
- No. You would need locking or fault handling. Here there is one CPU and no threads, so nothing changes between the check and the write.
- Why do the tests use a pipe instead of wait?
- xv6's wait returns no exit status, so a marker byte through a pipe shows whether the write succeeded.
- What would error code 6 mean instead of 7?
- A user write to a page that is not present.
- What do mprotect and munprotect return?
- Zero on success and minus one on an invalid request, and an invalid request changes nothing.
- In one sentence: a process can switch the write bit of its own pages off and on, safely. The hardware enforces it, and the kernel can neither crash nor bypass it.
- Now do the three exercises in VIVA.md without any help, answer the questions aloud, and rehearse the demo on your presentation machine. When you can rewrite setuvmwrite from memory and explain every line, you own it. Good luck.
