# agent-skills

A curated collection of AI agent skills for software development workflows.

## What is this?

agent-skills provides reusable skills that power AI-agent-driven development workflows. While primarily designed for Claude Code, the skills follow the [Agent Skills specification](https://agentskills.io/specification) for cross-platform compatibility.

### Key Skills

- **autodev-init** — Interactively initialize a repository's AI agent development environment. Sets up steering documents (product/tech/market/plan/work), installs workflow skills, and generates project structure documentation.
- **merge-dependabot-bump-pr** — Review and merge Dependabot version bump PRs with 4-point safety checks (release age, critical bugs, breaking changes, source diff).

## Quick Start

Install via Claude Code plugin marketplace:

```bash
/plugin marketplace add mizunashi-mana/agent-skills
/plugin install autodev
/plugin install merge-dependabot-bump-pr
```

Available plugins:

- `autodev` — AI agent development environment scaffolding (the `autodev-init` skill).
- `merge-dependabot-bump-pr` — Dependabot bump PR review and merge.

## License

Apache-2.0 OR MPL-2.0
