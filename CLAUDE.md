# CLAUDE.md

<!-- antislop:start -->
## antislop

This project uses antislop (https://github.com/miqdadbadjuber/anti-slop, v3.2.32), a filter against generic AI slop in copy, code and UI. It is not a style guide: the film's look and the narration voice stay ours. In Storyloom it matters most for narration and scene scripts (copywriting), code comments, and the core rules; the UI skills apply only to any page or overlay we build.

For copy, code comments, UI, people, or mobile layout work, read `antislop.md` (core, at the repo root) and then the skill for the task (use these paths even if a same-named global skill exists):
- Core filter, always on: `.claude/skills/antislop/SKILL.md`
- Copy & text (narration, scripts, titles, descriptions): `.claude/skills/antislop-copywriting/SKILL.md`
- Code comments: `.claude/skills/antislop-code/SKILL.md`
- UI / visual: `.claude/skills/antislop-ui/SKILL.md`
- People: `.claude/skills/antislop-human/SKILL.md`
- Mobile / responsive: `.claude/skills/antislop-layoutmobile/SKILL.md`

Before starting, follow the core's "Two Usage Modes" section in strict order: explicit session instruction first, then global preference, then ask. A session instruction always wins. In this project, when no session instruction and no saved global preference exist (for example in a cloud session), use `during` and do not ask: the owner wants antislop applied while working. For a resolved mode, say `antislop active: <mode> (session override).` or `antislop active: <mode> (global preference).` once before presenting findings or making edits.
Only an explicit choice of antislop during or after selects a session mode. A request to review, audit, or avoid file edits does not select a mode.
For read-only tasks, put the active-mode notice only at the start of the final answer, never in progress messages. For editing tasks, announce before the first edit and omit it from the final answer.
To update antislop later: `npx antislop-ai --update` from the repo root, and copy the release's `antislop.md` over the root copy.
<!-- antislop:end -->
