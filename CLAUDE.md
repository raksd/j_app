# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state

The repository is nearly empty. It contains no application source, build system, lint config, or test suite, so there are no build, lint, or test commands to run yet. Do not assume a framework or toolchain; ask or inspect again before adding one.

## Layout

- `skills-lock.json` pins externally sourced skills. The `grill-me` entry comes from GitHub `mattpocock/skills` at `skills/productivity/grill-me/SKILL.md`, with a content hash. Keep the lock file in sync if that skill is updated.
- `.agents/skills/grill-me/` holds a local copy of that skill:
  - `SKILL.md` has `disable-model-invocation: true` and delegates to a `grilling` skill via the Skill tool. That `grilling` skill is not in this repo.
  - `agents/openai.yaml` sets `allow_implicit_invocation: false`.

## Skill location

This skill lives under `.agents/skills/`, not `.claude/skills/`. Claude Code loads project skills from `.claude/skills/`, so this one may not be discovered automatically. Confirm before relying on it.
