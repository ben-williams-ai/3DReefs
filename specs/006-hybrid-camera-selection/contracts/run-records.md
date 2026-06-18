# Contract: Run Records

Patch selection must continue using the Feature 1 run-record system.

Required run-record behaviour:

- `splat.patch` starts and completes as a normal stage.
- Selector name, version, and signature appear in patch metadata.
- Reuse or overwrite decisions for incompatible selector outputs happen before
  patching starts.
- Warnings from patch selection are added to run warnings without blocking valid
  patch outputs.
- Diagnostic export failures are recorded as warnings, not silent failures.
- Feature 006 acceptance does not require `splat.train`, `splat.cleanup`,
  `splat.merge`, or `splat.sog`.
