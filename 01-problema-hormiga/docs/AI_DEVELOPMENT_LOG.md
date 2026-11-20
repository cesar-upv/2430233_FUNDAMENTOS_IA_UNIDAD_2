# AI Development Log

Factual record of AI-assisted development work. Entries are written when the
work happens; they are never back-dated or invented.

## 2026-10-05 — Phase 1: grid domain and optimal multi-goal BFS

### Scope delivered

First functional base of the project: a minimum grid model, a typed multi-goal
search state, an optimal BFS with path reconstruction, and unit tests.
Deliberately **not** built in this phase: Qt / GUI, A*, Dijkstra, random map
generation, persistence, animations.

### Agents used

| Agent | Role in this phase |
|---|---|
| orchestrator | coordination, layer/contract decisions, quality gate, this log |
| algorithms | all production code (`domain/`, `search/`) and its tests |
| tester | independent adversarial verification; own regression suite |
| reviewer | one final read-only review |

`architect` was deliberately not used: the contracts were fully determined by
`AGENTS.md` plus the functional rules of the task, so no design exploration was
required. `qt-ui` and `visualization` had no work in this phase.

### Files created

Production:

- `src/ant_pathfinding/domain/position.py` — immutable `(x, y)` cell coordinate,
  `x` = column, `y` = row growing downwards, plus the four orthogonal offsets.
- `src/ant_pathfinding/domain/grid.py` — immutable `width x height` grid owning a
  normalized `frozenset` of blocked cells; validates positive dimensions and
  in-bounds obstacles; `contains`, `is_walkable`, in-bounds `neighbors`.
- `src/ant_pathfinding/domain/scenario.py` — `AntScenario(grid, start, goal, foods)`,
  the problem instance; validates that start, goal and every food are walkable.
- `src/ant_pathfinding/search/state.py` — `SearchState(position, collected)`; the
  collected-food set is part of the state identity.
- `src/ant_pathfinding/search/result.py` — immutable `SearchResult(found, path,
  cost, expanded_states)` with `success`/`failure` constructors and invariant checks.
- `src/ant_pathfinding/search/bfs.py` — `solve_bfs(scenario)`: BFS over states with
  parent pointers for path reconstruction.

Tests: `tests/unit/domain/test_position.py`, `test_grid.py`, `test_scenario.py`;
`tests/unit/search/conftest.py` (shared solution-validity helper),
`test_state.py`, `test_result.py`, `test_bfs.py`;
plus the independent adversarial suites
`tests/unit/domain/test_domain_adversarial.py` and
`tests/unit/search/test_bfs_adversarial.py`.

### Main decisions

- **Multi-goal state is `(position, collected frozenset)`.** Reaching the same
  cell with different collected food is a different state; a visited set keyed by
  position alone is invalid for this problem.
- **BFS is optimal here** because every move costs 1, so the queue yields states
  in non-decreasing depth and the first terminal state popped is optimal.
  No greedy "walk to the nearest food" strategy exists in production code; it is
  implemented only as a counterexample oracle inside the adversarial tests.
- **Terminal condition is a conjunction**: on the goal cell AND all food
  collected. Passing through the goal earlier keeps expanding.
- **Search state space is `cells x 2^foods`** — inherent to exact multi-food
  search. Recorded here as the scaling constraint for the future UI.
- **Value objects normalize their collections in `__post_init__`** (`frozenset` /
  `tuple`) so nothing can be aliased from a mutable argument, while keeping the
  precise read-side annotations so the search hot loop and path consumers need no
  defensive conversions.
- **`expanded_states` counts queue removals** (states expanded), including the
  initial state and, on success, the terminal goal state. It is **not** the number
  of discovered states and **not** an ant-step count:
  `expanded == discovered - len(frontier at return)`.
- Deliberately no Strategy protocol or ABC: with a single algorithm, an
  interchangeable interface would be a speculative abstraction.

### Verification performed

- `./scripts/fix.sh` then `./scripts/check.sh` after every change set.
- Independent adversarial testing (`tester`): optimality of `solve_bfs`
  cross-checked against three references that do not mirror the implementation
  (Held-Karp DP over food orders, uniform-cost search over an integer food mask,
  and a depth-limited DFS referee), plus exhaustive 2x2 and 3x3 sweeps and
  randomized robustness sweeps — agreement on `found` and `cost` in every case,
  no disagreement.
- Defects found by `tester` and fixed by `algorithms`: `SearchState` did not
  normalize `collected` (an unhashable, mutable state was constructible),
  `SearchResult` did not normalize `path` (the cost invariant could be broken
  after construction), and a false claim in the `solve_bfs` docstring. The tester
  converted those into permanent regression tests.
- One final read-only review (`reviewer`) with an independent re-derivation of
  BFS optimality. Findings fixed: the `expanded_states` docstring overclaimed
  ("strictly smaller" than the discovered count — false when the frontier is empty
  at return), stale test docstrings restating the refuted claim, docstrings that
  promised inputs their annotations forbade, and a domain docstring that described
  Qt scene rendering, which `AGENTS.md` forbids in the domain layer.

### Known pending items (not blocking, deferred on purpose)

- The adversarial suite is large (~2.2k lines) relative to the production code;
  `reviewer` recommends folding the repeated reference-agreement sweeps into a
  smaller parametrized set.
- `tests/unit/domain/test_domain_adversarial.py` imports the search layer and
  asserts on a search result, which inverts the layering the source respects; the
  search-exercising tests belong under `tests/unit/search/`.
- Several helpers are duplicated between the project tests and the adversarial
  suite; the duplication is intentional (the adversarial copy must stay
  independent of the code under test) but is currently undocumented.
- No architectural decision record exists yet under `docs/architecture/`; the
  decisions above are currently recorded only in this log and in code.
- `mypy` in `pyproject.toml` covers only `src/ant_pathfinding`, so test
  annotations are not type-checked.
- Validation raises `AttributeError` for non-`Position` inputs (e.g. plain
  tuples) and does not reject fractional grid dimensions; decide when a real
  caller (persistence, editor) exists.
- `src/ant_pathfinding/__init__.py` still holds the scaffold placeholder `main()`
  and its line is the only uncovered line.
- `solve_bfs` is a single blocking call returning one value; the search progress
  contract (iterator/events) must be settled before the visualization phase.

## 2026-10-05 — Phase 2: extensible search engine (Dijkstra, A*, progress contract)

### Scope delivered

One incremental search engine shared by BFS, Dijkstra and A*, an admissible
multi-goal heuristic, a name-based selection interface, and the Qt-free search
progress contract the visualization phase consumes. Deliberately **not** built:
heuristic memoization, obstacle-aware distances, weighted edges.

### Agents used

| Agent | Role |
|---|---|
| orchestrator | coordination, quality gate, this log |
| architect | design of the algorithm interface, the progress contract, the heuristic and the metric semantics (design only) |
| algorithms | all production code (`search/`), ADRs, docstring accuracy |
| tester | adversarial optimality/consistency verification; independent suite |
| reviewer | final read-only review of the engine and the heuristics |

### Files created

- `search/progress.py` — `SearchOutcome`, `SearchStatistics`, `SearchStep`: the
  observable progress contract, a leaf module that does not import the runner.
- `search/runner.py` — `SearchRunner`: the single expansion loop. Priority is
  `(cost + estimate, insertion sequence)`; stale pops are discarded without being
  counted; a state whose cost improves is **reopened**, not closed.
- `search/dijkstra.py`, `search/astar.py`, `search/algorithms.py` — entry points
  plus `SearchAlgorithm` / `new_runner` / `solve` (`match` + `assert_never`).
- `search/heuristics/{__init__,lower_bounds}.py` — `type Heuristic`, plus
  `uniform_cost` (0) and `manhattan_mst`.
- `docs/architecture/decisions/0001-one-search-engine-three-settings.md`,
  `0002-admissible-inconsistent-heuristic-with-reopening.md`.

`search/bfs.py` was rewritten as a delegation to the engine; `SearchResult` and
`SearchState` were **not** modified, so the existing 691 tests still passed unchanged.

### Main decisions

- **One engine, three settings.** The three algorithms differ only in what they add
  to the accumulated cost. Written as three loops, the multi-goal goal test, the
  counters and the progress contract would exist three times. See ADR 0001.
- **Heuristic: MST over `{ant} ∪ pending foods ∪ {goal}`, Manhattan metric.** It
  accounts for pending food *and* the goal, which `max(d(nearest food), d(goal))`
  does not, and it grows with the number of remaining targets. Admissibility: the
  first-visit order of a completion walk is a Hamiltonian path over that vertex set,
  and a Hamiltonian path is a spanning tree.
- **The heuristic is admissible but NOT consistent, on purpose.** The design's
  consistency proof was wrong — MST is not monotone under vertex-set inclusion, and a
  move *replaces* the ant's own vertex, so the estimate can jump in either direction
  (smallest verified counterexample: a 2x3 grid with no walls, estimate 4 → 2 across
  one move). The engine reopens improved states instead of closing them, so
  admissibility alone gives optimality. See ADR 0002.
- **On a unit-cost grid Dijkstra *is* BFS** — same pop order, same expanded count,
  same path. Documented and pinned by tests rather than presented as a coincidence.
- **No `Protocol`/`ABC`/registry.** `SearchAlgorithm` + a `match` is the whole
  selection interface; the module docstring names the trigger for revisiting it.
- **`SearchResult` untouched.** Counters live on `SearchRunner.statistics` as a
  snapshot; extending the result would have meant editing 81 correct assertions or
  inventing dishonest defaults.

### Metrics semantics

`expanded_states` counts states popped, not superseded, and processed — including the
initial state and, on success, the terminal state. `discovered_states` counts distinct
states ever inserted. `frontier_size` counts queued entries, superseded included;
`frontier_peak_size` is its high-water mark. For uniform cost
`discovered_states == expanded_states + frontier_size`; under A* only
`discovered_states - expanded_states <= frontier_size` holds, and a reopened state is
counted as an expansion twice, so `expanded_states` can exceed `discovered_states` on
a **successful** run. All documented on `SearchStatistics`.

### Defects found and fixed

- `algorithms` found that the architect's consistency proof was invalid and rewrote
  four modules' docstrings around the real behaviour.
- `tester` found four documentation overclaims, including "a successful run expands
  at most the discovered states" (false for a reopening search) and an A* docstring
  that implied consistency was required for optimality. All fixed.
- `reviewer` found eleven more documentation defects — a domination proof whose stated
  reason did not establish it, an unqualified "never underestimates by a factor of
  two" that walls break, a counterexample claimed as "smallest" when a smaller one
  existed — plus a broken chained comparison in one test and a real
  `StrEnum`-returns-`str` crash when switching editing tools in the combo box
  (`AssertionError` on every tool change; found in Phase 5).

### Tests

Project tests 691 → 854. `tester` added an independent suite (own oracles, no shared
code) and then consolidated it from 337 collected cases to 78 by moving sweeps inside
test bodies — same properties, a quarter of the collection time. Optimality was
checked against two independent references on ~19,000 scenarios, admissibility on
1.36M reachable states, and BFS pop-for-pop against a hand-written FIFO loop.

### Quality gate

`./scripts/fix.sh` then `./scripts/check.sh`: **854 passed**, all checks green.

## 2026-10-05 — Phase 3: random solvable scenario generation

### Agents used

`orchestrator` (coordination, gate, log) and `algorithms` (implementation and its
focused tests). No architect call: the contract was fully determined by `AGENTS.md`
and the task. No tester and no reviewer call — the phase is a single small module and
the risk is low.

### Files created

- `src/ant_pathfinding/generation/scenario_generator.py` — `GenerationRequest`
  (rows, columns, food_count, obstacle_ratio, seed) and `generate_scenario`.
- `tests/unit/generation/test_scenario_generator.py` — 16 cases.

### Main decisions

- **Solvability is guaranteed by connectivity, not by solving the problem.** A flood
  fill of a random anchor cell picks one component large enough to host start, goal
  and foods. No multi-goal search runs during generation.
- **Bounded retries.** At most 100 attempts, then a `ValueError` naming the constraint
  to relax. An explicit failure beats an unbounded loop.
- **The domain stays the authority.** `AntScenario` already validates walkability, so
  generation does not duplicate it.

### Tests

16 focused cases: happy path, zero foods, several foods, obstacle ratios 0.0/0.2/0.5,
seed determinism, the connectivity invariant across 30 seeds, invalid parameters, and
the unsatisfiable-request error. One 10-line local flood fill as the oracle.

### Quality gate

**588 passed**, all checks green.

## 2026-10-05 — Phase 4: first Qt window and grid editor

### Agents used

`orchestrator`, `qt-ui` (all production and test code), and `algorithms` for the entry
point only — `qt-ui` was blocked by its permission scope from editing
`src/ant_pathfinding/__init__.py`. No architect call: the Qt structure was dictated by
the task.

### Files created

- `presentation/qt/editor.py` — `EditTool`, `MIN_SIDE`, `starter_scenario()`,
  `ScenarioEditor`: the draft scenario plus validation.
- `presentation/qt/grid_scene.py` — `GridScene`: cell geometry, graphics items, mouse
  input with snap-to-grid.
- `presentation/qt/main_window.py` — `MainWindow`: toolbar, Generate dock, view.
- `tests/integration/qt/test_editor.py` — 11 behaviour tests.
- `src/ant_pathfinding/__init__.py` — `main()` creates the `QApplication` and shows
  the window. Qt is imported **inside** `main`, so importing the package pulls in no
  Qt and headless tools stay usable.

### Main decisions

- **The domain is the authority on validity.** Every edit builds a draft and
  constructs `Grid` + `AntScenario`; a `ValueError` keeps the previous scenario and
  shows the domain's own message in the status bar. Start and goal are always set, so
  "unset" is unrepresentable; blocking the ant or the goal, or putting food on an
  obstacle, is refused with a visible reason rather than silently repaired.
- **Flat shapes only.** `QGraphicsRectItem` / `QGraphicsEllipseItem` with plain
  colours. No sprites, textures or assets.
- **Rendering is rebuilt, not mutated.** `GridScene.set_scenario` clears and re-adds
  items; Phase 5's overlay therefore had to be re-added after it, not before.

### Verification

Beyond the suite, the app was launched headlessly under
`QT_QPA_PLATFORM=offscreen` and driven through `app.exec()` with a throwaway script
(deleted afterwards), confirming the window constructs, shows and exits 0.

### Quality gate

**599 passed**, all checks green.

## 2026-10-05 — Phase 5: execution and visualization

### Agents used

`orchestrator`, `qt-ui` (implementation and tests), `reviewer` (one final read-only
pass, plus one fix cycle).

### Files created

- `presentation/qt/search_view.py` — `SearchPanel` (run/playback controller + metrics)
  and `SearchOverlay` (one `QGraphicsItem`).
- `tests/integration/qt/test_search_view.py` — 10 cases.

### Main decisions

- **`QTimer` + `runner.step()`, never a thread.** Two timers: a 20 ms search timer
  that advances a configurable burst of 1/10/100/1000 expansions, and a 150 ms
  playback timer that walks the returned path. Run resumes the live runner rather than
  starting a new one.
- **The widget layer consumes the progress stream and nothing else.** No widget builds
  a state, orders a frontier or re-implements a domain rule. The path is read only from
  `runner.result()` after the outcome is `FOUND`, and `result()` is never called while
  a run is live or stopped, where it raises.
- **The frontier is approximated, honestly.** `discovered − expanded` is exact for
  uniform cost; under A* only `discovered − expanded ⊆ frontier` holds. The panel draws
  the difference and says so in one comment, rather than adding an engine accessor for
  a display nicety.
- **The state space is bounded by product, not by each factor.** 100×100 with 9 foods
  is ~5.1M states. Generation is refused above ~2·10⁵ states with a status-bar message.

### Defects found and fixed

- A real crash: `_tool_selected` asserted `isinstance(itemData, EditTool)`, but PySide6
  returns a `StrEnum` member from a combo box as a plain `str`, so changing the editing
  tool raised `AssertionError` every time. Fixed to `EditTool(tool)`.
- A new run did not cancel an in-flight playback, leaving the Play button checked and
  labelled "Pause" and able to walk a path nobody asked for. Fixed in `_clear_visuals`.
- Two buttons both labelled "Step" (search vs. playback); the search one silently
  discarded a found result. Relabelled "Step search" / "Step walk".
- Status-bar messages never expired; they now clear after 5 s.
- `discovered_states` and `frontier_peak_size` were snapshotted every tick and never
  shown. Frontier size is now a metric row; the other two are no longer retained.

### Reviewer verdict

Shippable as an educational visualizer. No pathfinding logic in the widgets, no
`QThread`, no duplicated domain representation, and the progress contract consumed
correctly in every path traced.

### Verification

Headless smoke under `QT_QPA_PLATFORM=offscreen`: generated a map, ran A* to
completion, played the path back (foods collected `2 / 2`, playback disabled at the
goal), stepped exactly 400 times for 400 expansions, confirmed an edited map resets
the run, and confirmed a stopped run reports `stopped` with no result. The console
script was also confirmed to reach the Qt event loop with no traceback.

### Quality gate

`./scripts/fix.sh` then `./scripts/check.sh`: **611 passed**, all checks green.