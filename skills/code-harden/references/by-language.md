# Per-Language Rubric Extensions

The main rubric in `rubric.md` applies across languages. This file lists
language-specific failure modes to add to the critique pass when relevant.

If the code is in a language you write fluently, you can skim this file.
If not, read the relevant section carefully before critiquing — many of
these patterns have no analog in other languages and you'll miss them.

---

## TypeScript / JavaScript

**Type discipline**

- No `any` in exported signatures; if internal, justify in comment
- `unknown` is fine but must be narrowed before use
- Discriminated unions (`type State = { kind: 'loading' } | { kind: 'ok', data: T } | ...`)
  over boolean flags + optional fields
- `as` casts are last resort; prefer type guards or refined types
- `// @ts-expect-error` over `// @ts-ignore` (it fails when the underlying issue is fixed)
- Prefer `Readonly<T>` / `readonly` for fields that shouldn't be mutated
- Generic constraints (`<T extends Foo>`) over loose generics

**React-specific**

- `useEffect` dependency array correct and stable (no object literals inline)
- Cleanup functions returned where subscriptions exist
- Functional setters for state updated from async callbacks
- `useCallback` / `useMemo` only with measured benefit or to stabilize a dep array
- No `useState` for derived values (compute from props/other state)
- Keys are stable across renders (not array index for reorderable lists)
- No setState in render
- No conditional hooks
- Refs for imperative DOM access, not for "values that change but don't trigger renders" (use state for that, ref for DOM)
- Context split by update cadence (don't put fast-changing and slow-changing state in same provider)

**Node-specific**

- Streams have error handlers, not just data handlers
- File handles closed in `finally` or use stream pipelines
- `process.env` access centralized, not scattered
- Unhandled promise rejections will crash in modern Node; handle them
- Worker threads have a shutdown path

**Modern JS**

- `Promise.allSettled` over `Promise.all` when partial failure is acceptable
- `AbortController` for cancellable async (fetch, custom)
- `structuredClone` over JSON parse/stringify hacks
- Optional chaining (`?.`) over manual null-checks, but don't hide bugs with it

---

## Python

**Type discipline**

- Type hints on all public functions (parameters and return)
- `Optional[X]` only when truly nullable; don't use it as "I don't know what to put"
- `mypy --strict` should pass; treat warnings as errors
- `TypedDict` over loose dicts for structured data
- `Protocol` for duck-typed interfaces
- `Literal[...]` for enum-like string parameters
- Avoid `Any` except at boundaries with untyped libraries

**Resource management**

- Context managers (`with`) for file/socket/lock/connection
- `try/finally` if a context manager doesn't exist
- No `__del__` for cleanup; use context managers

**Concurrency**

- `asyncio.gather` with `return_exceptions=True` when partial failure is OK
- `asyncio.shield` when you must complete despite cancellation
- Don't mix sync and async without `run_in_executor`
- Don't use bare `time.sleep` in async code; use `asyncio.sleep`
- GIL doesn't protect you from logical races; locks where needed
- `threading.Event` for cancellation flags

**Error handling**

- No bare `except:` (catches `KeyboardInterrupt` etc.)
- Use specific exception types
- `raise X from e` to preserve causal chain
- Don't catch `Exception` unless you also re-raise or it's at a true top-level boundary

**Pythonic patterns**

- Comprehensions over loops where readable
- `enumerate` over `range(len(...))`
- `zip` over indexed parallel iteration
- f-strings over `.format` or `%`
- `pathlib.Path` over `os.path` string manipulation
- `dataclass` / `pydantic` over manual `__init__`

---

## Rust

**Ownership & borrowing**

- No `unwrap` / `expect` outside `main` or tests; use `?` or pattern match
- `&str` parameters over `String` when you don't need ownership
- Lifetime elision used where possible; explicit lifetimes when not
- `Cow<str>` when sometimes-owned, sometimes-borrowed
- `Arc<Mutex<T>>` only when really needed; prefer channels/message passing

**Error handling**

- `Result<T, E>` propagation discipline
- Use `thiserror` for library errors, `anyhow` for application errors
- Error variants are meaningful (caller can match on them)
- `From` impls for converting between error types

**Async**

- Cancellation safety: every `await` point must be safe to cancel
- `tokio::select!` ordering matters (random by default)
- Don't hold locks across `await`
- `JoinHandle` is awaited or detached intentionally

**Idiom**

- `iter().map().collect()` over manual loops where clearer
- `if let Some(x) = ...` over `match` for single-arm checks
- Avoid `clone` until it's needed; profile before assuming it's a bottleneck
- Newtype wrappers for domain types (don't pass raw `u64` for user IDs)

---

## Go

**Concurrency**

- Every goroutine has a defined exit path (don't leak)
- `context.Context` passed through call chains for cancellation
- Channels closed by the sender, not receiver
- `sync.WaitGroup` for "wait for these N to finish"
- `select { case <-ctx.Done(): ... }` to check cancellation
- Don't use `time.Sleep` in production code; use timers with cancellation

**Error handling**

- `errors.Wrap` / `fmt.Errorf("...: %w", err)` to add context
- `errors.Is` / `errors.As` for inspection
- Sentinel errors for predictable cases (`io.EOF`)
- Return errors; don't `panic` in library code

**Resource management**

- `defer` for cleanup, declared right after acquisition
- File/socket/db connections closed via `defer`
- Don't `defer` in a loop without thought (deferred calls accumulate)

**Idiom**

- Naked returns only in short functions
- Receiver names short and consistent across a type's methods
- Interfaces small (1-3 methods); accept interfaces, return concrete types
- No "Manager" / "Util" / "Helper" types; name by what they do
- `iota` for enum-like constants

---

## Java / Kotlin

**Null safety**

- Kotlin: avoid `!!`; use `?.`, `?:`, or proper null checks
- Java: `@Nullable` / `@NonNull` annotations consistently
- `Optional<T>` for return types, not parameters or fields

**Resource management**

- `try-with-resources` for everything implementing `AutoCloseable`
- Kotlin: `use { }` extension

**Concurrency**

- Don't share mutable state without synchronization
- `synchronized` blocks small; prefer concurrent collections
- Kotlin: structured concurrency with `coroutineScope`
- Exception handling in coroutines: `SupervisorJob` if siblings shouldn't cancel each other

**Exception discipline**

- Checked exceptions: catch and handle, don't blanket-throw `Exception`
- Don't catch `Throwable` (catches `OutOfMemoryError`)
- Unchecked: still document in Javadoc

---

## Swift

**Optionals**

- No force unwrap (`!`) without a clear reason and comment
- `guard let` for early return, `if let` for branching
- `??` for defaults

**Memory**

- `[weak self]` in closures that outlive the capturing scope
- `[unowned self]` only when guaranteed alive
- Retain cycles in delegates: use `weak var delegate`

**Concurrency**

- `async`/`await` over completion handlers in new code
- `@MainActor` on UI-touching code
- `Task` cancellation: `try Task.checkCancellation()` at await points
- Actors for shared mutable state
- `Sendable` conformance for cross-actor types

**SwiftUI**

- `@State` for local UI state
- `@StateObject` for owned observables; `@ObservedObject` for passed-in
- `@Environment` for context-like values
- Avoid heavy work in body; cache in computed properties or actors

---

## C / C++

This file's coverage is light because if you're writing C/C++ you already
know the rubric. The high-stakes items:

- Buffer bounds on every array access
- `nullptr` checks before deref
- Ownership clear: who allocates, who frees
- RAII for resources in C++; explicit cleanup in C
- No undefined behavior (signed overflow, shift by bit-width, etc.)
- Thread safety annotated (atomic, mutex)
- Strict aliasing respected
- No raw `new`/`delete` in C++; use smart pointers
- `const` correctness throughout
- Initialize everything (no uninitialized reads)

---

## SQL

- Parameterized queries always; no string concatenation with user input
- Indexes on columns used in WHERE / JOIN / ORDER BY
- `EXPLAIN` plans understood for queries that touch large tables
- Transactions explicit; isolation level appropriate
- No `SELECT *` in production code; name columns
- `LIMIT` on anything that could return unbounded rows
- Foreign keys defined where the relationship is real
- NOT NULL where applicable (most columns)
- Deletes/updates scoped with WHERE clause that's been triple-checked

---

## Shell (bash, zsh)

- `set -euo pipefail` at the top
- Quote all variable expansions (`"$var"`, not `$var`)
- `local` for variables inside functions
- `[[ ]]` over `[ ]` in bash
- Check command exit codes; don't assume success
- `mktemp` for temp files; `trap` to clean up
- No parsing `ls`; use globs or `find`
- `printf` over `echo` for portability
