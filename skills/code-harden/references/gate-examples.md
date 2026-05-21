# The Gate: Worked Examples

The gate is what separates this skill from a generic "make it better" loop.
Every candidate critique runs through one question:

> If I left this unchanged, what concrete bad thing would happen?

If you can answer that in one sentence with a specific bad outcome, the
critique is real. If you can't, drop it.

Below are worked examples. Internalize the pattern. When you find yourself
wavering on a critique, come back to this file.

---

## REAL critiques (fix these)

### Example 1: Missing cleanup

```ts
useEffect(() => {
  const id = setInterval(tick, 1000)
}, [])
```

- Candidate: "Missing `clearInterval` in cleanup."
- Bad thing: timer keeps firing after unmount; if it calls setState, you get
  the "can't update unmounted component" warning and an actual memory leak.
- Real. Fix.

### Example 2: Stale closure

```ts
const [count, setCount] = useState(0)
useEffect(() => {
  const id = setInterval(() => setCount(count + 1), 1000)
  return () => clearInterval(id)
}, [])
```

- Candidate: "`count` is captured stale; this only increments to 1."
- Bad thing: the timer always reads `count = 0` from its closure; the counter
  is broken.
- Real. Fix (use functional setter or include count in deps).

### Example 3: Untyped public API

```ts
export function processOrder(data: any): any { ... }
```

- Candidate: "`any` on both sides eliminates type safety at every call site."
- Bad thing: callers will pass wrong shapes, get runtime errors, and the
  type checker won't help. A reviewer will block this in PR.
- Real. Fix.

### Example 4: Silent error swallow

```ts
try {
  await saveOrder(order)
} catch (e) {
  console.error(e)
}
```

- Candidate: "Logging and continuing pretends success when the save failed."
- Bad thing: the caller thinks the order was saved; the UI shows success;
  the database has nothing. Real user-facing bug.
- Real. Fix.

### Example 5: SQL injection

```python
cursor.execute(f"SELECT * FROM users WHERE name = '{name}'")
```

- Candidate: "User input concatenated into SQL string."
- Bad thing: trivial injection if `name` is user-controlled. Security
  incident.
- Real. Fix.

### Example 6: Race condition on async fetch

```ts
const [data, setData] = useState(null)
const [query, setQuery] = useState('')

useEffect(() => {
  fetch(`/search?q=${query}`)
    .then(r => r.json())
    .then(setData)
}, [query])
```

- Candidate: "If query changes while a fetch is in flight, the older
  response can resolve after the newer one and overwrite it."
- Bad thing: user types "dogs" then "cats", sees results for "dogs" because
  the dogs fetch was slower and resolved last.
- Real. Fix (AbortController or sequence number).

### Example 7: Goroutine leak

```go
go func() {
    for msg := range ch {
        process(msg)
    }
}()
```

- Candidate: "No way to stop this goroutine if `ch` is never closed."
- Bad thing: goroutine lives forever; in a long-running service this
  accumulates.
- Real. Fix (context cancellation or close ch in a defined place).

### Example 8: Missing required ARIA

```tsx
<div onClick={handleClick}>Delete</div>
```

- Candidate: "Not a button. No keyboard activation. Not announced as
  interactive by screen readers."
- Bad thing: keyboard users and screen reader users can't access this
  action. Accessibility violation, in some jurisdictions a legal liability.
- Real. Fix (use `<button>`).

### Example 9: Off-by-one

```ts
function getFirstN(arr: T[], n: number): T[] {
  return arr.slice(0, n - 1)
}
```

- Candidate: "Returns n-1 elements, not n."
- Bad thing: function lies about what it does; every caller is wrong.
- Real. Fix.

### Example 10: Magic number with no explanation

```ts
if (retries > 7) throw new Error('Too many retries')
```

- Candidate: "Why 7?"
- Bad thing: future maintainer has no way to know if 7 is safe to change,
  derived from a calculation, or arbitrary. They'll either be afraid to
  touch it or break something.
- Real. Fix (named constant + comment explaining the choice).

---

## SPECULATIVE critiques (drop these)

### Anti-example 1: Premature memoization

```ts
const items = data.map(d => ({ ...d, label: d.name.toUpperCase() }))
```

- Candidate: "Should use `useMemo` for performance."
- Bad thing: ... none stated. No measurement. `data` is unknown size.
- Speculative. Drop.

If `data` is known to be 10,000 items and the component re-renders 60 times
per second, that's different. But that's a *measured* concern, not a generic
"should memoize."

### Anti-example 2: "Could be more abstract"

```ts
function calculateTax(amount: number, rate: number): number {
  return amount * rate
}
```

- Candidate: "Could be made generic to handle multiple tax types."
- Bad thing: ... none. The function does one thing and is used in one place.
- Speculative. Drop. (YAGNI.)

### Anti-example 3: Defensive guard against impossible state

```ts
function getUser(id: string): User {
  const user = users[id]
  if (!user) throw new Error('User not found')
  return user
}
```

- Candidate: "Should also check that `users` is not null."
- Bad thing: ... only matters if `users` can be null. If it's a module-level
  const initialized at import, it can't be.
- Speculative. Drop. Defensive guards against impossible states confuse the
  reader about what's possible.

### Anti-example 4: Style preference

```ts
const result = items
  .filter(i => i.active)
  .map(i => i.name)
```

- Candidate: "Could be a for-loop for clarity."
- Bad thing: ... none. The chained version is idiomatic and clear.
- Speculative. Drop.

### Anti-example 5: Speculative scalability

```python
def get_users():
    return db.query("SELECT * FROM users").fetchall()
```

- Candidate: "Won't scale if users table grows large."
- Bad thing: yes, true at some scale. But the function is named `get_users`
  and the caller is presumably aware. Without a stated scale concern, this
  is speculation.
- Speculative as-stated. If you know the caller renders this list and there
  are 1M+ users, it becomes real (pagination required). Otherwise drop.

### Anti-example 6: "Could add logging"

```ts
async function chargeCard(amount: number) {
  await stripe.charge({ amount })
}
```

- Candidate: "Should log the charge for audit."
- Bad thing: depends on the system. In some systems, logging is required
  (compliance, audit). In others, logging is handled at a different layer.
- Speculative unless the spec or stated requirements say logging is needed.
  Drop unless you have evidence it's required.

### Anti-example 7: Test coverage

- Candidate: "No tests for this function."
- Bad thing: function isn't verified to work.
- Real in the abstract, but **not the scope of this skill**. The user asked
  for code, not tests. If they want tests, that's a separate request. Note
  in changelog as "no tests written; out of scope" and move on.

### Anti-example 8: "Could use a library"

```ts
function debounce<T extends (...args: any[]) => void>(fn: T, ms: number) {
  let id: ReturnType<typeof setTimeout>
  return ((...args: Parameters<T>) => {
    clearTimeout(id)
    id = setTimeout(() => fn(...args), ms)
  }) as T
}
```

- Candidate: "Could use lodash.debounce."
- Bad thing: ... none. The local implementation is correct, ~5 lines, and
  avoids a dependency.
- Speculative. Drop.

---

## Borderline cases

These are the ones where you have to think.

### Borderline 1: Performance without measurement

```tsx
{messages.map(m => <Message key={m.id} {...m} />)}
```

- Candidate: "Should virtualize for long lists."
- Bad thing: depends. If `messages` is bounded to ~100, no. If unbounded
  and could be 10,000, yes — DOM gets slow.

How to resolve: check the spec. If the spec implies bounded data, drop. If
unbounded or unclear, note as a fork ("chose simple .map; for >1000 items
swap to virtual list"). Don't iterate to fix unless the spec demands it.

### Borderline 2: Single global vs. dependency injection

```ts
import { db } from './db'

export async function getUser(id: string) {
  return db.users.findOne({ id })
}
```

- Candidate: "Hard to test; can't inject a fake db."
- Bad thing: real if tests are in scope or the user mentioned testing.
  Otherwise speculative for now (YAGNI).

How to resolve: if the user asked for testability, fix. If not, this is a
fork: "chose direct import for simplicity; for testability swap to DI." Note
and move on.

### Borderline 3: Hardcoded value

```ts
const TIMEOUT_MS = 5000
```

- Candidate: "Should be configurable."
- Bad thing: depends. If callers will reasonably want different timeouts,
  yes. If 5000ms is correct in all known cases, no.

How to resolve: if the spec shows multiple use sites with different needs,
fix. If only one caller exists, drop with a note "exposed if needed later."

---

## The meta-rule

When you can't decide if a critique is real, ask yourself:

> Am I generating this critique because I genuinely see a problem, or
> because I feel like I should find more issues to look thorough?

If it's the second one, drop the critique. The discipline of stopping early
is the most senior thing you can do in a code review. Junior reviewers find
everything; senior reviewers find what matters.

Apply the same discipline to your own code.
