# Architecture and Extension Contracts

**Status:** Initial architecture baseline. Preserve clear boundaries but implement only what the current milestone needs. The files below are planned locations, not a claim that all modules already exist.

## 1. Design goals

- The evolutionary algorithm is a **pure-Python, Qt-independent engine**.
- Selection, crossover, mutation, replacement, encoding, and objective functions are independently testable and, where valid, interchangeable.
- A runner produces reproducible **generation snapshots** and optionally operation events for the live teaching view.
- The GUI is an adapter that receives results and draws them; it never owns algorithm state.
- Storage can be introduced later without redesigning domain objects or the engine.
- New problems may be registered internally; a third-party plugin loader is **out of scope** for the first version.

## 2. Target package map

```text
src/evolutionary_lab/
├── __init__.py
├── domain/                 # Immutable-ish domain models, configuration, validation
├── evolution/
│   ├── encoding/           # Binary first; real-coded later
│   ├── selection/          # Roulette, SUS, binary tournament
│   ├── crossover/          # One-point first; real-coded later
│   ├── mutation/           # Bit-flip first; real-coded later
│   ├── replacement/        # Reference parent replacement and classroom variant
│   ├── engine.py           # Pure evolution orchestration
│   └── statistics.py       # Best, mean, diversity
├── problems/
│   ├── project_01/         # Verified functions; later min/multivariable
│   ├── project_02/         # Future real encoding/functions
│   └── registry.py         # Internal catalogue / metadata
├── simulation/
│   ├── runner.py           # Scheduling, cancellation, controlled RNG
│   ├── snapshots.py        # Generation replay contracts
│   └── events.py           # Ephemeral live operation events
├── application/            # UI-independent use cases and coordination
├── presentation/
│   ├── windows/            # Sidebar + tabs shell
│   ├── widgets/            # Inspector, controls, tables
│   ├── plotting/           # PyQtGraph adapters
│   └── viewmodels/         # Presentation state mapping
├── education/              # Concepts, formulas, guided exercises
└── persistence/            # Future SQLite and import/export adapters

tests/
├── unit/
└── integration/
docs/
```

These subdirectories should be created **when needed**, not generated as empty scaffolding en masse. Existing initialized top-level packages are authoritative.

## 3. Domain entities and invariants

**ExperimentConfig** (versioned/configurable): problem identifier and direction; encoding and domains; population and generation limits; rates and their units; operator names/settings; elitism; seed policy; history-retention policy. Validation must fail early on incompatible or invalid selections.

**Individual**: stable identity *within a run/generation*, representation-specific genotype, decoded phenotype (`tuple[float, ...]` to support future multivariable tasks), raw objective result, and optional effective selection fitness. Treat genotype and interpretation as separate concepts; avoid a permanent assumption of exactly one real `x`.

**Population**: ordered collection with configured size; selection may repeat the same genotype. Child identity/parentage is tracked when available without making full lineage storage mandatory.

**GenerationSnapshot**: generation index, independent copy of all individual values (not references to mutable current individuals), configuration/run identity, and derived statistics. The first snapshot is generation `0`. It must remain valid even as later generations evolve.

**OperationEvent**: ephemeral event for selection/draw/probability, parent pairing, crossover cut and offspring, bit mutation, evaluation, and replacement. Events are suitable for live teaching playback, not initially part of the persistent history guarantee.

**RunRecord** (later): persisted run ID, schema and algorithm versions, configured/actual seed, status, timestamps, results, selected snapshots, and storage policy.

### Implemented foundation (M02)

- `domain/models.py` defines immutable intervals, binary/real genotype value objects, individuals and ordered populations. Collections are copied to tuples; population identities are unique, while genotypes may repeat. M21–M23 add real-coded operators and execution to the original real data contract.
- Individuals retain a vector phenotype, optional finite raw objective and separate optional nonnegative `selection_fitness`. M04 evaluates decoded phenotypes and assigns weights only through an explicit policy; decoding remains a separate operation.
- `domain/config.py` validates per-variable domains and positive finite precision, population size, generation limit and integer seed. Generation limit zero allows the initial population only; integer seeds may be signed. `validate_for(problem)` checks identity, direction, representation and search-domain compatibility. M07 adds selection, reproduction/replacement and fitness policies, rates and tie/zero-weight settings.
- Precision means the requested maximum discretization step; it never rounds the continuous objective or phenotype. Binary length calculation/decoding/initialization belong to M03.
- `domain/problems.py` provides the `ObjectiveFunction` callable protocol and `OptimizationProblem.evaluate`, which validates vector dimensions, closed bounds and finite results. Internal validation exceptions are `ValueError`; presentation will own localized messages when these APIs reach the GUI.
- `problems/registry.py` exposes a read-only catalogue and `get_problem`. The original entry, `project_01.f1`, declares binary reference compatibility, the continuous optimum `(0.1,) -> 1.0`, Spanish metadata and book provenance. Its mathematical callback is independent of genotype representation.

### Binary encoding and initialization (M03)

- `evolution/encoding/binary.py` converts binary genotypes, strings and unsigned integers. `bits[0]` has weight 1, as verified in the book's `bin_dec` (printed p.301 / PDF p.299); display strings are most-significant-bit first and retain leading zeros.
- `chromosome_length(domain, precision)` computes the minimum positive length satisfying `(b-a)/(2**L-1) <= precision` with exact rational/integer arithmetic, avoiding logarithm rounding. The exact values of the supplied float bounds/precision are used.
- Immutable `BinaryEncoding(domain, length)` implements the affine mapping with exact endpoints. Inverse encoding selects the nearest grid point; exact ties select the larger integer. This inverse rounding rule is application-defined, not quoted from the book. Resolution and half-step quantization bounds are mathematical; decoded values have normal final binary64 rounding.
- Encoding rejects grids finer than the largest interior float spacing, preserving distinguishable decoded values and round trips rather than silently claiming unsupported precision. A one-bit encoding always represents the two valid endpoints.
- `evolution/initialization.py::initialize_population(config, problem, rng)` validates before drawing, then returns generation 0 at the configured size, with unique identifiers and possible repeated genotypes. The caller supplies a fresh `Random(config.seed)` for a reproducible run; a supplied RNG is consumed, never reseeded or replaced. Objective/selection fitness stay `None` until M04. M19 initializes one independently sized binary segment per variable.
- The mathematical decoding formula and bit order were checked against the scanned source; Python arithmetic and RNG streams are not claimed to reproduce the C++ implementation bit for bit.

### Evaluation and population statistics (M04)

- `domain/evaluation.py` defines `FitnessPolicy` and immutable `PopulationStatistics`. Evaluated results reuse the existing immutable `Individual` and `Population` models.
- `evolution/evaluation.py` evaluates the stored decoded phenotype through `OptimizationProblem.evaluate`, checks representation compatibility and returns new values without changing identifiers, ordering, genotypes or generation index. Re-evaluation replaces both objective and fitness, including clearing stale weights.
- The default `NONNEGATIVE_IDENTITY` policy requires maximization and finite nonnegative objectives; for verified f1, selection fitness equals the raw objective. `OBJECTIVE_ONLY` preserves signed objectives and leaves fitness unset. M18 adds explicit population-relative minimization policies; no silent objective transformation is used.
- `evolution/statistics.py` ranks best/worst by **raw objective and optimization direction**, keeping the first population member on ties. Objective minimum/maximum/mean and selection-fitness minimum/maximum/mean are separate; fitness must be present for all members or absent for all. Finite means remain valid even when a naive intermediate sum would overflow.
- Binary diversity is the mean normalized Hamming distance over unordered pairs of distinct **individuals**, including repeated genotypes: `sum_locus(k*(N-k)) / (L*N*(N-1)/2)`. Counting differing pairs per locus takes O(NL) time. A singleton or identical-genotype population has diversity zero; real-genotype statistics leave this binary-only metric unset.
- Statistics describe the current population, not a continuous/discrete global optimum or run-wide best-so-far. Zero selection weights are valid evaluation data; sampling policy for a zero total belongs to M05.

### Selection and binary variation (M05–M06)

- `domain/selection.py` exposes a shared callable selection contract and frozen results.
  Selections may repeat immutable individuals; indices point into the source population.
- Proportional selection requires explicit nonnegative weights; zero total uses named
  error/uniform policies. Cumulative boundaries include 0 and 1 with half-open intervals.
- SUS retains its draw/pointers; tournaments retain competitors/winners/tie draws, rank
  effective fitness or direction-aware objectives and sample competitors with replacement.
- `domain/variation.py` exposes frozen genotype-level operator traces. Binary operators
  accept the genotype union and reject unsupported representations before random draws.
- Per-pair crossover uses internal cuts 1..L-1; active crossover requires L>=2.
  `cross_at_point` separately allows book endpoint cuts 0..L through explicit opt-in.
- Bit-flip mutation consumes one draw per bit, including rates 0/1. Cut and mutation
  positions count from the internal LSB-first gene order, not the display string.

### Numerical principles

- Keep **objective value** separate from **selection weight/fitness**; this is crucial for minimization and negative functions.
- Reject non-finite objective results and invalid bounds. Define behavior for zero sum of roulette weights and all-equal competition as an explicit named policy.
- Binary decoding must satisfy lower/upper endpoints exactly up to floating-point tolerance and maintain precision-step bounds.
- Keep tie behavior deterministic under a seed, and keep references to the book's actual sampling algorithm when working in reference mode.
- Never assume `best_fitness(t)` is monotonically increasing in the *current generation* when the configured replacement does not preserve the best individual. A separate `best_so_far(t)` metric is monotonic for maximization.

## 4. Operator contracts

Prefer narrow `typing.Protocol` contracts over inheritance hierarchies. The example signatures below are **illustrative**, not fixed API commitments:

```python
from random import Random
from typing import Protocol


class SelectionOperator(Protocol):
    def select(
        self,
        population: "Population",
        count: int,
        rng: Random,
    ) -> list["Individual"]: ...


class CrossoverOperator(Protocol):
    def crossover(
        self,
        parent_a: "Genotype",
        parent_b: "Genotype",
        rng: Random,
    ) -> tuple["Genotype", "Genotype"]: ...


class MutationOperator(Protocol):
    def mutate(self, genotype: "Genotype", rng: Random) -> "Genotype": ...
```

Use an operator **registry** that declares supported genotype representations and required configuration. Validate compatibility before enabling or running an operation, e.g., do not apply `bit_flip` to a real-coded vector or SBX to a binary bit string.

Keep function/problem definitions in the problem registry with verified `id`, title, bounds, direction, known optimum (if grounded), formula/description in Spanish, and a pure evaluator. Do not embed PyQtGraph objects in problem definitions.

### Book fidelity profile

The reference configuration uses roulette, `BOOK_REFERENCE` reproduction/replacement,
identity fitness and bit-flip mutation, with no implicit elitism. SUS/tournament and
`PAIRWISE` reproduction are explicit alternatives, including when direct parent
replacement is selected. Replacement strategy alone does not identify full book mode.

M07 visually verified Chapter 2 printed pp.38–39, 44–46 (PDF pp.36–37, 42–44),
and Appendix B printed pp.298–300, 302–303 (PDF pp.296–298, 300–301):

- Reference selection creates an ordered intermediate population. Reproduction draws
  once per individual, pairs eligible slots consecutively and drops the final odd candidate.
  A generation-wide cut is drawn even if no pairs are eligible.
- Chapter 2 specifies cuts 0..L, including whole-chromosome swap/copy. These safe bounds
  are implemented explicitly. Appendix B's expression admits L+1 and out-of-bounds access;
  it is not reproduced. Pairwise crossover instead uses internal cuts 1..L-1.
- Reference crossover children are evaluated and directly replace their selected parent
  slots before mutation. All slots, including unpaired/skipped slots, then undergo mutation;
  changed individuals are decoded/evaluated before final statistics.
- Classroom replacement compares the fully mutated/evaluated child against its
  **selected** corresponding parent. Strict objective improvement follows problem direction;
  ties retain the parent. Selection can still lose a previous generation's best individual.
- The appendix adds 2% elitism, whereas Chapter 2's simple GA does not. M07 implements
  the latter without silently copying the appendix's elite conditions.
- Half-open roulette intervals resolve source boundary ambiguity and skip zero weights.
  Safe bounds, Python numerics/RNG and application policies preclude bit-for-bit C++ parity.

## 5. Evolution and replay pipeline

```text
Validated configuration + problem + isolated RNG
    -> initialize population
    -> evaluate / normalize selection weights
    -> GenerationSnapshot(0)
    -> generation loop:
         selection -> crossover -> mutation
         -> evaluation -> replacement (variant-specific order)
         -> statistics -> GenerationSnapshot(n)
    -> completion / cancellation / failure
```

The reference workflow must respect the ordering implemented in the source; do not force the generic flow above onto the original algorithm if its evaluation or replacement sequence differs. The classroom mode should apply improvements only after the offspring has been evaluated.

### Implemented engine (M07)

`evolution/engine.py` exposes `iterate_generations(config, problem)` and
`run_evolution(config, problem)`. The first yields generation 0 followed by exactly
`generation_limit` transitions; the second collects them in an immutable `EvolutionResult`.
Configuration/operator compatibility and encoding limits are checked before RNG creation.
The engine owns one isolated `Random(config.seed)` and passes it explicitly to operators.
M19 executes binary vectors with independent domains/precision; real-coded algorithms remain deferred.

Snapshots in `simulation/snapshots.py` contain immutable population values, configuration,
implementation version, statistics and best-so-far with its first observed generation.
IDs identify generation-local slots; selection traces preserve source individuals/indices.
Best-so-far ranks recorded generation populations, retaining the earlier result on ties.
`simulation/events.py` retains actual in-session selection, pairing, mutation, evaluated
offspring and replacement traces; `replacement_before_mutation` specifies the event order.
Sharing frozen value objects between snapshots is safe; no mutable engine state is exposed.
History/trace retention and persistent replay remain later milestones.

Headless demo API:

```python
from evolutionary_lab.domain.config import ExperimentConfig
from evolutionary_lab.evolution.engine import run_evolution
from evolutionary_lab.problems.registry import PROJECT_01_F1

config = ExperimentConfig(
    PROJECT_01_F1.identifier, PROJECT_01_F1.domains, (0.001,), 10, 100, 42
)
result = run_evolution(config, PROJECT_01_F1)
```

**Replay model:** save a full immutable generation snapshot so the UI can move forward/backward without rerunning evolution. For live sub-generation playback, stream ephemeral operation events as they occur; if they are not persisted, archived runs cannot guarantee exact step-by-step genetic-operation replay. Never portray reconstructed events as originals.

**Data volume:** if storing `N` individuals for `G+1` generations, history grows roughly with `O(NG * genotype size)`. In later milestones, implement size estimation and user-visible sampling/retention options. Do not silently drop data.

## 6. Qt threading and visualization

- Only the **main Qt thread** creates/manipulates widgets and plot items.
- Run longer computation via a `QObject` worker on `QThread` (or a comparably safe pattern), communicate with Qt signals using plain domain snapshots/event DTOs, and support cooperative cancellation.
- Avoid one UI signal per bit for large populations; batch progress updates and allow rendering throttling independently from simulation speed.
- PyQtGraph shows `f(x)` curve and scatter of individual phenotypes; update reusable plot items rather than recreating full scenes every frame.
- Individual inspection must use domain snapshot data, not plot coordinates as the authority.
- Use `QSplitter` for resizable layouts, sidebar navigation, horizontal tabs and configurable animation speed. The Qt UI must remain responsive during computation.
- Localizable text stays at the presentation/education layer, ideally behind a simple translation key/helper, enabling future `QTranslator`/Qt Linguist catalogs.

### Delivered desktop adapter (M08–M11)

- `presentation/workers.py` runs curve evaluation and the existing generation iterator on
  a QObject/QThread worker. Queued signals deliver frozen snapshots in batches of at most
  32 (or approximately every 40 ms); no widgets/plots are touched from the worker.
- Cancellation checks interruption before the next generation; reset discards late results.
  Failure preserves valid buffered snapshots. Close requests cancellation and joins before
  destroying QObject ownership. Generation-local work is the cancellation boundary.
- The simulation view keeps in-memory history; a separate QTimer handles replay only.
  Seeking/pausing/speed changes never reseed or rerun the engine.
- Parameter input reuses public `validate_configuration` before worker creation. Percent
  controls convert to probabilities once; mutation is per bit. Form edits affect the next run.
- Desktop limits are 500 members, 2000 transitions and 100,000 retained individual states;
  the headless engine's contracts are unchanged. Persistence/retention controls remain deferred.
- Population/inspector and fitness/diversity plots use snapshot values and existing theme
  tokens. Generation selection synchronizes the plots and attempted-operation metadata.
- Minimum size is 900×740; inspector labels wrap and parameter/metadata panels scroll.
- `scripts/smoke_gui.py --simulate` exercises the installed entry point, two seeded worker
  runs, navigation, a real replay timer, inspector/statistics and optional native PNG captures.

## 7. Persistence and presets (later milestones)

Use SQLite through a repository/adapter boundary; start with `sqlite3` from the Python standard library unless a real need justifies more. SQLite schema and migration IDs must be versioned. Write persistent data atomically where possible and handle cancellation/partial runs.

Proposed tables/concepts, subject to evolution: `presets`, `runs`, `generation_snapshots`, `run_statistics`. Keep large event traces opt-in, rather than requiring permanent `operation_events` initially.

A **preset** includes name/description, schema version, problem/optimization direction, variable domains and precision, encoding, population size, operator IDs and parameters, termination criteria, seed policy, and applicable display-independent execution settings. It **does not** include results, runtime events, or a historical population. A run stores resolved effective seed and configuration snapshot, with results. Changing a preset never rewrites a past run.

Exports (JSON, CSV, PNG, SVG, PDF) must be created from run data and verified snapshots. PNG/SVG/plotting dependencies are UI concerns; PDF generation belongs to an export adapter. Importing presets from JSON requires strict schema validation.

## 8. Testing strategy

**Unit:** binary encode/decode endpoints and resolution, bit-flip invariants, probability sums, SUS equal spacing, tournament winner/ties, cut validity, replacement decisions, statistic correctness, malformed configurations.

**Integration:** known objective function with deterministic seed, complete generations, fixed population size, replay accuracy, responsive cancellation, and (later) save/reload equality.

**GUI smoke:** launch and render main shell, switch sidebar and top tabs, update plot, inspect a real individual, start/pause/seek without Qt cross-thread errors. Capture screenshots when the runtime supports it; don't invent screenshot evidence.

**Major gates only:** broad Hypothesis suites, large-population performance, longer stochastic regressions and cross-platform smoke runs. Avoid timing-sensitive assertions for stochastic convergence; test determinism and structural guarantees first.

## 9. Extension checklist

To add a new operator: (1) implement a pure class/function against its contract, (2) declare representation compatibility and parameters, (3) register it, (4) add unit/edge-case tests, (5) add Spanish UI metadata and equation/demo if teaching-relevant, (6) update the roadmap/status, (7) preserve existing preset/run compatibility.

To add a new problem: verify its formula/domain/reference, add a pure evaluator and metadata, test known sample values/optima within appropriate tolerance, register it, and expose it in the GUI without modifying the engine.

Keep changes small, readable and reversible. When actual implementation establishes new constraints, update this document instead of creating duplicate architectural specifications elsewhere.

### Project 1 extension (M18–M19)

- Literal minimization weights are `1.05*cmax-g`; a separately named signed extension
  uses `cmax+0.05*abs(cmax)-g`. Revision uses the final population after replacement,
  reuses objectives and preserves the explicit zero-weight policy. Raw objectives rank
  survivors and best-so-far; weights from different generations are not comparable.
- BinaryGenotype retains segment lengths; BinaryVectorEncoding reuses scalar mappings.
  Crossovers pair corresponding segments and keep per-variable cut metadata; mutation
  records flattened positions that the inspector maps to variable-local LSB positions.
- The registry supports verified fixed-dimensional problems and variable-dimensional
  families; get_problem(id, dimensions) creates the latter's immutable problem value.
- Workers sample scalar curves or two-dimensional grids; higher-dimensional populations
  use domain-normalized parallel coordinates. Analysis compares raw objectives; selection
  fitness and current cmax remain available in the inspector. History is never recomputed
  for replay. Parameter edits affect the next run, not an existing snapshot.
- Source differences, rejected formulas and application cut scheduling are documented
  in `PROJECT_01_VERIFICATION.md`; no full C++/RNG parity is asserted.

### Project 2 integration (M21–M23)

- Real runs use empty precision, one gene per variable and explicit uniform reset mutation.
  Pairwise real crossover dispatches within the existing engine; selection, evaluation,
  replacement and immutable snapshots are shared. Binary scheduling/RNG remains unchanged.
- One-point cuts between variables; uniform crossover records its complementary mask;
  arithmetic uses configured alpha; SBX records a shared pair draw/beta and raw children.
  Literal/continuous SBX and clip/reject bounds policies are named separately; see
  `PROJECT_02_VERIFICATION.md` for the verified source and application choices.
- Real diversity is mean pairwise, per-variable domain-normalized L1 distance:
  `sum_{i<j} sum_k abs(x_ik-x_jk)/(b_k-a_k) / (D*N*(N-1)/2)`.
  Identical populations/singletons give zero. Sorting coordinates and summing adjacent
  gaps computes this in O(D*N*log N). It is distinct from binary Hamming diversity;
  the binary metric stays unset for real runs.
- Project selection chooses representation and compatible controls, using the same
  objective catalogue, worker, plots and replay. Inspectors retain attempted operator
  metadata even when classroom replacement preserves a parent. Settings affect new runs.
