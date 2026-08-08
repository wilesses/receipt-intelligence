# Receipt Tracker v2 — Project Guide

## Purpose

You are working on a long-term software project.

Your responsibilities are:

- implement requested features;
- preserve code quality;
- preserve project knowledge;
- keep documentation synchronized with the code;
- leave the project in a better state after every completed task.

The codebase is the primary source of truth.

---

# Project Memory

The project uses an Obsidian Vault as its long-term knowledge base.

Documentation is not temporary.

It represents accumulated engineering knowledge.

Every completed task should improve either:

- the code;
- the documentation;
- or both.

---

# Source of Truth

When information conflicts, always trust in this order:

1. Source code
2. Database schema
3. CURRENT_CONTEXT.md
4. Other Obsidian documentation

Never modify working code just because documentation is outdated.

Update the documentation instead.

---

# Startup Workflow

Before starting any implementation:

1. Read this PROJECT_GUIDE.md.
2. Inspect the affected code
3. Read CURRENT_CONTEXT.md.
4. Run:

```powershell
git status
```



4. Read only the Obsidian notes relevant to the requested task.
5. Inspect the related code.
6. Understand the existing implementation before changing anything.

Do not read the entire Vault unless explicitly requested.

---

# Workflow Selection

Choose the appropriate development workflow automatically.

Do not wait for the user to explicitly request a workflow.

Use them only when they meaningfully improve the task.

Preferred mapping:

- New feature → Brainstorming → Writing Plan
- Large multi-step implementation → Writing Plan
- Bug investigation → Systematic Debugging
- Before claiming completion → Verification Before Completion
- Major completed implementation → Request Code Review
- Security-sensitive changes → Security Scan

Do not invoke workflows for trivial edits, formatting, documentation-only changes, or simple configuration updates.

Keep workflow overhead proportional to the complexity of the task.

---


# Development Rules

Prefer:

- small focused changes;
- readable code;
- existing architecture;
- reusable code;
- consistency.

Avoid:

- unnecessary refactoring;
- rewriting working code;
- introducing duplicate logic;
- changing public behavior without reason.
- Never introduce a second implementation of existing logic.
- If similar functionality already exists, extend it instead of creating parallel code.
- Before creating a new module or service, check whether the existing architecture can be extended instead.

If a large architectural change seems beneficial, explain it before implementing it.

---

# Data Safety

Existing project data is valuable.

Unless explicitly instructed by the user, NEVER:

- delete the SQLite database;
- recreate the database;
- drop tables;
- truncate tables;
- remove receipt history;
- overwrite user data;
- delete imported PDF receipts;
- destroy existing data.

When a database change is required:

- preserve existing data whenever possible;
- prefer additive migrations;
- document schema changes;
- update CURRENT_CONTEXT.md.

If a destructive migration is required, stop and ask the user.

---

# Obsidian Vault Safety

The Obsidian Vault is the permanent knowledge base for this project.

Treat every project note as valuable.

Unless explicitly instructed by the user, NEVER:

- delete notes;
- delete folders;
- rename notes;
- move notes;
- remove documentation because it looks old;
- replace detailed documentation with shorter versions.

If documentation becomes outdated:

- update it;
- extend it;
- or mark it as deprecated.

Preserve engineering knowledge.

Do not modify personal notes or any Vault content unrelated to Receipt Tracker.

---

# Obsidian Documentation Rules

Before creating a new note:

1. Search for existing documentation.
2. Extend existing notes whenever appropriate.
3. Create a new note only when the concept is genuinely new.

Avoid duplicate notes.

Use Obsidian wikilinks.

Example:

[[Receipt Parser]]

When a new note is created:

- connect it to existing notes;
- update parent notes if appropriate;
- avoid orphan pages.

Create links because they represent meaningful relationships, not to increase graph density.

---

# CURRENT_CONTEXT.md

CURRENT_CONTEXT.md is the project's working memory.

Every future Codex session starts from this file.

After every completed task update it.

Keep it concise.

Do not turn it into a changelog.

It should always describe the CURRENT verified project state.

It should contain:

- current project state;
- latest completed task;
- files changed;
- database changes;
- current implementation;
- important implementation details;
- unfinished work;
- confirmed known issues;
- next recommended task;
- instructions for the next Codex session.

Replace obsolete information.

Preserve still-relevant context.

---

# Learning Policy

Whenever you discover information that will likely save time in future development, preserve it.

Examples:

- parser edge cases;
- database constraints;
- implementation limitations;
- architectural decisions;
- important assumptions.

Do not store guesses.

Store verified knowledge only.

---

# Documentation Policy

Documentation must describe implemented behavior.

Never describe planned functionality as completed.

If implementation is partial, document it as partial.

Keep documentation synchronized with the code.

---

# Dependency Policy

Before introducing a new dependency:

- verify that the functionality cannot reasonably be implemented using the standard library or existing project dependencies;
- explain why the dependency is needed;
- avoid adding packages for small convenience features.

---

# Security Review

Perform a security review only when appropriate.

Typical examples:

- authentication
- authorization
- file uploads
- SQL queries
- database migrations
- shell execution
- external APIs
- network services
- user-controlled input

Do not perform security workflows for ordinary UI work, styling, documentation, or simple refactoring.

---


# Git Rules

Before making changes:

```powershell
git status
```

Before finishing:

```powershell
git status
git diff
```

Never execute without explicit user permission:

- git reset --hard
- git clean
- git restore
- force checkout
- any command that discards user work

Do not create commits unless explicitly requested.

---

# Verification

Before declaring the task complete:

- review modified code;
- check for obvious errors;
- run available tests when possible;
- verify requested behavior;
- update documentation;
- update CURRENT_CONTEXT.md.

If verification cannot be performed, clearly explain why.

Never claim success without verification.

---

# Architecture Preservation

Prefer extending the existing architecture over introducing new abstractions.

Avoid:

- unnecessary frameworks;
- duplicate services;
- parallel implementations;
- large-scale rewrites.

If an architectural redesign appears beneficial, explain the trade-offs before implementing it.

Favor incremental improvements over replacement.

---


# Definition of Done

A task is complete only when:

- requested functionality is implemented;
- existing user work is preserved;
- documentation matches the implementation;
- relevant Obsidian notes are updated;
- meaningful wikilinks are added or updated;
- CURRENT_CONTEXT.md is updated;
- git status has been reviewed;
- the final report is provided.

---


---

# Final Report

## Summary

## Files changed

## Verification

## Next recommendation