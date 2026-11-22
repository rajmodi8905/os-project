# Narration script and chapter times

Spoken with a local offline voice; re-record in your own voice if you prefer.


## 0:00  Problem

- This video prepares you for the viva on read-only page protection in xv6.
- We go from the problem, through the background and our solution, to the code block by block, and then the tests and a live demo.
- At the end you get three example changes an examiner might ask for, and rapid-fire viva questions.
- Pause often, and try to rewrite each function yourself. You must own every line.
- The task, from the OSTEP virtual memory project: add two system calls to xv6.
- mprotect makes a range of pages read-only. munprotect makes them writable again.
- The address must be page aligned, and the length counts pages, not bytes.
- Reads must still work, but a write to a protected page must kill that process, and only that process.
- A failed call must change nothing. The change must be immediate. And fork must keep the protection.

## 0:52  Background

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

## 2:30  Solution

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

## 6:07  Tests & demo

- To test this from user code, vmtest uses a child process, because a faulting write kills only its own process.
- The child writes, and only if the write succeeds does it write a marker byte into a pipe.
- The parent reads the pipe. End of file means the child died before the marker, so the write faulted.
- One test deserves special mention. The child writes the page first, caching a writable translation, then calls mprotect and writes again.
- Without the CR3 reload, that second write would succeed. We proved it by deleting the line: this test failed. Then we restored it.
- Now the live demo. We run vmdemo with seven and three: three pages, value seven. First a writable control.
- After mprotect returns zero, reading still works.
- A child writes to the last page and dies. The kernel line says trap fourteen error seven, a page fault from a user write. The parent is alive and its value is unchanged.
- A fresh child inherits the read-only page, so it faults too.
- Invalid requests return minus one, and the rejected munprotect changed nothing: the next child still faults.
- After munprotect, writes work again, for the parent and for a child.
- The full check prints three pass lines. It passed in a Linux container, in GitHub Actions, and on your Pop O S laptop. The ten faults vmtest counted match ten kernel messages.
- We also broke the code on purpose. Deleting the CR3 reload, or merging the two passes, made tests fail. The Mac has passed only the baseline so far, so run check there first.

## 7:42  Modify it

- Part four. The examiner may ask you to change the code. The method is always the same.
- Name the files and the function. Make the smallest change. Rebuild and test. Then explain why it works.
- Example one: add a getprot call that reports whether a page is writable. The helper walks the page table without allocating, requires a present user page, and returns the writable bit.
- The wrapper fetches one argument and calls the helper. Then the wiring is exactly like mprotect: a number, an extern and table entry, a stub, and two prototypes.
- Example two: make the length a count of bytes. Only changeprotection changes. Reject non-positive lengths, then convert to pages, rounding up.
- Subtract one before dividing, so we never add four thousand ninety-five and overflow. Mention that some vmtest cases assume page counts.
- Example three: print a clearer message on a write fault. In trap.c, in the user branch, check for a page fault with the error bits present, write and user.
- Print the faulting page with PGROUNDDOWN of rcr2, before the existing message. PGROUNDDOWN is already included through mmu.h.
- Other likely requests: kill the caller instead of returning an error, refuse page zero, cap the length, or return how many pages changed. For each, name the file, the line and the test.
- Predict before you run: deleting lcr3 fails the immediate-effect test. Merging the passes leaves a page read-only after a rejection. Dropping the user check accepts the guard page. And argptr in sys read panics the kernel.

## 9:18  Viva Q&A

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
- In one sentence: a process can switch the write bit of its own pages off and on, safely. The hardware enforces it, and the kernel can neither crash nor bypass it.
- Now do the three exercises in VIVA.md without any help, answer the questions aloud, and rehearse the demo on your presentation machine. When you can rewrite setuvmwrite from memory and explain every line, you own it. Good luck.
