---
name: hypothesis-verdict
description: "Manual-only. Runs ONLY when the user explicitly types /hypothesis-verdict. Never auto-invoke. Do not trigger on hypothesis file changes, backtest results, or any other event."
---

# /hypothesis-verdict — Apply a Verdict to a Hypothesis

**MANUAL INVOCATION ONLY.** Do not run this skill unless the user has explicitly typed `/hypothesis-verdict`. Never infer that this skill should run from a diff, a commit, a backtest result, or any other event.

**This skill is MECHANICAL ONLY.** It moves files, fills template scaffolding, and updates status lines. The verdict REASONING comes entirely from the user — never inferred, never invented.

---

## Arguments

The command signature is:

```
/hypothesis-verdict <H-ID> [killed|shelved|backtested|promoted]
```

- **H-ID**: Hypothesis identifier, e.g. `H007`. If missing, ask: "Which hypothesis ID? (e.g. H007)"
- **Verdict**: One of `killed`, `shelved`, `backtested`, or `promoted`. If missing or ambiguous, ask: "What is the verdict? (`killed` / `shelved` / `backtested` / `promoted`)"

Do not proceed until both arguments are clearly established.

---

## Step 1 — Locate the Hypothesis File

Search for the hypothesis file at:

1. `D:\Quant_engine\docs\research\hypotheses\<H-ID>_*.md` (primary location)
2. `D:\Quant_engine\docs\research\graveyard\<H-ID>_*.md` (if already moved)

Use the Glob tool with pattern `docs/research/hypotheses/<H-ID>_*.md` and then `docs/research/graveyard/<H-ID>_*.md`.

If no file is found in either location, STOP and report:
> "No hypothesis file found for `<H-ID>` in `hypotheses/` or `graveyard/`. Check the ID and try again."

If found, read the file fully.

Also read the following reference files to understand the required structures:
- `D:\Quant_engine\docs\research\graveyard\H004_vol_targeting.md` — the graveyard format to model
- `D:\Quant_engine\docs\research\TEMPLATE_HYPOTHESIS.md` — the hypothesis template structure

---

## Step 2 — STOP and Ask for Verdict Reasoning

Do NOT write any reasoning yourself. Do NOT infer what failed from the hypothesis file or any backtest results you can see. Do NOT pre-fill autopsy fields from memory.

Ask the user this exact question, substituting the verdict:

> **"What is the reasoning for this verdict?"**
>
> Provide the following for the autopsy:
> 1. What failed (or passed): which kill criteria triggered, or which promotion criteria were met?
> 2. Structural vs parameter failure: is the idea fundamentally wrong, or wrong for this universe/constraint set?
> 3. Revisit conditions: under what future conditions should this be re-examined (or "none" if truly dead)?
>
> Your words will go verbatim into the reasoning fields — I will not rephrase or add to them.

Wait for the user's answer. Do not proceed until they respond. Do not ask follow-up questions unless the user's answer is literally empty.

---

## Step 3 — Update the Hypothesis File Status Line

Using the **Edit tool** (never Write), update the `**Status:**` line in the hypothesis file:

- `killed` → `**Status:** KILLED`
- `shelved` → `**Status:** SHELVED`
- `backtested` → `**Status:** BACKTESTED`
- `promoted` → `**Status:** PROMOTED`

Also update the `**Last updated:**` field to today's date (`2026-05-28` unless the system date says otherwise).

If the hypothesis file already has a `## Decision` section, update the `**Outcome:**` field to match the verdict. If the `## Autopsy` section exists, fill it using the user's answer from Step 2 — verbatim into the appropriate sub-fields (`**Why it failed:**`, `**Structural vs parameter issue:**`, `**Revisit conditions:**`). Do not add text that the user did not provide.

---

## Step 4 — Execute the Verdict Action

### If verdict == `killed`:

1. Move the hypothesis file to the graveyard using `git mv`:
   ```bash
   git mv "docs/research/hypotheses/<filename>" "docs/research/graveyard/<filename>"
   ```
   This preserves git history. Do NOT use a regular file copy + delete.

2. The graveyard file already exists after the move — it IS the hypothesis file. Verify it is now at `docs/research/graveyard/<filename>`.

3. Check whether a separate graveyard copy needs to be created. Model the graveyard entry on `H004_vol_targeting.md`:
   - Add the preamble block at the top:
     ```markdown
     > **Graveyard copy.** Full hypothesis at `docs/research/hypotheses/<filename>`.
     > Graveyard entries are never removed.
     ```
   - Add a `## Kill Summary` table with kill criteria columns: Criterion / Result / Value.
   - The `## Autopsy` section uses the user's reasoning from Step 2.
   - Only add sections that are substantiated by the hypothesis file content + user answer. Do not invent backtest tables if the user did not provide numbers.

   Note: For H004 the hypothesis file WAS the graveyard file after `git mv`. Reproduce this pattern — the moved file becomes the graveyard resident, updated with the graveyard preamble and kill summary.

### If verdict == `shelved`:

Do NOT move the file. Keep it in `hypotheses/`. Update status to SHELVED in place using the Edit tool. Add or update a `**Unlock condition:**` line in the Preconditions section (or Decision section) with the user's stated revisit conditions.

### If verdict == `backtested`:

Update status to BACKTESTED in place using the Edit tool. No file move. The backtest results section should already exist in the hypothesis file — if the user provided numbers in Step 2, insert them into the `## Backtest Results` table using the Edit tool.

### If verdict == `promoted`:

Update status to PROMOTED in place using the Edit tool. No move to graveyard. Add a note to the `## Decision` section: "Validated findings should be moved to `docs/research/findings/` per PIPELINE.md." Do not create the findings file yourself — note it as a TODO for the user.

---

## Step 5 — Update CLAUDE.md

There are **two** "Current hypothesis count:" lines in `D:\Quant_engine\CLAUDE.md` that must both be updated:

1. Line ~152 — in the "Structured Research Pipeline" section (under `## What Claude Code Should Do Proactively`).
2. Line ~181 — in the "Current Phase" block near the bottom of the file.

For each line, use the **Edit tool** to update the hypothesis count entry. Match the EXACT existing format:

```
**Current hypothesis count:** H001 (graveyard — ...) · H004 (graveyard — ...) · H005 (graveyard — ...) · H006 (SHELVED — ...)
```

Rules for updating:
- If verdict is `killed`: add `· <H-ID> (graveyard — <title>, KILLED <date>)` and maintain the existing entries. Keep entries in H-number order.
- If verdict is `shelved`: add `· <H-ID> (SHELVED — <title>, re-evaluate <condition>)`.
- If verdict is `backtested`: add `· <H-ID> (BACKTESTED — <title>)`.
- If verdict is `promoted`: add `· <H-ID> (ACTIVE — <title>, PROMOTED <date>)`.
- If the H-ID is already in the count line (e.g., previously SHELVED and now KILLED), replace its entry in place.

Use the Edit tool with the exact existing line as `old_string` to make this surgical — do not rephrase or reformat any other part of the line.

---

## Step 6 — Propose a Commit Message (Do NOT Commit)

Print the following for the user — do not run `git commit`:

```
Proposed commit message:
────────────────────────
<verdict>: <H-ID> <title> — <one-line summary of what triggered the verdict>

Details:
- Status: <old status> → <KILLED/SHELVED/BACKTESTED/PROMOTED>
- <one key finding from user's reasoning, 1 sentence>
- CLAUDE.md hypothesis count updated (both occurrences)
<if killed:>
- Graveyard: docs/research/graveyard/<filename>
────────────────────────
Do NOT run git commit — Arsh executes manually.
```

---

## Step 7 — Summary to User

Show a brief summary:
- What file was updated / moved
- What status line now reads
- Which two lines in CLAUDE.md were updated
- The proposed commit message

---

## Anti-Patterns — Never Do These

- Do NOT write verdict reasoning yourself — only the user provides it.
- Do NOT infer kill criteria from the hypothesis file content or any backtest results visible in the repo.
- Do NOT use `git commit` — only propose the message.
- Do NOT use the Write tool on `CLAUDE.md` or the hypothesis file — always use Edit.
- Do NOT move a `shelved` hypothesis to the graveyard — SHELVED stays in `hypotheses/`.
- Do NOT skip either CLAUDE.md occurrence — both must be updated.
- Do NOT auto-trigger from diffs, commits, backtest outputs, or any other event.
- Do NOT create new hypothesis files — this skill only processes existing ones.
