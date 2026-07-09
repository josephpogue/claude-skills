# claude-skills

Joseph Pogue's [Claude Code](https://claude.com/claude-code) skills, in one
installable repo. Point your agent at this repo and pull in a skill by name.

## Install a skill

```bash
npx skills add josephpogue/claude-skills --skill=frontier-go-wild
```

```bash
npx skills update frontier-go-wild
```

`npx skills` (the [skills.sh](https://skills.sh) standard) installs the skill
folder under `~/.agents/skills/` and symlinks it into `~/.claude/skills/`.
That is a complete install for pure-prompt skills. Skills that drive a browser or need credentials ship a companion
`setup-*` skill you run once after install (see below).

## Skills

### Tools

| Skill | What it does | Setup |
|-------|--------------|-------|
| [`frontier-go-wild`](./skills/tools/frontier-go-wild/README.md) | Find Frontier Go Wild seat availability day-by-day for an origin and many destinations, ranked by fee. | Run `bash setup.sh` in the skill folder once on a new machine (browser toolkit only — no login or credentials). |

## Layout

```
skills/<bucket>/<skill-name>/SKILL.md   the skills (skills.sh reads these)
.claude-plugin/plugin.json              the ship manifest (which skills are public)
docs/<bucket>/<skill-name>.md           per-skill quickstart pages
scripts/link-skills.sh                  dev: symlink skills into ~/.claude/skills
```

## Local development

To work on these skills against your live agent, symlink them into your skill
directory (a `git pull` then keeps your installed copies current):

```bash
bash scripts/link-skills.sh
```

## License

MIT. See [LICENSE](./LICENSE).
