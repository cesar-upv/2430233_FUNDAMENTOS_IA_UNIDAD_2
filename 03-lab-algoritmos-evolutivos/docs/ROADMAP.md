# Development Roadmap

**Status:** M00 through M11 complete (including M01.1 and M11.1); graphical MVP and scoped UI polish delivered. M18–M19 are complete. M12–M17 and M20 remain TODO.\
**Method:** Small, independent, working milestones with measurable acceptance criteria.\
**Legend:** `TODO` · `IN PROGRESS` · `DONE` · `BLOCKED`.

Each milestone should finish with demonstrated behavior, relevant passing checks, a conventional commit (after user authorization to begin implementation), and an update to `PROJECT_STATUS.md`. Never automatically complete the entire roadmap in one session.

## Phase 0 — Repository and runnable shell

| ID | Status | Deliverable and acceptance |
|---|---|---|
| M00 | DONE | Verified uv/locked dependencies, Python 3.12, package/runtime imports, configured Ruff/pytest/strict mypy, and documented commands in README. |
| M01 | DONE | Runnable PySide6 entry point with sidebar, horizontal tabs, resizable panels and Spanish empty states; light/dark/system appearance. Offscreen GUI tests and real Wayland launch verified. |
| M01.1 | DONE | Refined existing shell: menu removed with quit shortcut preserved; inline Settings with Appearance category, immediate/persistent QSettings themes, licensed local Tabler SVG icons. Navigation/restart/minimum-size tests and visual GUI checks. |
| M02 | DONE | Immutable domain/config models, representation-independent objective contract and one registered Project 1 function, verified visually against printed p.151 / PDF p.149. Strict bounds/finite/dimension/compatibility checks and deterministic unit tests. |

## Phase 1 — Book-based evolutionary core

| ID | Status | Deliverable and acceptance |
|---|---|---|
| M03 | DONE | Binary/string/integer/real conversions, minimal precision-to-length, fixed-length encoding and seeded initial populations using the M02 models. Exact endpoints, nearest quantization, validation and reproducibility tested; [0,1], precision 0.001 uses 10 bits. |
| M04 | DONE | Immutable individual/population evaluation using registered problems, explicit identity/objective-only fitness policies, separate objective/fitness statistics and normalized mean pairwise Hamming diversity. Negative objectives, ties, duplicate genotypes, zero weights and singletons tested; no selection probabilities or operators. |
| M05 | DONE | Roulette with half-open cumulative intervals, SUS and binary tournament; explicit zero-weight/tie policies, immutable sampling traces and deterministic boundary tests. |
| M06 | DONE | Two complementary offspring, per-pair one-point crossover and per-bit mutation; explicit short/incompatible chromosome policies and immutable cut/mutation traces. |
| M07 | DONE | PDF-verified reference scheduling/direct parent replacement and classroom strict improvement; validated configuration, immutable snapshots/traces, statistics/best-so-far and reproducible headless f1 runs through 100 generations. |

## Phase 2 — First demonstrable academic MVP

| ID | Status | Deliverable and acceptance |
|---|---|---|
| M08 | DONE | Worker-evaluated f1 curve and real initial population, generation updates, best/selected markers and snapshot-based inspector; theme and Wayland smoke checks. |
| M09 | DONE | Full worker runs, cooperative cancellation/reset/close, separate replay timer and previous/next/slider/generation seek; deterministic reruns and responsiveness tested. |
| M10 | DONE | Real best/mean/best-so-far fitness and Hamming history, validated Spanish parameter form with all selectors/rates, replay speed and instant/manual mode; theme/data checks. |
| M11 | DONE | Installed-entry end-to-end f1 runs, deterministic GUI reruns, real replay timer, inspection/navigation/statistics/themes, 241 passing tests and native Wayland captures; limitations recorded. |
| M11.1 | DONE | Controlled chart views with reset actions, readable titles/axes/external legends, snapshot summaries, grouped parameters and consistent replay/button states; 246 tests and updated native captures. |

**MVP completion boundary:** At the end of **M11**, the user has a functional Project 1 single-variable maximization laboratory, including all three selection methods and the inspected, replayable evolution of generations.

## Phase 3 — Teaching features

| ID | Status | Deliverable |
|---|---|---|
| M12 | TODO | Spanish concept library and context-aware formula/help views, with clear source labels. |
| M13 | TODO | Independent interactive selection, crossover, mutation and encoding demos plus guided exercises (no grading). |

## Phase 4 — Persistence, comparisons and exports

| ID | Status | Deliverable |
|---|---|---|
| M14 | TODO | Versioned SQLite experiment storage and full generation replay for ordinary runs; size estimates and retention options for large runs. |
| M15 | TODO | Named, validated presets with fixed/automatic seed policy; run/preset separation; reopen experiment. |
| M16 | TODO | Side-by-side results comparison, charts and parameter summaries for independent experiments. |
| M17 | TODO | Verified JSON/CSV data and PNG/SVG plot exports, then PDF run report. |

## Phase 5 — Complete Project 1

| ID | Status | Deliverable |
|---|---|---|
| M18 | DONE | PDF-verified literal/signed minimization policies, per-generation fitness revision, three verified minima and real GUI problem/direction selection. |
| M19 | DONE | Per-variable binary segments/domains/precision and matched crossover/mutation; 11 verified problem families, scalar curves/2D heatmaps/normalized coordinate views, adaptive parameter form and real GUI runs. |
| M20 | TODO | Parameter studies, optima verification and a major integration/regression check. |

## Phase 6 — Project 2 and future extensions

| ID | Status | Deliverable |
|---|---|---|
| M21 | DONE | Immutable real vectors, seeded uniform initialization, per-gene uniform reset mutation and explicit reject/clip bounds policies, verified against Project 2. |
| M22 | DONE | PDF-checked one-point/uniform/arithmetic/SBX, literal and named continuous SBX variants, explicit repair traces and compatible real operators in the shared engine. |
| M23 | DONE | Project 1/2 selector, compatible real controls, shared worker/plots/replay/inspector, normalized real diversity, deterministic GUI runs and source-faithful notes. |
| FUTURE | TODO | Genealogy explorer, density/histogram and 3D views, user-defined safe mathematical expressions, custom palettes, GIF/video, multiprocess runs, external plugins. |

## Book-verification gates

Before marking a book-specific milestone `DONE`, verify the original equations, order of selection/reproduction/evaluation, and replacement semantics against the scanned PDF. The reference's Chapter 2 **parent replacement** must not be replaced by the teacher's conditional-improvement rule. Verify formulas visually when OCR is ambiguous. Keep detailed original C++ parity **optional**; use small deterministic unit tests for comparable behaviors.

## Execution policy

- Work on the smallest remaining milestone that unblocks end-to-end behavior.
- Small checks often; expensive property, performance, mutation or full visual suites at major milestones/releases.
- Only add modules that current functionality needs. No speculative plugin loader, account system or installers.
- Update this status table when a milestone finishes and keep the handoff concise in `PROJECT_STATUS.md`.

## Demo configuration (application defaults, not book-mandated)

Project 1 `f1` on `[0,1]`, `epsilon=0.001`, 10-bit encoding, population 10, 100 generations, roulette, one-point crossover at 70%, per-bit mutation at 1%, reference replacement, seed 42. All rates and values are configurable; they are **not quotations of the textbook or instructor requirements**.

M07 implements these demo rates as configuration defaults. Reference reproduction uses
per-individual crossover candidate probability and one shared cut per generation;
the explicit `pairwise` alternative uses probability/cut per consecutive pair.
