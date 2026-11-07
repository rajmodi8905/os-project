# os-project working instructions

- Read the parent OS `context.md` and the shared user context before local work.
  Keep private continuation notes in ignored `context.md`; never publish local
  account notes, unrelated coursework, lecture PDFs, or email drafts.
- Scope: read-only page protection in x86 xv6, following `plan.md` and the
  OSTEP specification. Null-page protection is outside the selected scope.
- Current authorization is basic setup. Do not silently implement later
  milestones while the user is reviewing or studying this checkpoint.
- Preserve upstream history, LICENSE and README. Record the pinned base and
  separate existing xv6 code from project contributions and future plans.
- Run only inside QEMU using project image files, as a normal user. Never write
  host disks, replace the host kernel, or change boot configuration.
- Use meaningful checks appropriate to each change; record actual commands and
  outcomes. A feature is not implemented just because documentation proposes it.
- Keep a short current checkpoint and dated session history so another agent
  can resume. Public validation belongs in docs; private local handover stays
  ignored. Do not include AI coauthor/author identity in Git metadata. Keep
  factual assistance disclosure in project documentation.
