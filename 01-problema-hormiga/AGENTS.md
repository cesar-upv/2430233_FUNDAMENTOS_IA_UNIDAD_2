# Ant Pathfinding — Project Instructions

## Project purpose

This repository contains an educational desktop application for visualizing
pathfinding and graph-search algorithms in a grid environment.

The application is written in Python 3.12 and PySide6/Qt 6.

The core problem is a multi-goal shortest-path problem in which one ant must:

1. start from exactly one initial position;
2. collect every food item;
3. avoid blocked cells;
4. move only in the four orthogonal directions;
5. finish at exactly one goal;
6. minimize total movement cost when using an optimal algorithm.

All movement costs are currently equal to 1.

---

## Package management

Use `uv` exclusively for Python package and environment management.

Allowed:

    uv sync
    uv add <package>
    uv add --dev <package>
    uv run <command>

Do not use:

    pip install
    poetry
    pipenv
    conda

Do not manually edit `uv.lock`.

When dependencies change, let `uv` update the lockfile.

---

## Architecture

The project follows a lightweight layered architecture.

Dependency direction:

    presentation/qt
          |
          v
      application
          |
          +----------+
          v          v
       search    generation
          \          /
           \        /
             domain

`persistence` may translate domain objects to and from external formats, but
the domain must never depend on persistence.

### domain

`src/ant_pathfinding/domain/`

Contains the core model and invariant rules.

The domain:

- MUST NOT import PySide6 or any Qt module.
- MUST NOT depend on presentation.
- MUST NOT depend on application.
- MUST NOT contain UI state.
- MUST NOT know how objects are rendered.
- SHOULD use explicit value objects, enums, dataclasses, and typed contracts
  where appropriate.

### search

`src/ant_pathfinding/search/`

Contains search algorithms, heuristics, search states, results, and events.

The search layer:

- may depend on domain;
- MUST NOT import PySide6;
- MUST NOT manipulate widgets;
- MUST NOT know colors, animations, or graphical items;
- MUST remain independently testable without starting a Qt application.

Search algorithms should expose behavior through typed interfaces or protocols.

Prefer Strategy-style composition for interchangeable algorithms and
heuristics.

### generation

`src/ant_pathfinding/generation/`

Contains random map generation and connectivity validation.

It may depend on domain.

It MUST NOT depend on Qt.

### application

`src/ant_pathfinding/application/`

Coordinates use cases between domain, search, generation, persistence, and
presentation.

Application code should orchestrate behavior rather than implement search
algorithms or rendering logic.

### presentation

`src/ant_pathfinding/presentation/qt/`

Contains PySide6-specific code.

Qt-specific concerns belong here:

- widgets;
- windows;
- scenes;
- views;
- graphical items;
- user input;
- timers;
- visual rendering;
- animations.

Do not place pathfinding logic inside Qt widgets.

### persistence

`src/ant_pathfinding/persistence/`

Reserved for serialization and map storage.

Persistence is not a priority until the core domain, search engine, and UI are
stable.

---

## Design principles

Use design patterns only when they solve an actual project problem.

Preferred patterns include:

- Strategy for search algorithms.
- Strategy for A* heuristics.
- Event-driven / Observer-style communication for search visualization.
- Command for editor operations if undo/redo is implemented later.
- Protocols for stable boundaries between implementations.

Avoid unnecessary factories, abstract base classes, wrappers, managers, and
dependency-injection frameworks.

Prefer simple Python composition over enterprise-style abstraction.

Do not introduce a new abstraction until at least one concrete responsibility
justifies it.

---

## Search correctness

Correctness and optimality are more important than graphical polish.

The multi-goal problem MUST NOT be modeled using only the ant position.

The search state must account for both:

    ant position
    collected or remaining food state

Reaching the same grid cell with a different set of collected foods represents
a different search state.

Do not implement the final solution as repeated greedy searches toward the
nearest food while claiming global optimality.

Algorithms that are documented as optimal must actually preserve optimality
under their stated assumptions.

A* heuristics used for optimal search must be admissible.

When practical, compare A* and Dijkstra results against BFS on small,
deterministic maps.

---

## Qt and concurrency

Never update Qt widgets directly from a worker thread.

Keep algorithm execution and visual rendering separate.

Search visualization should consume search events or equivalent intermediate
state rather than making search algorithms manipulate the UI.

Prefer incremental execution through iterators, generators, events, timers, or
controllers before introducing threads.

Do not introduce concurrency until it is justified by measured UI blocking.

---

## Python standards

Target Python 3.12.

Use modern Python syntax supported by Python 3.12.

All production code should be type annotated.

`mypy` runs in strict mode.

Prefer:

- dataclasses for small data-oriented models;
- Enum or StrEnum for closed sets of semantic states;
- Protocol for behavioral contracts;
- pathlib instead of manual path manipulation;
- explicit domain-specific names.

Avoid:

- `Any` unless technically necessary;
- wildcard imports;
- mutable default arguments;
- global mutable state;
- broad `except Exception` without justification;
- boolean parameters whose meaning is unclear at the call site;
- premature optimization.

Do not use `# type: ignore`, `# noqa`, or equivalent suppression merely to make
quality checks pass.

A suppression requires a real technical reason and should be as narrow and
documented as possible.

---

## Code organization

Keep modules focused on one coherent responsibility.

Do not create directories, classes, protocols, services, repositories, or
controllers merely because they appear in an architecture diagram.

Create architectural components when the implementation actually needs them.

Avoid circular imports.

Avoid duplicated representations of the same domain concept.

Prefer immutable values for search states when practical.

---

## Testing

Use pytest.

Qt-specific tests may use pytest-qt.

New behavior should normally include tests.

Prioritize tests for:

1. domain invariants;
2. search correctness;
3. optimal path cost;
4. unreachable food or goals;
5. goal policies;
6. map generation guarantees;
7. regressions.

Do not modify or weaken a correct test merely to make an implementation pass.

Do not write meaningless tests only to increase coverage percentage.

Coverage is diagnostic information, not the objective of the test suite.

---

## Required verification

After changing Python code, run:

    ./scripts/fix.sh

Then run:

    ./scripts/check.sh

A coding task is not complete until `./scripts/check.sh` passes.

If it fails:

1. determine the actual cause;
2. correct the implementation;
3. run the checks again.

Do not:

- disable Ruff rules to hide a new problem;
- weaken mypy configuration;
- remove failing tests without justification;
- alter `scripts/check.sh` to bypass a failure;
- claim success while the quality gate is failing.

---

## Scope discipline

Implement the smallest coherent change that satisfies the current task.

Do not implement unrelated future features without being asked.

Do not perform large refactors while solving a small isolated problem unless
the existing architecture makes the requested change unsafe or impractical.

If a refactor is necessary, explain why.

Functional correctness comes before visual decoration.

---

## Documentation

Important architectural decisions should be recorded under:

    docs/architecture/

Significant architecture decisions may use ADRs under:

    docs/architecture/decisions/

The AI-assisted development process is recorded in:

    docs/AI_DEVELOPMENT_LOG.md

When an agent performs a meaningful implementation task, record factual
information when requested or when the current workflow explicitly requires
it.

Never invent historical development entries retroactively.

---

## Git safety

Agents may inspect Git state and diffs.

Do not:

- push to a remote;
- force-push;
- rewrite history;
- run destructive reset commands;
- delete uncommitted user work;
- discard unrelated changes.

Do not create commits unless the current task explicitly requests commits.

Before modifying an existing file, preserve unrelated user changes.

---

## Dependency policy

Avoid adding runtime dependencies unless they provide clear value.

The current expected runtime dependency is primarily PySide6.

Standard-library solutions are preferred for domain and search code when they
are clear and maintainable.

Any new runtime dependency should be justified before introduction.

---

## Definition of done

A code implementation is complete only when:

1. it respects the architectural dependency rules;
2. its behavior is covered by appropriate tests;
3. `./scripts/fix.sh` has been run;
4. `./scripts/check.sh` passes;
5. no known correctness issue is being hidden;
6. the final response summarizes the actual changes and verification results.
