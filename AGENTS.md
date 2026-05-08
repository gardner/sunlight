Please write `PROGRESS.md` with a "Next Steps" section when you finish a slice
of work. Ensure there is only one "Next Steps" section.

Run wrangler using `pnpm dlx wrangler@latest`

Please make descriptive commits at reasonable intervals.

# Git Hooks

- Ensure the shared git hooks are installed before committing:
  `git config core.hooksPath .githooks`.
- Never use `--no-verify` unless the user explicitly confirms it first.


## IMPORTANT

- Use TDD "Red, green, refactor" where possible.
- Optimize for code readability and long-term maintenance.
- Write simple yet powerful code.
- Keep things elegant.
