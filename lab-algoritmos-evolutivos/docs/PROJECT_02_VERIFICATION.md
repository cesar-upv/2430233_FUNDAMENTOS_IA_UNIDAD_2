# Project 2 source checks

Verified visually against the ignored local PDF; page numbers are one-based.

## M21

- Printed pp.157–158 / PDF pp.155–156: one floating-point component per variable;
  initialize each component uniformly within its own interval. Objectives are the same
  as Project 1; real representation has no binary discretization precision.
- Printed pp.161–162 / PDF pp.159–160: uniform mutation replaces a selected gene with
  a new uniform value from its allowed interval. The application applies a configurable
  Bernoulli decision to each variable, recording decisions and replacement draws.
- Invalid input chromosomes are rejected before consuming randomness. Uniform samples
  clamp only endpoint floating-point rounding. General offspring bounds policies are
  explicitly named reject/clip; clipping is application behavior, not a book SBX rule.
- Chromosomes/results are immutable. The supplied Random instance is consumed without
  reseeding or using module-global randomness. Replacement may draw the same old value;
  mutation metadata records attempted gene resets.

## M22

- Printed p.159 / PDF p.157 refers one-point crossover back to Chapter 2; Chapter 4
  printed p.108 illustrates a cut between real components. We use internal cuts 1..D-1;
  an active one-point operator on D=1 is rejected. This safe cut policy is explicit.
- Printed p.160 / PDF p.158: uniform crossover swaps each matching component with its
  own configured probability and produces complementary children. Arithmetic crossover
  uses alpha*p1+(1-alpha)*p2 and its complement, with a fixed configurable alpha in [0,1].
- Printed p.161 / PDF p.159, corroborated by Chapter 4 printed p.111 / PDF p.109:
  the first SBX branch is typeset `2*u**(1/(n+1))`, without parentheses around 2*u.
  Literal mode preserves that expression. The separately named continuous variant uses
  `(2*u)**(1/(n+1))`. Both use `(1/(2*(1-u)))**(1/(n+1))` when u>=0.5.
  No silent correction is made. The scan uses n=1; configurable nonnegative n is exposed.
- SBX draws one u per pair before the component loop, then generates
  `(p1+p2)/2 +/- beta*abs(p2-p1)/2`. Stable midpoint arithmetic avoids intermediate sums.
- The source supplies no SBX boundary repair. Named clip (default) and reject policies
  are application choices; reject stops the run on an invalid child. Non-finite values
  always fail. Traces retain raw children, repaired coordinates, beta/u, masks and cuts.
- Real operators use one crossover probability per consecutive pair; an odd last slot
  is still mutated. The existing selection/evaluation/replacement/snapshot loop is shared
  with binary runs. Binary reference scheduling and its RNG sequence are preserved.

## M23

- Both projects reuse the verified objective catalogue: the Project 2 introduction
  explicitly asks to repeat the Project 1 functions. Stable objective IDs stay unchanged.
- Real diversity is an application statistic, not a book formula: average absolute
  coordinate distance divided by each domain width, then averaged over variables and
  unordered pairs of individuals. It is bounded by 0..1; duplicates count as separate
  individuals and a singleton gives zero. It is not equivalent to Hamming distance.
- GUI hides binary precision for real runs and one-point crossover for a single variable.
  SBX literal/continuous formulas and clip/reject behavior are explicitly labeled.
  The same worker, plots, history and direction-aware replacement serve both projects.
