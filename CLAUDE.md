# claude-skills — repo conventions

Skills live flat, one folder per skill: `skills/<skill-name>/SKILL.md`. This
mirrors how they land at runtime (`~/.claude/skills/<skill-name>`), so the repo
layout matches the installed layout. No category buckets — keep it flat.

## Rules

- Every shipped skill has an entry in the top-level `README.md` **and** in
  `.claude-plugin/plugin.json`. Drafts that should not be installable stay out
  of both.
- Each skill's `SKILL.md` frontmatter is either **user-invoked**
  (`disable-model-invocation: true`, reachable only by the human typing its
  name) or **model-invoked** (omit that key; write a trigger-rich description).
- A skill that needs setup beyond copying its folder (a toolchain, credentials,
  per-repo config) is self-bootstrapping: it ships its installer **inside its own
  folder** as `setup.sh`, and its `SKILL.md` carries a `## Setup` section telling
  the user to run it once on a new machine. One folder per skill — no separate
  `setup-<skill>` companion. See `frontier-go-wild`.
- Never commit secrets. Credentials live in the user's local
  `~/.config/credentials/store.toml`, written by the skill's `setup.sh` at
  install time, never in this repo.
- Skills reach each other by prose invocation ("run `bash setup.sh` in the skill
  folder"), not by cross-folder file links.

## Install path

Skills install via the skills.sh standard: `npx skills add josephpogue/claude-skills --skill=<name>`.
For local development, `bash scripts/link-skills.sh` symlinks every skill into
`~/.claude/skills`.
