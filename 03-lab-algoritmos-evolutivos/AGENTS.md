# Agent Operating Rules

This file is the operational contract for AI coding agents working on **Evolutionary Lab**. It is provider-agnostic: do not assume OpenCode, Codex, Claude Code, or a specific multi-agent runtime.

## Mission and non-negotiables

Build a reproducible, extensible educational desktop application for evolutionary algorithms, initially implementing **Project 1: Optimización de funciones (A)** from *Algoritmos evolutivos: un enfoque práctico* (Lourdes Araujo and Carlos Cervigón). The evolutionary algorithms must be implemented **in this repository**, not delegated to a genetic-algorithm framework.

- Prefer **working, tested vertical slices** over speculative infrastructure, lengthy plans, or documentation-only progress.
- The **evolutionary core must not import PySide6, PyQtGraph, or Qt types**.
- Keep reference behavior from the book separate from classroom or experimental variants; do not silently alter the reference algorithm.
- Do not guess unreadable book formulas or pretend to have verified behavior against the original C++.
- Keep the application responsive; simulations must not block Qt's UI thread.
- Preserve deterministic execution when given the same seed, configuration, and implementation version.
- Do not add DEAP, PyGAD, or libraries that implement selection, crossover, mutation, or the evolutionary loop for us.

## Before starting work

1. Read `INSTRUCTIONS.md` (product scope), `docs/ARCHITECTURE.md` (contracts), `docs/ROADMAP.md` (milestones), and `docs/PROJECT_STATUS.md` (handoff state). Read only the portions needed for the current task afterward.
2. Inspect `git status --short`, recent commits (if any), `pyproject.toml`, relevant code, and existing tests.
3. Identify the **smallest incomplete milestone** and the relevant acceptance criteria. Do not repeat completed work.
4. Confirm whether `references/book.pdf` exists **only if the task requires the book's exact wording or C++**. If it is absent, use already verified facts and mark source-dependent work as blocked; never invent source content.
5. If the user's current task explicitly sets a different, narrower scope, follow that scope.

## Working mode and delegation

- Default to **one primary agent**. Use a specialist/subagent only for a clearly separable task with an expected net benefit in time or quality. Avoid agent orchestration overhead under restricted token/time budgets.
- Work on one milestone or narrowly scoped user request at a time. Provide a compact plan when necessary, then implement.
- Define the touched files, expected behavior, and tests before making cross-cutting changes. Avoid two agents editing the same files simultaneously.
- No speculative refactors or premature abstractions. Use `Protocol`, dataclasses, and separation of concerns when they solve a present problem.
- A milestone must result in a usable, demonstrable improvement. Do not spend an entire session on docstrings, enormous mutation-test suites, or framework scaffolding.

## Language and documentation

| Content | Language |
|---|---|
| Code, symbols, modules, APIs, type annotations | English |
| Code comments and docstrings | English; concise and non-redundant |
| Commit messages and technical design docs | English |
| End-user GUI text, errors, educational explanations and equations | Spanish (`es`) |
| `README.md` | Spanish |

Keep user-visible strings outside domain logic and ready for later localization. Do not introduce an elaborate translation framework before it is necessary. Maintain substantial documentation under `docs/`, not in the README. Add comments explaining **why**, not merely restating **what** a statement does.

## Style and architecture

- Target Python **3.12** as initially pinned; do not change the target without a reason and explicit review.
- Follow PEP 8 and project Ruff settings. Use type annotations on public APIs and meaningful dataclasses/immutable value objects as appropriate.
- Use dependency injection for random number generators and external resources; do not depend on module-global randomness in the engine.
- Keep domain models separate from algorithm operators, use-case coordination, Qt views, and persistence adapters.
- Validate configurations and representation/operator compatibility before a run. Handle invalid ranges, non-finite fitness, zero total roulette weight, and invalid chromosome lengths explicitly.
- Respect module boundaries in `docs/ARCHITECTURE.md`; do not make persistence or presentation the source of truth for an experiment.
- Never evaluate arbitrary user-supplied Python code. Custom mathematical expressions are **out of the MVP** and must eventually use a restricted parser with tests.

## Dependencies and prohibited shortcuts

Allowed in scope: PySide6, PyQtGraph, NumPy for visualization support, Python standard library, SQLite, and development tools (`uv`, Ruff, mypy, pytest; Hypothesis when justified). New major runtime dependencies require a clear justification and user approval. Math/plotting libraries must **not** replace the educational algorithm implementations.

Never fabricate sample measurements, test outcomes, screenshots, completed milestones, book citations, or verification claims. Book formulas that OCR garbles must be checked visually before being implemented.

## Tests: cost-aware tiers

1. **Fast loop (during coding):** targeted `uv run pytest ...` for affected tests and `uv run ruff check ...` / `uv run ruff format --check ...` on touched paths.
2. **Milestone gate:** full relevant unit/integration tests, `uv run ruff check .`, `uv run ruff format --check .`, and `uv run mypy src` once configured; run a GUI smoke check when the milestone affects the UI.
3. **Major milestone / release:** full suite, property-based/stress/performance tests and visual regression checks as appropriate. Do not run expensive exhaustive suites after every trivial change.

Do not mark checks as passing if they were skipped. Record the exact checks actually executed. Property tests should focus on invariants: representation bounds, probability normalization, offspring validity, deterministic seeds, population size, and monotonic best-so-far tracking (not monotonic current-generation fitness unless elitism enforces it).

## Git and permitted actions

- Use Conventional Commits (`feat(core): ...`, `test(evolution): ...`, `fix(ui): ...`, `docs: ...`) **after completing a verified milestone**, once development begins.
- Never add an agent as author/co-author. Respect repository Git identity.
- **Do not `git push`, create a remote, publish releases, force-push, delete history, or rewrite previous commits** without explicit permission.
- Do not use destructive Git actions (`git reset --hard`, `git clean -fd`, broad reverts) to discard someone else's work.
- Work inside this repository. Do not alter unrelated local projects or system configuration; normal `uv` cache usage is acceptable.
- Never commit personal secrets, local experiment databases, environments, or the copyrighted reference-book PDF.
- Preserve `uv.lock` and `.python-version` in version control; `.venv/` stays ignored.

## Milestone completion and handoff

When a milestone is completed:

1. Check its acceptance criteria and report actual validation commands/results.
2. Create a coherent conventional commit when authorized to do milestone work; do not stage unrelated files.
3. Update `docs/ROADMAP.md` (milestone status) and `docs/PROJECT_STATUS.md` (brief current state, next task, blockers, validation). Keep `PROJECT_STATUS.md` roughly **50–100 lines or less**.
4. Stop at the requested boundary. Never automatically attempt the entire roadmap.

If interrupted, leave `docs/PROJECT_STATUS.md` with a concise resume point. If a task is blocked, explain what is missing rather than implementing a guessed workaround.
