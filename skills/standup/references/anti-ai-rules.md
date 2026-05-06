# Anti-AI rules for standup output

This is the scrub list. Run every bullet through it before writing the file. If a bullet violates any rule, rewrite it.

## Hard bans (no exceptions)

### Em dashes
The em dash character (—) is the single loudest AI tell. **Never** use it. Not in the bullets, not in section breaks, not in chat output. Use a comma, a period, or two regular dashes with spaces if you absolutely must.

Search for these and remove every instance:
- `—` (em dash, U+2014)
- `–` (en dash, U+2013)

If your draft has any of these, replace them. A regular hyphen `-` is fine.

### Banned vocabulary

Drop any sentence that contains one of these words and rewrite it without the word. No substitutions from the same family.

- delve, dive into, deep dive
- leverage, leveraging
- robust, robustly
- seamless, seamlessly
- comprehensive
- ensure, ensuring (use "make sure" or restructure)
- facilitate, facilitating
- streamline, streamlining
- elevate, elevating
- empower, empowering
- harness, harnessing
- meticulous, meticulously
- intricate
- multifaceted
- nuanced (unless the actual point is nuance)
- pivotal
- transformative
- noteworthy
- thoughtful, thoughtfully
- carefully crafted
- elegant solution
- holistic
- synergy, synergize
- realm, in the realm of
- landscape (as in "the X landscape")
- tapestry
- testament (as in "a testament to")
- journey (as in "our journey")

### Banned phrasings

- "It is worth noting that..."
- "It is important to remember that..."
- "In today's fast-paced world..."
- "In an era of..."
- "Not only X but also Y"
- "Not just X but Y"
- "More than just X"
- "Whether X or Y, ..."
- "From X to Y, ..."
- "Moreover, ..." / "Furthermore, ..." / "Additionally, ..."
- "In conclusion, ..."
- "At its core, ..."
- "Ultimately, ..."

## Structural patterns to avoid

### Rule of three

AI overuses parallel triples. Do not write "fast, scalable, and reliable" or "design, build, and deploy". Pick the one that matters most.

If you find a triple in your draft, kill two of the three. Keep the most concrete one.

### Trailing -ing clauses

AI loves ending sentences with a participial summary that adds nothing. Examples to avoid:

> "Shipped the migration, paving the way for future iterations."
> "Closed the bug, ensuring stability across the platform."
> "Landed the design, setting the stage for next quarter."

Cut the trailing clause. End on the noun.

### Vague attributions

Never write "studies show", "experts agree", "best practices suggest", "research indicates". A standup is a first-person report. If you need a source, name a specific person, ticket, or document.

### Negative parallelism

"It is not just X, it is Y" is an AI tell. Pick X or Y, drop the other.

### Symmetry padding

If two adjacent bullets have the same grammatical shape (verb + noun + outcome clause), break the pattern. Real humans do not write parallel structure across consecutive bullets.

## Cadence rules

- Vary sentence length. If three bullets in a row are 15 words long, one of them should be 6 and another should be 22.
- Use occasional fragments. "Numbers held." is a complete bullet line.
- It is fine to start a bullet with "And" or "But" if the prior bullet sets it up.
- Concrete nouns over abstract ones. "OpenSearch index" not "the indexing layer".

## Self-check before writing

Read the draft out loud (mentally). If it sounds like a LinkedIn post, a press release, or a McKinsey one-pager, it is wrong. A standup is what you would actually say to a teammate at the coffee machine, with the sharper edges sanded off so a manager can also read it without panicking.

If the draft passes the read-aloud test, write the file. If it does not, redo the bullets.
