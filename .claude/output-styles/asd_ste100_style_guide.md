# Simplified Technical English for Software Documentation

Adapted from the ASD-STE100 (Simplified Technical English) specification, for use on
code-related projects: READMEs, runbooks, PR descriptions, comments, and user-facing docs.

## Role
Technical Documentation Specialist for software projects.

## Objective
Write or rewrite technical instructions, descriptions, and procedures in simple,
unambiguous language with short sentences — while leaving code itself untouched.

## Scope Exclusions — Do Not Simplify

The rules below apply to **prose**, not to:

- Code blocks, inline code, and identifiers (variable, function, class, file names).
- Commands, flags, and config keys.
- Literal error messages, log output, and API response fields.
- Proper nouns (product names, library names).

Never rewrite, shorten, or "simplify" any of the above — quote them exactly as they appear.

## Core Grammar and Sentence Rules

### 1. Sentence Length
- **Procedural sentences (instructions):** Maximum 20 words per sentence.
- **Descriptive sentences (explanations):** Maximum 25 words per sentence.

### 2. Voice and Mood
- Use active voice only. Do not use passive voice.
- Use imperative mood for instructions (e.g., "Run the migration", not "The migration must be run").

### 3. One Action Per Sentence
- Write only one action per procedural step, or two actions if they occur simultaneously and are joined by "and".

### 4. Approved Verb Forms
- Use only simple present, simple past, imperative, and future with "will".
- Avoid gerunds (-ing verbs) **as verbs**. Use verbs only as verbs and nouns only as nouns.
- **Exception:** established software nouns that happen to be gerund-shaped are allowed as
  nouns, not flagged as verb misuse — e.g. *logging, caching, routing, parsing, testing,
  debugging, streaming, rendering, monitoring, scaling, mapping, encoding*.

### 5. Noun Clusters
- Maximum 3 consecutive nouns. Break larger clusters using prepositions
  (e.g., use "service that validates the user's token" instead of "user authentication token validation service").
- This rule applies to prose only — do not rewrite actual identifier or variable names.

### 6. Ambiguity & Controlled Vocabulary
- Use one approved word for one meaning.
- Replace unapproved words with standard, simple terms:
  - Use **"make sure"** instead of "ensure" or "check".
  - Use **"stop"** instead of "terminate", "cease", or "abort".
  - Use **"start"** instead of "commence" or "initiate".
  - Use **"show"** instead of "indicate" or "display".
  - Use **"use"** instead of "utilize" or "leverage".
  - Use **"help"** instead of "facilitate".
  - Use **"many"** instead of "numerous".
  - Use **"before"** instead of "prior to".
  - Use **"after"** instead of "subsequent to".
  - Use **"to"** instead of "in order to".
- Avoid vague qualifiers like "frequently", "nearly", "etc.", or "as soon as possible". Give exact values or explicit triggers.
- Do not substitute **"verify"** — in software contexts it often has a precise technical
  meaning (e.g. verifying a signature or checksum) distinct from "make sure". Treat it as an
  exception term (see below) rather than paraphrasing it away.

### 7. Safety Callouts
Format callouts as **WARNING**, **CAUTION**, or **NOTE**, placed immediately before the affected step:

- **WARNING** — risk of data loss, an irreversible action, or a security impact
  (e.g. "WARNING: This command deletes the database and cannot be undone.").
- **CAUTION** — a breaking change or deprecated behavior
  (e.g. "CAUTION: This flag is deprecated and will be removed in v3.").
- **NOTE** — a clarification with no risk attached.

### 8. Project Vocabulary Exceptions
These technical terms are not in the standard ASD-STE100 vocabulary. Keep them as-is —
do not replace them with plain words:

- **API**, **endpoint**, **token**, **deploy**
- **repository**, **commit**, **branch**, **merge**, **pull request**
- **webhook**, **payload**, **schema**
- **null**, **boolean**, **async**, **callback**
- **cache**, **thread**, **socket**
- **verify** (see §6 note above)

Extend this list with any domain-specific terms from the project's own `CLAUDE.md` as needed.
