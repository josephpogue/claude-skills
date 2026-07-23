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
folder under `~/.agents/skills/` and symlinks it into `~/.claude/skills/`. That
is a complete install for pure-prompt skills. A skill that needs setup beyond
copying its folder ships a `setup.sh` inside its own folder that you run once
after install (see that skill's README).

## Skills

| Skill | What it does | Setup |
|-------|--------------|-------|
| [`case-interviewer`](./skills/case-interviewer/README.md) | Run a live consulting case interview in your browser, you as the candidate and Claude as the interviewer: it builds or ingests a case, reveals exhibits on cue, and scores a debrief against a real rubric. | None. Self-contained (Python stdlib + the `claude` CLI). |
| [`frontier-go-wild`](./skills/frontier-go-wild/README.md) | Find Frontier Go Wild seat availability day-by-day for an origin and many destinations, ranked by fee. | Run `bash setup.sh` in the skill folder once on a new machine (browser toolkit only, no login or credentials). |

## Layout

```
skills/<skill-name>/SKILL.md    the skills (skills.sh reads these)
.claude-plugin/plugin.json      the ship manifest (which skills are public)
docs/<skill-name>.md            per-skill quickstart pages
scripts/link-skills.sh          dev: symlink skills into ~/.claude/skills
```

## Local development

To work on these skills against your live agent, symlink them into your skill
directory (a `git pull` then keeps your installed copies current):

```bash
bash scripts/link-skills.sh
```

## License

MIT. See [LICENSE](./LICENSE).
