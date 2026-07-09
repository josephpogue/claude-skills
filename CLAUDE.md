# claude-skills — repo conventions

Skills live under `skills/<bucket>/<skill-name>/SKILL.md`. Buckets so far:

- `tools/` — skills that do a concrete job, often driving real systems.

Add more buckets (`productivity/`, `personal/`, `in-progress/`) as skills arrive.

## Rules

- Every shipped skill has an entry in the top-level `README.md` **and** in
  `.claude-plugin/plugin.json`. Drafts that should not be installable go in an
  `in-progress/` bucket and stay out of both.
- Each skill's `SKILL.md` frontmatter is either **user-invoked**
  (`disable-model-invocation: true`, reachable only by the human typing its
  name) or **model-invoked** (omit that key; write a trigger-rich description).
- A skill that needs setup beyond copying its folder (a toolchain, credentials,
  per-repo config) ships a companion **`setup-<skill>`** user-invoked skill that
  bootstraps it. The skill folder carries instructions; the setup skill carries
  the install. See `setup-frontier-go-wild`.
- Never commit secrets. Credentials live in the user's local
  `~/.config/credentials/store.toml`, written by the setup skill at install
  time, never in this repo.
- Skills reach each other by prose invocation ("run `/setup-frontier-go-wild`"),
  not by cross-folder file links.

## Install path

Skills install via the skills.sh standard: `npx skills add josephpogue/claude-skills --skill=<name>`.
For local development, `bash scripts/link-skills.sh` symlinks every skill into
`~/.claude/skills`.
