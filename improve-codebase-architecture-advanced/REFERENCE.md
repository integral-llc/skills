# Reference

## Verification Anti-Patterns

Sub-agents consistently produce inflated findings when running metrics without reading code. These are the known failure modes - guard against all of them before presenting any candidate.

### File size != function size

A 400-line file does NOT mean it has a 400-line function. The agent must identify the actual function boundaries (read the `func` declarations and their closing braces) and report real function sizes. A 400-line file with 10 well-factored methods is NOT the same problem as one monolithic function.

**Test**: For any claim "function X is N lines," read function X. Count lines from its declaration to its closing brace. Report the real number.

### High fan-in on small types is good design

A core domain type (e.g., `User`, `Session`, `Order`) will naturally have high fan-in because many modules need it. This is ONLY a problem if the type is ALSO large, unstable, or mixes unrelated concerns. A 76-line type with 63 fan-in is a well-designed core model, not a "hub problem."

**Test**: Read the type. If it's under 100 lines, coherent, and rarely changes, drop the candidate.

### Single responsibility is about concepts, not methods

An HTTP client class with `validate()`, `listModels()`, and `sendMessage()` has ONE responsibility: "communicate with this API." These are not separate responsibilities. SRP means one REASON TO CHANGE, not one METHOD.

**Test**: Ask "would these methods change for different reasons?" If they all change when the API changes, it's one responsibility.

### Settings screens reference many types by nature

A settings view that configures providers, audio, shortcuts, and appearance will naturally import types from all those domains. High fan-out on a settings screen is inherent to its purpose, not a design flaw. Splitting it into sub-views just moves the imports around.

**Test**: Would splitting actually reduce the total number of type references? If no, the coupling is inherent, not fixable by restructuring.

### Co-change coupling has innocent explanations

Files that change together may be genuinely coupled (split concept) OR may just be part of the same feature additions. Adding a new LLM provider naturally touches the provider class, cost calculator, and prompt assembler in the same commit. That's not a coupling problem - it's a feature that spans layers.

**Test**: Look at the commit messages. If the co-changes are feature additions across layers, the coupling is natural. If they're bug fixes where fixing one file requires a corresponding fix in another, it's genuine coupling.

### Duplication must be exact, not approximate

Two files that "handle similar concepts" are not necessarily duplicated. Read both files side by side. Count the lines that are IDENTICAL or near-identical (same logic, same types, same structure). If less than 50 lines overlap, the duplication cost of extracting a shared abstraction may exceed the benefit.

**Test**: Diff the two files conceptually. Report the exact number of duplicated lines and the total lines of each file. If overlap is under 30%, it's probably not worth extracting.

### Extensions are not separate entry points

A class split across a main file and an extension file (e.g., `RequestManager.swift` + `RequestManagerStream.swift`) is ONE type with ONE public interface. Callers don't "coordinate 3 files" - they call one method on one type. The file split is an organizational choice, not an architectural problem.

**Test**: Count the number of distinct entry points callers actually use. If it's 1-3 methods on one type, the internal file organization is irrelevant to callers.

## Dependency Categories

When assessing a candidate for deepening, classify its dependencies:

### 1. In-process

Pure computation, in-memory state, no I/O. Always deepenable - just merge the modules and test directly.

### 2. Local-substitutable

Dependencies that have local test stand-ins (e.g., PGLite for Postgres, in-memory filesystem). Deepenable if the test substitute exists. The deepened module is tested with the local stand-in running in the test suite.

### 3. Remote but owned (Ports & Adapters)

Your own services across a network boundary (microservices, internal APIs). Define a port (interface) at the module boundary. The deep module owns the logic; the transport is injected. Tests use an in-memory adapter. Production uses the real HTTP/gRPC/queue adapter.

Recommendation shape: "Define a shared interface (port), implement an HTTP adapter for production and an in-memory adapter for testing, so the logic can be tested as one deep module even though it's deployed across a network boundary."

### 4. True external (Mock)

Third-party services (Stripe, Twilio, etc.) you don't control. Mock at the boundary. The deepened module takes the external dependency as an injected port, and tests provide a mock implementation.

## Complexity Metrics

Use these to quantify architectural friction beyond gut feel.

### Fan-in / Fan-out

- **Fan-in**: Number of modules that depend on this module (import it, call it). High fan-in = widely used. High fan-in + high churn = fragile hub that breaks many consumers when it changes.
- **Fan-out**: Number of modules this module depends on. High fan-out = the module knows too much. It's entangled with the system rather than encapsulating a concept.
- **Ratio**: A deep module should have high fan-in (many callers) and low fan-out (few dependencies). If both are high, the module is a pass-through, not an abstraction.

### Cyclomatic Complexity

Count of linearly independent paths through a function. Each `if`, `else`, `case`, `for`, `while`, `catch`, `&&`, `||` adds a path. Target: under 10 per function. Over 20 is a strong deepening signal - the function is hiding a state machine that deserves its own module.

### Cognitive Complexity

Measures how hard code is to understand, not just how many paths it has. Adds weight for:
- Nesting depth (each level compounds)
- Breaks in linear flow (early returns, continues, breaks)
- Recursion
- Boolean logic chains

A function with cyclomatic complexity 8 but all paths at nesting level 1 is easier to reason about than one with cyclomatic complexity 6 but three levels of nesting. Cognitive complexity captures this.

## Churn Analysis

Files that change together frequently are natural deepening candidates - they're already one logical unit that the current architecture forces apart.

### Co-change frequency

Find which files change in the same commits:

```bash
git log --format='%H' --since='6 months ago' | while read hash; do
  git diff-tree --no-commit-id --name-only -r "$hash" | sort | paste -sd, -
done | sort | uniq -c | sort -rn | head -20
```

### High-churn files

Find the most frequently modified files:

```bash
git log --format='%H' --since='6 months ago' | while read hash; do
  git diff-tree --no-commit-id --name-only -r "$hash"
done | sort | uniq -c | sort -rn | head -30
```

### Interpreting churn data

- Two files that always change together but live in separate modules = strong deepening candidate
- A file that changes in every commit but is stable in interface = implementation detail that should be hidden
- A file that changes often AND breaks callers = leaky abstraction, needs a better boundary

## Hot Path Assessment (The Critical 3%)

Knuth: "We should forget about small efficiencies, say about 97% of the time: premature optimization is the root of all evil. Yet we should not pass up our opportunities in that critical 3%."

A candidate is on a hot path if:

- It executes per-request, per-frame, or per-event in a tight loop
- Profiling data shows it in the top N functions by CPU time or allocation count
- It sits in a streaming pipeline where latency accumulates (e.g., token processing, audio buffer handling)
- It's called O(n) or worse times per user action, where n grows with data size

**If a candidate is on a hot path**: interface design must not add indirection that costs measurable latency. Prefer inlining, value types, and zero-copy patterns. The sub-agent producing the "minimize interface" design should be explicitly told about the performance constraint.

**If a candidate is NOT on a hot path**: optimize for clarity and correctness. Extra indirection for a cleaner interface is a good trade.

## Equivalence Testing

When replacing shallow modules with a deepened module, prove behavioral equivalence before deleting old tests. Adapted from Knuth's methodology: prove correctness first, then optimize.

### Pattern

1. **Capture golden data**: Before any refactoring, run the existing shallow modules' tests and record their inputs and outputs as fixtures.
2. **Write boundary tests**: Write tests for the new deep module's interface using the same inputs. Assert the outputs match the golden data.
3. **Run both in parallel**: Keep old tests running alongside new boundary tests until the boundary tests cover all golden data scenarios.
4. **Delete old tests**: Only after boundary tests pass on all golden data.

This ensures the deepened module is behaviorally identical, not just "it compiles and the new tests pass."

## Concurrency Boundary Checklist

Before deepening modules that cross concurrency boundaries:

- [ ] Identify which modules are isolated (actors, serial queues, main-thread-only)
- [ ] Identify which modules are non-isolated or use concurrent access
- [ ] Map shared mutable state between modules
- [ ] Determine if deepening requires changing isolation domains
- [ ] Check for potential deadlocks from merging modules with different lock hierarchies
- [ ] Verify the deepened module's isolation model is consistent (don't mix actor-isolated and non-isolated mutable state)

## Error Propagation Analysis

Before deepening, map how errors flow:

- Which module originates each error type?
- Where are errors translated (e.g., database error to domain error to HTTP status)?
- Where are errors swallowed or logged-and-ignored?
- Does deepening eliminate translation layers (good) or create one module that catches everything (bad)?

The deepened module should own its error types and translate at the boundary. Internal errors should not leak. If the current modules each define error types that callers handle differently, the deepened interface must preserve those distinctions or explicitly simplify them.

## Testing Strategy

The core principle: **replace, don't layer.**

- Old unit tests on shallow modules are waste once boundary tests exist - delete them
- Write new tests at the deepened module's interface boundary
- Tests assert on observable outcomes through the public interface, not internal state
- Tests should survive internal refactors - they describe behavior, not implementation

## Issue Template

<issue-template>

## Problem

Describe the architectural friction:

- Which modules are shallow and tightly coupled
- What integration risk exists in the seams between them
- Why this makes the codebase harder to navigate and maintain
- Quantitative signals: churn coupling data, fan-in/fan-out counts, complexity scores

## Proposed Interface

The chosen interface design:

- Interface signature (types, methods, params)
- Usage example showing how callers use it
- What complexity it hides internally
- Fundamental operation count for the common caller

## Data Structure Rationale

- What internal representation the new interface enables
- Why the current decomposition prevents this representation
- Time/space complexity improvement (if any)

## Boundary Rationale

- Why the interface cuts here and not one level higher or lower
- What would break if the boundary moved inward (too shallow) or outward (too broad)
- Which concept the module owns exclusively

## Dependency Strategy

Which category applies and how dependencies are handled:

- **In-process**: merged directly
- **Local-substitutable**: tested with [specific stand-in]
- **Ports & adapters**: port definition, production adapter, test adapter
- **Mock**: mock boundary for external services

## Concurrency Model

- Isolation domain of the deepened module
- Thread-safety guarantees at the interface boundary
- Shared mutable state (if any) and how it's protected

## Testing Strategy

- **Equivalence verification**: Golden data captured from existing modules, boundary tests assert identical outputs
- **New boundary tests to write**: describe the behaviors to verify at the interface
- **Old tests to delete**: list the shallow module tests that become redundant
- **Test environment needs**: any local stand-ins or adapters required

## Migration Plan

- Number of callers that must change
- Whether migration is incremental (adapter/shim phase) or all-or-nothing
- Error propagation changes callers must handle

## Implementation Recommendations

Durable architectural guidance that is NOT coupled to current file paths:

- What the module should own (responsibilities)
- What it should hide (implementation details)
- What it should expose (the interface contract)
- How callers should migrate to the new interface

</issue-template>
