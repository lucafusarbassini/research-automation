# Toy Problem: Comparing Numerical Integration Methods

## Research Goal

Compare three numerical integration methods (Trapezoidal Rule, Simpson's Rule,
Monte Carlo Integration) on a set of benchmark functions. Measure convergence
rates, accuracy vs. step count, and wall-clock time. Produce a short LaTeX
paper with figures and tables summarizing the findings.

## Why This Problem?

- **Not trivial**: requires implementing 3 algorithms, running convergence
  experiments, producing plots, and writing analysis.
- **Not complex**: all math is well-understood; ground-truth integrals are
  available analytically.
- **Exercises every ricet subsystem**: code generation, testing, paper writing,
  literature search, reproducibility logging, verification, auto-debug, etc.

## Benchmark Functions

| Function | Integral on [0, 1] | Exact Value |
|----------|-------------------|-------------|
| f(x) = x^2 | int_0^1 x^2 dx | 1/3 |
| f(x) = sin(pi*x) | int_0^1 sin(pi*x) dx | 2/pi |
| f(x) = exp(-x^2) | int_0^1 exp(-x^2) dx | ~0.7468 (erf) |
| f(x) = 1/(1+25*x^2) | Runge function | ~0.5494 |

## Deliverables

1. Python module `src/integrators.py` with the 3 methods
2. Pytest test file `tests/test_integrators.py`
3. Convergence experiment script `experiments/convergence.py`
4. Figures: convergence plots saved to `figures/`
5. LaTeX paper `paper/main.tex` with results
6. Reproducibility log for each experiment run
