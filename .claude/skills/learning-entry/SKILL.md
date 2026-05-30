---
name: learning-entry
description: "Manual-only. Runs ONLY when the user explicitly types /learning-entry. Never auto-invoke. Do not trigger on code changes, diffs, commits, or any other event."
---

# /learning-entry — Append an Entry to LEARNING.md

**MANUAL INVOCATION ONLY.** Do not run this skill unless the user has explicitly typed `/learning-entry`. Never infer that this skill should run from a diff, a commit message, or a code change.

---

## Arguments

The command signature is:

```
/learning-entry [decision|mistake] "<short title>"
```

- **Type**: `decision` or `mistake`. If missing or ambiguous, STOP immediately and ask: "Is this a `decision` or a `mistake`?"
- **Title**: Short descriptive title for the entry. If missing, ask: "What is the short title for this entry?"

Do not proceed until both arguments are clearly established.

---

## Step 1 — Read the Git Context (No User Prompting)

Run these three commands to gather context from the repository. Do NOT ask the user to describe what changed — read it from the diff yourself.

```bash
git log -20 --oneline
git diff HEAD
git diff --staged
```

Read the output carefully:
- From `git log`: note the 20 most recent commit messages and dates.
- From `git diff HEAD` and `git diff --staged`: identify which files changed, what was added/removed, and any observable structural decisions.

Do NOT ask the user to repeat anything visible in these outputs.

---

## Step 2 — Ask EXACTLY ONE Question, Then Wait

After reading the git context, ask the user exactly ONE question:

> **"Rationale beyond the diff?"**

Wait for the user's answer before proceeding. Do not ask follow-up questions. Do not ask for clarification unless the user's answer is literally empty. The user's answer is the "why behind the code" — the reasoning that is NOT visible in the diff. It may be short (one sentence) or long (a paragraph). Accept it as-is.

Do NOT:
- Infer or fabricate the rationale from the diff
- Ask about files changed, what the code does, or what was tested
- Ask multiple questions

---

## Step 3 — Format the Entry

Format the entry to match the EXACT style of the relevant section in `D:\Quant_engine\LEARNING.md`.

### For `decision` entries — match the "📐 Decisions Log" format:

```markdown
### YYYY-MM-DD — <Title from arg>

**Context**: <1–3 sentences summarizing the situation drawn from git log + diff. What was the state of the system before this change? What problem was being solved?>

**Decision**: <What was decided or built? Draw specifics from the diff — file names, function names, config keys, test counts, CLI flags. Be concrete.>

**Rationale**: <The user's answer to "Rationale beyond the diff?" verbatim or lightly cleaned. Do NOT rephrase substantively.>

**Files**: <Comma-separated list of the key files touched, drawn from git diff.>

---
```

- Date: today's date in `YYYY-MM-DD` format. Today is 2026-05-28 unless the system date says otherwise.
- Do not add sub-bullets or tables unless the user's answer includes them.
- Do not invent rationale. The diff gives context; the user gives reasoning.

### For `mistake` entries — match the "🐛 Mistakes & Corrections" template:

```markdown
### YYYY-MM-DD — <Title from arg>

**What happened**: <What went wrong? Draw from git diff — what was the broken state, what error was visible?>

**Root cause**: <Technical cause of the bug or misjudgment, drawn from diff + user answer.>

**Impact**: <What was affected? Tests? Live signals? Data integrity? Draw from diff; fill with user answer where diff is insufficient.>

**Fix**: <What was changed to fix it? Be specific — file names, function names, what was added/removed. Draw from diff.>

**Guardrail added**: <What practice, assertion, or check prevents recurrence? If user didn't mention one, write "None specified.">

**Test added**: <What test was added, if any? If user didn't mention one, write "None specified.">
```

- Do not add a trailing `---` separator for mistake entries (the section already has template-level formatting).
- Do not invent what the bug was or how it was fixed beyond what the diff shows and what the user said.

---

## Step 4 — Insert at the TOP of the Correct Section Using the Edit Tool

**NEVER use the Write tool on `LEARNING.md`.** A PreToolUse hook blocks Write to this file and it would overwrite history. Always use the **Edit tool**.

**NEVER modify, delete, or reorder any existing entries.** This file is append-only.

### For `decision` entries:

The anchor for the Edit tool is the line immediately after the section header and its description block:

```
## 📐 Decisions Log

> Architectural and design choices with rationale. The "why" behind the code.

```

Insert the new entry immediately after that blank line, before the current first entry (the one that starts `### 2026-05-28 — Tier 1 Complete...`).

Specifically, use this as `old_string` in the Edit tool:

```
> Architectural and design choices with rationale. The "why" behind the code.

### 2026-05-28 — Tier 1 Complete
```

And prepend the new entry before the `### 2026-05-28` line in `new_string`.

If the topmost existing entry is different (because a newer entry was added since this skill was written), anchor on the section header line and the first `###` that follows it.

### For `mistake` entries:

The anchor is the section header block:

```
## 🐛 Mistakes & Corrections

> Bugs, bad signals, misjudgments. Post-mortem format. Pain teaches.

```

Insert the new entry immediately after that blank line, before the first existing mistake entry.

Anchor with `old_string` being the description line plus enough of the following content to be unique:

```
> Bugs, bad signals, misjudgments. Post-mortem format. Pain teaches.

### 2026-05-19 — Backtest engine sliced bottom-N
```

And prepend the new entry before the `### 2026-05-19` line in `new_string`.

If newer mistake entries exist, anchor on whatever is currently the topmost entry.

---

## Step 5 — Show the Inserted Entry

After the Edit tool call completes, display the full text of the inserted entry to the user so they can confirm it looks right.

Do NOT commit. Do NOT git add. Do NOT modify any other file.

---

## Anti-Patterns — Never Do These

- Do NOT use the Write tool on `LEARNING.md` (it overwrites the file).
- Do NOT infer the rationale from the diff — always ask the user.
- Do NOT ask the user to describe the diff — read it yourself.
- Do NOT insert anywhere except the TOP of the correct section.
- Do NOT modify any existing entry.
- Do NOT auto-trigger this skill from diffs, commits, or code changes.
