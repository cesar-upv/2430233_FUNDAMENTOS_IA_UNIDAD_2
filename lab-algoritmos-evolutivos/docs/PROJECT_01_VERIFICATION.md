# Project 1 source checks

Verified visually against the local scan, using one-based PDF page numbers.
The PDF is ignored and must not be committed. Function IDs are application names.

## M18: minimization

- Printed p.153 / PDF p.151: `min1 = 1 + cos(x)/(1+0.01*x²)`, [0,50];
  `min2 = -abs(x*sin(sqrt(abs(x))))`, [-250,250];
  `min3 = sin(x)/(1+sqrt(x)+cos(x)/(1+x))`, [0,25].
- Printed p.154 / PDF p.152: revise all selection weights each generation using
  `w = 1.05*cmax - g`, with `cmax` the current population's largest raw objective.
  The literal policy rejects negative cmax rather than producing invalid weights.
- Named signed extension: `w = cmax + 0.05*abs(cmax) - g`. It equals the literal
  formula for nonnegative cmax and preserves minimization ordering for negative cmax.
  This extension is application behavior, not attributed to the book. All-zero weights
  retain the explicit error/uniform selection policy. Non-finite offsets/weights fail.
- Objectives determine replacement and best-so-far; generation-relative weights must
  not be compared across generations. Revision reuses stored raw objective values.
- The fourth minimization expression on printed p.153 appears as
  `5 + exp(0.5*pi*x²) - exp(0.1*x*cos(pi*x))`, [0,25]. It contradicts the stated
  minimum near x=23.9901 and overflows binary64 within that domain. It is excluded
  pending source clarification; no guessed sine or other correction is substituted.

## M19: remaining verified functions and binary variables

- Printed pp.151–152 / PDF pp.149–150: `f2 = 20+e-20*exp(-0.2*abs(x))
  -exp(cos(2*pi*x))`, [0,32]; `f3 = x+abs(sin(32*pi*x))`, [0,1];
  `f4 = 0.5-(sin(x)^2-0.5)/(1+0.001*x^4)`, [0,10].
  f2 uses an equivalent expm1 expression to preserve its exact nonnegative zero.
- Printed p.154 / PDF p.152: radial two-variable maximum on [-40,40]^2,
  `0.5-(sin(sqrt(x1^2+x2^2))^2-0.5)/(1+0.001*(x1^2+x2^2)^2)`.
  The denominator is transcribed as printed, not replaced by another benchmark variant.
- Printed p.155 / PDF p.153: Rastrigin on [-5.12,5.12]^n; negative sine-power sum
  on [0,pi]^n; negative `sum(x_i*sin(sqrt(abs(x_i))))` on [0,100]^n.
  The sine-power formula uses `(i+1)*x_i^2/pi`, i=1..n, exactly as printed;
  it yields -1 for n=1 at pi/2. No conventional index substitution is made.
- Printed pp.155–156 / PDF pp.153–154: per-variable binary chains and lengths,
  vector decoding, mutation over all variables and crossover between variable chains.
  The first printed crossover example appears to pair x1 with x2, then repeats x2.
  The implementation explicitly pairs corresponding variables to preserve independent
  domains and lengths; it does not claim to reproduce that apparent misprint literally.
- BinaryGenotype stores immutable flattened LSB-first segments plus their lengths;
  BinaryVectorEncoding reuses the scalar encoding for every variable. Scalar RNG draws
  remain unchanged. Reference scheduling draws one generation-wide cut per variable;
  pairwise scheduling draws one probability per pair and a cut per variable. This cut
  scheduling is the application's extension of the scalar reference, not C++ parity.
- Raw objective curves, 161×161 heatmaps and domain-normalized parallel coordinates
  are visualization adapters. Sampling/evolution run in the worker, without Qt in core.
- Catalogue: four univariate maxima, three univariate minima and four multivariable
  families. GUI families support 1..10 variables; the engine is not tied to that UI cap.
