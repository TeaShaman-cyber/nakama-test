# Editorial lifecycle

`nakama-test` has four publication-related surfaces with different authority.
They are deliberately not collapsed into one status flag.

```text
Notion
  editorial drafting / human judgment
        |
        v
Git repository
  canonical article body + provenance + QA
        |
        +--------------------+
        |                    |
        v                    v
GitHub Pages             1F916
canonical public text    discussion companion
```

## One repository entrypoint

Use:

```text
python tools/article_lifecycle.py new ...
python tools/article_lifecycle.py status ARTICLE
python tools/article_lifecycle.py verify-pages ARTICLE
python tools/article_lifecycle.py forum-payload ARTICLE
python tools/article_lifecycle.py publish-forum ARTICLE
```

`status` is the normal starting point. It reports the article's editorial
publication state, article-QA state, Pages receipt, forum companion receipt, and
one bounded next action.

Example:

```text
publication: draft
qa: PASS
pages: not_published
forum: draft (companion=draft)
next: editorial_review
```

## Starting a new article

A minimal draft can be scaffolded without copying metadata by hand:

```text
python tools/article_lifecycle.py new \
  --date 2026-09-22 \
  --slug example-article \
  --title "Example article" \
  --origin "Notion editorial draft" \
  --mode Jester \
  --series "Инженерная метафизика" \
  --forum
```

The command creates the journal Markdown, publication receipt, optional forum
companion, series metadata, and journal-index entry. It always starts as a
draft and performs no external write.

## Editorial state versus surface state

The article metadata field remains:

```text
Publication: draft | ready | published
```

This is editorial authority for the canonical article. Surface receipts are
separate:

```text
publication/<article>.json
  pages.state
  forum.state
```

Pages is the canonical public rendering of the Git article. A forum post is a
versioned discussion companion, not a second canonical copy of the article.
The companion lives under `distribution/forum/` and carries the canonical Pages
URL before publication.

## Promotion flow

The intended bounded lifecycle is:

```text
Notion Draft
-> Git draft
-> article QA / editorial review
-> Publication: ready
-> explicit promotion to Publication: published
-> merge + remote Git readback
-> Pages deploy + verify-pages --record
-> optional forum companion review
-> explicit forum publication
-> WRITE_VERIFIED readback
-> commit publication receipt
```

A green PR is a pre-merge gate, not a terminal state. A merged article is not a
verified Pages publication until the public readback succeeds.

## Forum publication

The forum companion is prepared and reviewed in Git. Inspect the exact payload
without writing anything:

```text
python tools/article_lifecycle.py forum-payload ARTICLE
python tools/article_lifecycle.py publish-forum ARTICLE
```

`publish-forum` is dry-run by default. An external write requires the explicit
flag:

```text
python tools/article_lifecycle.py publish-forum ARTICLE --execute
```

Before the write the command requires:

- `Publication: published`;
- a verified Pages receipt bound to the current article SHA-256;
- forum companion `Status: ready`;
- a forum-client checkout whose `HEAD == origin/main`.

The write uses the existing `theseus-1f916-client`. It never blindly replays an
ambiguous mutation. Only `WRITE_VERIFIED` updates the publication receipt to a
verified forum post. `RECOVERABLE` is preserved as recoverable state with the
operation id for later reconciliation.

Ordinary CI never performs a forum write.

## Receipts and authority

A publication receipt records observed per-surface state; it is not authority
to publish. Typical fields include the Pages source commit, article SHA-256,
HTTP readback, forum post id, operation id and verification timestamp.

The invariant is:

```text
article text authority       = Git
editorial promotion authority = explicit human/editorial decision
Pages verification           = public readback
forum verification           = 1F916 WRITE_VERIFIED/readback
```
