# The Critique Rubric

Walk these categories in order. For each category that applies to the code,
ask the listed questions. Write down what you find. Then apply the gate
from `SKILL.md` to filter speculative critiques out.

Most code doesn't need every category. Skip what doesn't apply.

---

## 1. Correctness

The fundamental question: does this code do what the spec says it does?

- Does the happy path produce the right output for at least one example I can mentally trace?
- Does the stated behavior (in the prompt, comments, or function name) match the actual behavior?
- Are there off-by-one errors in indexing, range bounds, slicing?
- Are conditions inverted? (`if !foo` where it should be `if foo`)
- Are async paths actually awaited where needed?
- Does early-return order make sense? Are guards in the right place?
- Is the function pure when it claims to be pure?

---

## 2. Lifecycle & resources

Anything that opens must close. Anything that subscribes must unsubscribe.

- Every `useEffect` with a subscription/listener/timer/observer has a cleanup return
- Every `addEventListener` has a matching `removeEventListener` (or `{ signal }` option)
- Every `setTimeout`/`setInterval` is cleared on unmount or completion
- Every file handle, socket, connection, lock is closed in a `finally`/`defer`/context manager
- Every `IntersectionObserver`, `MutationObserver`, `ResizeObserver` is disconnected
- Every `AbortController` is either consumed or its lifetime is bounded
- React: no setState calls on unmounted components
- React: dependencies array is correct (no missing deps, no over-included objects)
- Node: no detached event emitters
- Long-running tasks (workers, threads) have a stop mechanism

---

## 3. Concurrency & async

Anywhere two things can happen at once is a place to scrutinize.

- Cancellation: can the caller stop an in-flight operation? Is cancellation propagated?
- Stale closures: does the async callback read state that may have changed?
- Race conditions: if two async ops complete out of order, does the UI/state stay consistent?
- Ordering: does the code assume an order that isn't guaranteed?
- Functional setters: when updating React state from an async path, is the updater functional?
- AbortError handling: is an aborted op treated differently from a real error?
- Promise rejection: are all rejection paths handled?
- Locks/mutexes: do we always release in `finally`?
- Goroutine/coroutine leaks: every spawned task has a defined exit path

---

## 4. Type safety (typed languages)

Types should be load-bearing. If they're decorative, the code is undertyped.

- No `any`, `unknown` (without subsequent narrowing), or `as Foo` casts that aren't justified
- Discriminated unions where states are mutually exclusive (loading | success | error)
- No optional fields that are tied to specific states (use the union instead)
- Function returns: explicit return type on exported functions
- No `// @ts-ignore` or `// @ts-expect-error` without a comment explaining why
- Generics: type parameters are actually used to constrain, not decoration
- `Record<string, unknown>` over `object` where applicable
- Strict null checks respected (no `!` non-null assertions without justification)
- Python: type hints present on public functions, `Optional` only when truly nullable
- Rust: `Result<T, E>` propagation; no `unwrap`/`expect` outside `main`/tests
- Go: errors wrapped with context where they bubble up

---

## 5. Error handling

Every error has a defined caller experience. Nothing is swallowed silently.

- Every `throw` has a caller path that handles it
- Every `try/catch` either re-raises, logs+continues for a documented reason, or returns a typed error
- No `catch (e) { }` or `except: pass` (silent swallow)
- No `catch (e) { console.error(e) }` and then continue as if nothing happened
- Network errors distinguished from validation errors distinguished from programmer errors
- Caller can tell from the error type/message what went wrong and what to do
- Aborted operations are not treated as failures (separate state)
- Retry logic, if present, has a bound and a backoff
- Errors carry enough context to debug (include the operation that failed, not just the underlying message)

---

## 6. Edge cases

The cases the happy path forgot. The places off-by-one lives.

- Empty input: empty array, empty string, empty object, null, undefined
- Single-element input
- Maximum input (does it overflow, run out of memory, time out)
- Boundary values: 0, 1, -1, INT_MAX, INT_MIN, empty string vs whitespace string
- Malformed input: non-JSON to JSON.parse, non-number to parseInt, invalid UTF-8
- Concurrent calls: what if the function is called twice in flight
- Idempotency: what if the user clicks the button twice
- Out-of-order events: what if "stop" arrives before "start"

For each edge case identified: does the code handle it, or does it crash/silently-misbehave? If the spec doesn't cover the edge case, what's the most reasonable default behavior?

---

## 7. Determinism & idempotency

- Same input → same output (for the parts that should be pure)
- Side effects are localized and explicit (not buried in middle of logic)
- Retry safety: if the caller retries, do we double-charge / double-send / corrupt state?
- No reliance on iteration order of objects/maps where not guaranteed
- No reliance on `Date.now()` / `Math.random()` in logic that should be deterministic
- For database/external calls: are operations idempotent or do they need an idempotency key

---

## 8. Accessibility & UX (UI code only)

Skip this category entirely for non-UI code.

- ARIA roles on dynamic regions (`role="log"`, `aria-live` on chat/notification streams)
- Buttons have accessible labels (text content or `aria-label`)
- Inputs have associated `<label>` or `aria-label` / `aria-labelledby`
- Keyboard: every action reachable by keyboard, focus visible, tab order sensible
- Focus management: focus returns to a sensible place after modals close
- Loading states announced to screen readers (`aria-busy`, status regions)
- Color contrast not the sole signal (text + icon, not color alone)
- Motion: respects `prefers-reduced-motion` for non-essential animations
- Touch targets ≥ 44×44 on mobile

---

## 9. Security

Skip if the code doesn't touch user input, auth, secrets, or external systems.

- Input validation: anything from a user is validated before use
- SQL: parameterized queries, no string concatenation
- HTML rendering: escaped by default, `dangerouslySetInnerHTML` only with explicit sanitizer
- File paths from user: no path traversal (`..` rejected)
- Auth checks: every protected endpoint actually checks auth
- Secrets: not logged, not in error messages, not in client-side code
- CORS / CSRF: appropriate headers and tokens
- Rate limiting: present on anything that can be abused
- Timing attacks: constant-time comparison for tokens/passwords
- Crypto: standard libraries only, no homerolled

---

## 10. Readability

Code that works but can't be read will break later when someone modifies it.

- Names tell you what the thing is, not what type it is (`users`, not `userList`)
- Magic numbers have a named constant or a comment explaining them
- Long functions decomposed when the parts have natural names (don't decompose arbitrarily)
- Comments explain *why*, not *what* (the *what* is in the code)
- No dead code (commented-out blocks, unused imports, unreachable branches)
- No defensive guards for impossible states (they confuse the reader about what's possible)
- Consistent naming across the file/module
- Public API surface is intentional (export only what callers need)

---

## A note on order

When you find multiple categories of issues, fix in this order:

1. Correctness (it has to work first)
2. Security (if applicable)
3. Lifecycle & resources (silent leaks are bad)
4. Concurrency (silent races are worse than crashes)
5. Error handling (visible failures over invisible ones)
6. Type safety (catches future regressions)
7. Edge cases (one at a time, prioritize likely-to-occur)
8. Accessibility
9. Determinism
10. Readability (last, because changing names doesn't fix bugs)

If iteration 1 finds correctness bugs, fix those in v2 and leave readability
for v3 if you get there. Don't try to fix everything at once.
