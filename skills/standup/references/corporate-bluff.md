# Corporate bluff vocabulary

The point of "corporate bluff" is **defensible vagueness, not lying**. Every translated bullet must still map to something that actually happened. The translation removes engineering grit (broken stuff, dead ends, fights) so the standup reads like progress without inviting unnecessary questions.

## Core mappings

| What actually happened | How to write it |
|---|---|
| Fixed a broken thing | Stabilized X. De-risked X. Hardened X. |
| Wrote new code | Landed X. Shipped X. Delivered X. |
| Spent the day reading docs | Surveyed prior art. Aligned on the technical approach for X. |
| Got stuck and could not progress | Working through tradeoffs on X. Investigating X. |
| Argued with a teammate | Drove alignment on X. Worked through differing views on X. |
| Refactored without shipping anything | Hardened X. Simplified X. Tightened the internals of X. |
| Tried something that did not work | Validated the assumption that X is not the right approach. Explored the solution space for X. |
| Do not actually know yet | Validating assumptions on X. |
| Fixed a bug | Closed an edge case in X. Addressed a quality issue in X. |
| Got blocked by another team | Coordinating with stakeholders on X. Driving cross-functional alignment on X. |
| Slow progress | Steady progress on X. Building momentum on X. |
| Investigated something | Drove discovery on X. |
| Wrote a doc or spec | Captured the design for X. Codified the approach for X. |
| Set up the dev environment | Bootstrapped the foundation for X. |
| Read logs | Diagnosed signal in the telemetry for X. |
| Wrote tests | Tightened the safety net around X. |
| Asked someone for help | Looped in X for context. Synced with X. |
| Did not finish | In flight. Iterating toward delivery. |
| Reviewed someone else's PR | Provided technical review on X. |
| Researched options | Evaluated approaches for X. |

## Things to never say in a standup

These are dead giveaways and also invite questions:

- "Just" anything ("just refactoring", "just a small fix")
- "Quick" anything ("quick win", "quick refactor")
- "Almost done" (means "not done")
- "Should be ready by EOD" (a promise you do not have to make)
- "I think" / "I believe" (drop the hedge or remove the bullet)
- "Working on" without a noun (always name the thing)
- "Various" / "several" / "a few" (use a number or drop the bullet)
- "Cleanup" / "housekeeping" (sounds like padding)

## Cadence rules

- Lead each bullet with a verb in past tense for completed work, present continuous for in-flight work, or a clear noun phrase for blockers.
- One specific noun per bullet (the system, the file, the metric). Numbers when you have them.
- No editorial adjectives ("excellent", "great", "solid"). The work speaks; the bullet describes.
- Maximum 25 words per bullet. Anything longer is hiding something.

## Calibration examples

Bad:
> Worked on improving the regime detection system to deliver better performance.

Good:
> Stabilized the HMM regime detector. OOS backtest holds at 14.1% CAGR, 1.05 Sharpe over 2014-2026.

Bad:
> Spent some time looking into options trading stuff.

Good:
> Drove discovery on the options layer for regime-trader. Tradier sandbox client wired up; spec at v3.0 by Friday.

Bad:
> Had some issues with the deployment.

Good:
> Coordinating with platform on a Bedrock IAM permission for the migration. Unblock expected today.
