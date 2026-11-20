# Evolutionary Lab — Product and Implementation Specification

**Status:** Approved baseline after five requirements interviews (47 decisions).  
**Audience:** AI coding agents, maintainers, reviewers.  
**Languages:** Technical docs and code in English; end-user UI and learning content in Spanish.  
**Source of truth:** This specification, with implementation detail in `docs/ARCHITECTURE.md`, deliverables in `docs/ROADMAP.md`, and state in `docs/PROJECT_STATUS.md`.

## 1. Purpose

Build a desktop **interactive laboratory for evolutionary algorithms**. Its purpose is to **teach and demonstrate the mechanisms**, not just compute an optimum. Learners must inspect individuals, genotype-to-phenotype decoding, objective/fitness values, selection probabilities, genetic operators, changing populations, convergence, and diversity over generations.

The academic baseline is *Algoritmos evolutivos: un enfoque práctico* by **Lourdes Araujo and Carlos Cervigón** (Alfaomega / RA-MA, 2009). The user supplied a PDF during planning; a local copy is **not yet known to exist in the repository**. Relevant printed sections: Chapter 2 (genetic algorithms, selection, crossover, mutation and replacement); **Project 1: Optimización de funciones (A), pp. 151–156**; **Project 2: Optimización de funciones (B), pp. 157–162**; and **Appendix B: Solución Proyecto 1, código C++, from p. 295**. Printed page numbers and PDF viewer indices differ. Verify precise algorithms against the scan before claiming fidelity.

The source's **Project 1** uses binary individuals for univariate maximization, minimization and later multivariable optimization. **Project 2** extends function optimization to **real-coded chromosomes**, including uniform/discrete, arithmetic, and SBX crossover concepts. Project 2 is not simply “the multidimensional project”: Project 1 already includes multivariable tasks. The book provides an explicit C++ solution appendix for **Project 1**; do not claim a matching full Project 2 C++ appendix.

### Academic constraints

- Implement encoding, decoding, population initialization, evaluation, roulette/SUS/tournament, one-point crossover, bit-flip mutation, replacement, and the generation loop **from scratch**.
- Visualization, UI, local storage and scientific-array utilities are allowed; GA frameworks performing the teaching-relevant operations are not.
- Provide a **reference/book mode** and **selectable classroom/experimental variants**. Keep original and alternative logic distinguishable in code, presets, and UI.
- Explain formulas and algorithms within the app; avoid obscuring calculations behind external abstractions.
- All mathematical formulas and known optima drawn from the book must be checked on the scanned page. OCR text alone is not authoritative.

## 2. Approved implementation strategy

**Incremental, milestone-driven delivery**. Do not implement every listed capability at once.

### First demonstrable MVP

A working **single-variable maximization** from Project 1, including:

1. A curated set of book functions and simple illustrative functions, each with checked domain and mathematical definition.
2. Binary chromosome generation, decoding, individuals and populations; configurable size and deterministic seed.
3. Fitness evaluation; **roulette wheel, stochastic universal sampling (SUS), and binary tournament** selection.
4. One-point crossover, bit-flip mutation, and selectable reference and conditional parent–offspring replacement.
5. A complete generation loop with validation, bounded execution, and population statistics.
6. A PySide6 desktop shell and PyQtGraph plot of function and individuals.
7. Per-generation navigation, play/pause/step/speed controls, an individual inspector, and best/mean fitness and diversity plots.
8. Honest smoke and automated checks. The MVP must be runnable before adding SQLite, full lessons, or complex exports.

### Approved post-MVP features (phased)

- **Teaching:** theory library, context-aware help, LaTeX-style readable equations, interactive demos and guided exercises (no grading/accounts).
- **Experiments:** SQLite history, reusable presets, save/open generations, compare independent runs, configure retention for large populations.
- **Exports:** CSV, JSON, PNG, SVG and experiment PDF. GIF/video export is a later enhancement.
- **Extended Project 1:** minimization, multiple variables, additional objectives and statistical comparisons.
- **Project 2:** real-coded genotypes, real-domain initialization and mutation, compatible recombination operators including arithmetic and SBX.
- **Later UX:** genealogical explorer, advanced distributions/histograms, 3D surfaces, custom themes and custom functions.
- **Future scaling:** multiprocess execution, third-party plugin loading, external packaging only if subsequently requested.

## 3. Functional model and mathematical rules

### 3.1 Representations and decoding

For a binary unsigned chromosome of length `L`, decimal genotype `g`, and phenotype interval `[a,b]`:

\[
0\le g\le 2^L-1, \qquad x=a+\frac{g(b-a)}{2^L-1}.
\]

For requested resolution `epsilon > 0` and `b > a`, choose an integer `L >= 1` such that:

\[
\frac{b-a}{2^L-1}\le \varepsilon,
\quad\text{equivalently}\quad
L\ge\left\lceil\log_2\left(\frac{b-a}{\varepsilon}+1\right)\right\rceil.
\]

The requested `epsilon` is a **maximum discretization step**, not a promise that every decimal increment `epsilon` is exactly representable. For `[0,1]` with `epsilon = 0.001`, `L = 10` and step `1/1023 ≈ 0.0009775`.

Each individual must expose a genotype, decoded phenotype, **raw objective value**, and **effective selection fitness/weight** separately where they differ. Do not conflate a minimized objective with a positive roulette weight.

### 3.2 Book example function

A verified book Project 1 example (printed page 151, first maximization function) is:

\[
f_1(x)=\sin^6(5\pi x)\exp\!\left[-2\ln(2)\left(\frac{x-0.1}{0.8}\right)^2\right],
\quad x\in[0,1].
\]

The theoretical global maximum is `f(0.1) = 1`. A discrete 10-bit genetic encoding generally approximates, rather than represents, `x=0.1` exactly. This function is a good first visualization because it has multiple peaks. Other book functions require separate source-image verification before registration.

### 3.3 Selection

For roulette selection with valid nonnegative weights `w_i` and positive sum:

\[
p_i=\frac{w_i}{\sum_j w_j},\quad q_0=0,\quad q_i=q_{i-1}+p_i.
\]

Sample `u` uniformly in `[0,1)` and choose the interval `q_{i-1} <= u < q_i`. Precisely define how a zero weight sum or negative/non-finite objective is handled; do not divide by zero or silently reinterpret book behavior. Adaptation/normalization policies must be testable and visible.

For **SUS** selecting `k` individuals, draw one `a` uniformly in `[0,1)` and use:

\[
a_j=\frac{a+j-1}{k},\quad j=1,\dots,k.
\]

For **binary tournament**, randomly select two competitors and choose the one with better adaptation, with an explicit, seeded tie policy. Population selections may contain duplicates. Methods must share an abstract selection contract but not share an incorrect probability model.

### 3.4 Crossover, mutation, and replacement

- Binary one-point crossover: two same-length chromosomes, valid cut `1..L-1`; each offspring receives complementary segments. Handle `L < 2` by rejecting crossover or applying a documented non-crossover policy.
- Bit-flip mutation: each bit is an independent Bernoulli trial with configured `p_mut` in `[0,1]`. Distinguish **probability per bit** from percentage of individuals mutated.
- **Reference algorithm:** the book's simple GA uses roulette, one-point crossover, bit-flip mutation and parent replacement. Reproduce the **actual ordering, sampling decisions, and edge cases** using Chapter 2 and Appendix B, not an assumed generic implementation.
- **Classroom variant:** retain a parent when the corresponding offspring is not better (after computing the offspring's effective objective/fitness according to the problem direction). Document exact pairing, ties, mutation/evaluation order, and how population size stays constant.
- Elitism is a **separate, explicit option**, not an implicit consequence of either strategy; reference mode should not silently enable it.

A selected population of `N` is **not guaranteed to contain `N` distinct genotypes**. With `N=10` and five breeding pairs, be careful about odd selection counts, skipped crossover, and keeping population size constant.

### 3.5 Generations and diagnostics

At each generation, compute at least population size, best/mean raw objective, best/mean selection fitness where appropriate, best-so-far, and a binary diversity measure (e.g., mean pairwise normalized Hamming distance). Fitness stagnation and declining diversity can **suggest** premature convergence, but do not label a local optimum as proven without additional evidence.

Each run uses an isolated `random.Random(seed)`. Store the effective seed with the run. Reproducibility guarantees apply to an unchanged algorithm/configuration/implementation environment, not necessarily across future releases or independent C++ RNGs.

### 3.6 Baseline demo defaults (not quotations from the book)

**Provisional, user-configurable example settings** to launch the first demo:

| Parameter | Suggested value |
|---|---|
| Problem | Verified Project 1 `f1` |
| Domain and requested step | `[0,1]`, `0.001` |
| Population | `10` |
| Generation cap | `100` |
| Selection | Roulette |
| Crossover | One-point; probability `0.70` |
| Mutation | Bit-flip; probability `0.01` **per bit** (1%) |
| Replacement | Book-reference mode |
| Seed | `42`, editable |

These are **demonstration proposals**, not empirically optimal parameters, universal mutation limits, or rates required by the book. The book discusses smaller mutation rates (around `0.1%` in Chapter 2). The user/classroom notes also contain a `0.01%` versus `1%` ambiguity; expose and label the configured rate precisely. Record the chosen defaults in tests/presets and allow later revision.

## 4. Desktop UI and user interaction

- **Native desktop**: Python + PySide6 with PyQtGraph for responsive 2D scientific plotting. Target **Linux and Windows**; no installable binaries are currently required.
- Shell: persistent **sidebar** for sections plus **horizontal tabs** for workspaces in the current section.
- Use `QSplitter`/resizable panels and meaningful presets: Simulation, Analysis, Parameters, Teaching. Default layout must work without customization.
- Design direction: **academic minimalism + technical IDE**, not a colorful gamified interface.
- Appearance: Light, Dark, Follow System. Theme tokens should make additional palettes possible later.
- Spanish UI; centralize user-facing strings for future localization. Do not put Spanish literals inside engine/domain modules.

### Simulation views

- Plot `f(x)` and scatter individuals at their phenotype/objective positions; highlight selected and best individuals without implying impossible physical movement.
- Show generation index and controls: start, pause, stop, reset, previous/next, seek to a generation, and configurable playback speed. Animations are smooth but **optional/disablable**.
- Individual inspector: identifier (scoped to generation/run), binary genotype, decimal value, decoded phenotype, objective, effective fitness, generation, selection data and known parentage/mutations where recorded.
- Plot best and mean fitness/objective and diversity; additional charts are later extensions.
- Adaptive display: preserve full data while using smaller/transparent points or density visualization for large populations.
- Interactive explanations should connect a selected method to the actual formulas and parameters used. Avoid fake demo numbers being shown as live results.

**Replay distinction:** Persist **complete generation snapshots** (subject to later configurable retention) but not necessarily every detailed crossover/mutation event. In-session operation-by-operation playback can use an **ephemeral event trace**. Reopening an archived run guarantees generation-level review only unless operation events were explicitly saved; the UI must communicate that limitation.

## 5. Experiments and presets (post-MVP)

- SQLite local persistence, schema versioning/migrations, and data access via adapters; never treat a GUI table as canonical experiment storage.
- A **preset stores configuration, not execution results**: schema version; name/description; project/problem/function ID; optimization direction; domains and resolution; encoding and length; initialization; population size; selection and parameters; crossover and rate; mutation and rate/unit; replacement/elitism; stop criteria; and **seed policy** (fixed value versus automatic).
- A **run stores effective settings and actual seed**, application/algorithm versions, status, timestamps, summary metrics, saved generation populations and experiment-related metadata. Never overwrite a past run just because a preset is edited.
- Complete snapshots by default for small runs; estimate size, warn for large runs and allow a retention setting without silently discarding history.
- Compare independent runs with charts and parameter summaries; synchronized dual-engine playback is **not** required.
- Export JSON, CSV, PNG, SVG, PDF after those milestones are reached. GIF/video later.

## 6. Engineering, integrity, and acceptance

- Use `uv`, Python 3.12 initially; quality tools: Ruff, mypy, pytest and targeted property testing when useful.
- Tests cover mathematical invariants, numerical boundaries, deterministic seeds, operator behavior, algorithm integration, storage round-trips, and UI smoke checks.
- Full costly suites run at major milestones or release gates, not after every tiny edit.
- Use Conventional Commits per verified milestone; no remote publication, no invented co-authors, no out-of-repository modifications without permission.
- Preserve a small `docs/PROJECT_STATUS.md` handoff and a concise milestone-oriented `docs/ROADMAP.md`.
- Do not claim the program supports a planned feature until it is working and verified.

## 7. Explicit non-goals in the initial development cycle

No deep learning or GA frameworks; no cloud/backend/accounts; no browser-first web UI; no executable installers; no full multivariable/3D rendering in the first demonstrable MVP; no automated grading; no untrusted Python execution; no elaborate external plugin loader; no routine full mutation-test campaigns.

## 8. References and source traceability

Document the printed chapter/page associated with each book-origin operator and function. Distinguish three origins: **book-verified**, **instructor/classroom variant**, and **application-specific enhancement**. Include source comparisons and test cases where practical, but exact automated C++/Python parity is **not a prerequisite** (different random generators may make outputs differ). Keep the copyrighted PDF local and untracked. If a formula is uncertain, label it `needs source verification` and do not ship it as a verified reference.
