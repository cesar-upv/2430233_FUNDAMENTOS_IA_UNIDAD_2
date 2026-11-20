# Project Status — Agent Handoff

**Last updated:** 2026-10-14\
**Completed:** M00–M11, M01.1, M11.1, M18–M19 and M21–M23\
**Boundary:** M23 complete. Stop here; M12–M17 and M20 remain deferred.\
**Implementation:** Verified objective catalogue runs in Qt with binary or real encoding.

## Repository

- This session started clean at `71181b2` (approved M19); M18 was `f40b085`.
- M21: `0bbc92f`; M22: `18a9af7`; M23 is the latest milestone commit (see Git log).
- Python 3.12, existing dependencies and lockfile preserved. No GA framework added.
- No push/publication. PDF, preferences and screenshot artifacts remain ignored.

## Project 2 (M21–M23)

- Immutable real vectors have one finite component per variable, independent domains
  and no binary discretization precision. Initialization uses the injected Random.
- Uniform mutation applies a configurable Bernoulli decision per variable, followed by
  a uniform reset in that variable's domain. Decisions and reset draws are retained.
- Real one-point crossover cuts between components; active D=1 is rejected and the GUI
  omits this choice. Uniform masks produce complementary children. Arithmetic crossover
  uses a configured alpha in [0,1]. SBX draws one beta per pair for all components.
- SBX literal mode preserves the printed lower branch `2*u**(1/(n+1))`; the separately
  named continuous extension uses `(2*u)**(1/(n+1))`. Default index n=1 follows Project 2.
- SBX can exceed domains. Explicit clip (default) and reject/stop policies are application
  choices, not book rules. Non-finite children fail; raw children and repairs are traced.
- The shared engine supports all three selections, both replacements, min/max and
  multiple variables. Real runs use consecutive pairs; an odd final slot is still mutated.
  Implementation version is `genetic-ga-v4`; binary scheduling/RNG results are preserved.
- Real diversity is average pairwise L1 distance, normalized per domain and averaged
  over variables. Range 0..1; singleton/identical population = 0. It is distinct from
  Hamming, whose field stays unset for real runs. Calculation takes O(D*N*log N).
- GUI project selector configures representation and compatible operators; no binary
  precision appears for real runs. Operator settings are contextual and validated.
- Existing parameter groups, responsive columns/scroll, primary Run, worker, plots,
  themes, navigation, cancellation and timer replay are reused. Calculations stay off UI.
- Inspectors show real genes, fitness, attempted crossover/reset metadata and repairs,
  retaining the distinction between attempted children and conditional parent retention.
- Source checks: `PROJECT_02_VERIFICATION.md`; formulas verified visually against PDF.

## Project 1 compatibility

- Shared catalogue: four univariate maxima, three univariate minima and four
  multivariable families. Variable-dimensional families allow 1..10 variables in GUI.
- Binary segments retain independent domains/precision and per-variable cuts; mutation
  positions remain LSB-based. Raw objectives and selection weights stay separate.
- Minimization uses literal `1.05*cmax-g` or the named signed extension. Best-so-far and
  classroom replacement compare raw objectives; no implicit elitism or transformations.
- f1 seed 42 remains compatible: best-so-far=0.9999361576410012,
  final best=0.9923013444564796 (covered by regression tests).
- One variable uses curves, two use sampled heatmaps, higher dimensions use normalized
  parallel coordinates. Inspector and statistics follow the selected frozen snapshot.

## Actual validation

- M21: 53 directed tests. M22: 107 directed tests and real f1 with 101 snapshots.
- M23 directed GUI suite: 9 passed; all four operators, single/multiple variables,
  independent domains, custom settings, min/max, replay/themes, reject errors, binary return.
- Real diversity: 5 directed tests, including direct pairwise mathematical comparison.
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: passed (88 files).
- `uv run mypy src`: passed (51 source files).
- `uv run pytest -o faulthandler_timeout=15`: 358 passed in 38.95 seconds.
- Installed-entry native Wayland smokes: Project 2 f1/SBX, Rastrigin 2D/arithmetic,
  sine-root 3D/SBX and Project 1 f1. Each runs 100 transitions twice, compares all
  101 snapshots, checks objectives/bounds/statistics/inspection and exercises timer replay.
- Light/dark native captures and 900×740 offscreen run passed. No relevant QObject/QThread
  errors; existing Wayland text-input warnings are nonblocking. No new suite stalls.
- M19 previously had an intermittent offscreen PyQtGraph text-layout stall; unresolved
  cause remains historical, not claimed fixed by this work. Windows remains untested.

## Artifacts and limitations

- Simulation/Analysis/Parameters: `output/gui/m23-real-f1*.png`, `m23-real-2d*.png`,
  `m23-real-3d*.png`; binary regression captures: `m23-binary-f1*.png`.
- Minimum-size real captures: `output/gui/m23-real-minimum*.png`.
- Fourth univariate minimum remains excluded: inconsistent printed exponential overflows
  on the stated domain. No correction guessed; see `PROJECT_01_VERIFICATION.md`.
- History remains in memory (GUI limit 100,000 individuals). No persistence/export,
  parameter studies, new teaching modules or 3D surfaces were implemented.
