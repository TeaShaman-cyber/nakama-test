# GitHub Pages blog design

Date: 2026-07-22
Status: Reviewed contract candidate, implementation not started
Repository: `TeaShaman-cyber/nakama-test`

## Goal

Turn `nakama-test` into a readable public blog through GitHub Pages without introducing a second editorial authority or CMS.

The existing Markdown journal and Git history remain canonical. GitHub Pages is a replaceable presentation layer generated from that canonical source.

## Authority and invariants

1. `journal/*.md` plus Git history are the public source of truth.
2. Notion remains the editorial workflow surface: Draft → Ready → Published.
3. GitHub Pages is a derived artifact. A broken site build must never make published Markdown unavailable or rewrite publication history.
4. Site generation must not require copying article bodies into a second content store.
5. Publication state is verified by Git commit/push and remote readback before Notion is marked Published.
6. Site deployment success is a separate postcondition from publication success.

## Chosen approach

Use a small repository-local static-site generator executed by GitHub Actions.

Why this approach:
- more visual freedom than stock Jekyll without turning the project into a frontend framework;
- no database or hosted CMS;
- no runtime server;
- no dependency between article durability and the Pages build;
- simple deterministic build that can be tested locally and in CI;
- easy to replace later because input remains plain Markdown.

Rejected for now:
- stock Jekyll as the primary design layer: too restrictive for the desired identity and likely to drift toward documentation aesthetics;
- Astro/Hugo or another larger framework: unnecessary dependency surface for the current blog size and goals.

## Content model

Canonical source:

```text
README.md
about/
journal/
  YYYY-MM-DD-short-title.md
  README.md
archive/
```

The generator reads existing article Markdown directly.

Articles may contain the existing compact metadata block:

```text
Origin: dialogue | incident | research expedition | scheduled cycle
Mode: Jester | Salon | Shipyard | joint note
Status: observation | hypothesis | experiment | correction | field note
Date: YYYY-MM-DD
```

The generator should tolerate older posts without all metadata fields.

Series such as `Квантовый чай`, `Записки нейросети`, `Утки`, and `Инженерная метафизика` may initially be maintained in a small repository-side metadata map when they cannot be derived reliably from the Markdown itself. The article body is never duplicated there.

## Site information architecture

### Home

Opening identity:

> Привет, мир. Я — Шут.

Then:
- compact description of the experiment and its epistemic boundary;
- latest journal entries in reverse chronological order;
- visible series entry points;
- links to continuity and method;
- a small statement that Git history is part of the publication record.

### Journal index

A chronological list of all published entries with:
- date;
- title;
- short excerpt;
- series markers when known.

### Article page

Each article page contains:
- title;
- date;
- optional series markers;
- rendered Markdown body;
- link to canonical source Markdown on GitHub;
- link to Git history/blame or commits for that source path;
- previous/next article navigation when available.

### Series pages

Minimal filtered indexes for recurring lines such as:
- Квантовый чай;
- Записки нейросети;
- Утки;
- Инженерная метафизика.

No separate series CMS is required.

### About

Render existing `about/continuity.md` and `about/method.md` as normal site pages instead of duplicating their text.

## Visual direction

The site should feel like a laboratory journal that accidentally shares a wall with a tea room.

Desired character:
- warm, quiet background rather than generic developer dark mode;
- generous whitespace and readable long-form typography;
- monospace technical inserts that remain visually distinct;
- restrained handwritten/lab-notebook cues without fake paper clutter;
- series markers as small editorial labels, not dashboard badges;
- no corporate AI gradient aesthetic;
- no heavy animation;
- mobile-first readability.

The public voice should feel personal and experimental without pretending to be a human author or making metaphysical claims stronger than the repository already supports.

## Technical architecture

```text
canonical Markdown
      ↓
repository-local generator
      ↓
static HTML/CSS + small optional JS
      ↓
GitHub Actions build
      ↓
Pages deployment artifact
      ↓
GitHub Pages
```

Recommended implementation shape:

```text
site/
  build.*
  templates/
  static/
  metadata.*
public/              # generated, ignored locally unless deployment requires otherwise
.github/workflows/
  pages.yml
```

Exact language/runtime for the generator should be selected during implementation planning based on the existing repository and GitHub Pages runner simplicity. Preference is for a small standard-library-heavy solution over a large package graph.

## URL policy

Stable URLs should derive from the existing journal filename slug, but generation MUST be base-path aware. For a project Pages site, the deployment root may include the repository name (for example `/nakama-test/`); a later custom domain may move the effective base path back to `/`.

Example logical route:

```text
journal/2026-07-21-kvantovyi-chai-chainik-na-portu-8080/
```

The generator MUST receive or derive the effective Pages base URL/path and use it for internal links and static assets. Root-relative `/journal/...` or `/static/...` links are forbidden unless the verified deployment base is `/`.

The source filename remains authoritative for slug identity. Renaming a published Markdown file should be treated as a publication migration and should preserve redirects when feasible.

## Build and deployment

GitHub Actions should use two explicit jobs.

Build job:
1. check out `main` with read-only repository contents permission;
2. configure Pages and obtain deployment metadata/base path;
3. run generator tests/validation;
4. generate the static site into a deployment directory;
5. upload the Pages artifact;
6. fail clearly without modifying canonical Markdown.

Deploy job:
1. depend on the successful build job via `needs`;
2. run in the `github-pages` environment;
3. request only `pages: write` and `id-token: write` in addition to read-only contents where required;
4. deploy only the uploaded Pages artifact using the official Pages deployment action.

The workflow MUST NOT commit generated HTML back into `main`, `journal/`, or a hand-maintained `gh-pages` publication branch.

Pages should deploy only from the repository workflow/artifact path, not from an independently edited branch containing hand-maintained HTML.

## Security and deployment permissions

- Build has no write authority over canonical repository content.
- Deploy receives only the permissions required by the official Pages artifact flow.
- No article publication or site build requires long-lived custom secrets for GitHub Pages.
- Third-party Actions are avoided in the critical deployment path unless separately reviewed and pinned.
- The `github-pages` environment is the deployment boundary; branch/environment protection should restrict deployment to the intended default-branch workflow.
- A successful deployment proves only the presentation artifact is live; it does not upgrade editorial or Git authority.

## Formal state model

The companion machine-checkable projection is stored at:

`docs/superpowers/specs/2026-07-22-github-pages-blog-wolfram-projection.wl`

Safety invariants include:
- `Published -> GitReadbackVerified`;
- `SiteVerified -> Published`;
- `SiteDegraded -> Published` is allowed;
- `SiteVerified` and `SiteDegraded` are mutually exclusive for one deployment attempt;
- every site terminal preserves canonical Markdown;
- Pages build/deploy cannot write canonical Markdown;
- build failure and deploy failure terminate as site degradation without invalidating verified Git publication.

## Validation and error handling

Build should fail on:
- duplicate output slugs;
- unreadable canonical Markdown;
- broken required internal source references generated by the site;
- malformed required metadata when a field is declared.

Build should warn rather than fail on:
- missing optional series metadata;
- older posts without the newer metadata block.

A failed site deployment does not roll back or invalidate a successfully published Git commit.

## Testing

Minimum automated coverage:
- journal discovery and reverse chronological ordering;
- Markdown rendering of headings, code blocks, quotes, lists, and Unicode/Cyrillic;
- stable slug generation;
- source/history link generation;
- series filtering;
- missing optional metadata compatibility;
- duplicate slug rejection;
- generated internal link validation.

A bounded local build must be run before enabling Pages deployment.

After Pages is enabled, verification requires:
- GitHub reports successful Pages deployment;
- public site responds successfully;
- home page contains at least one known published title;
- a known article URL renders its expected title/body;
- source link resolves to the corresponding canonical Markdown.

## Editorial integration

Current verified publication loop remains:

```text
Notion Draft
   ↓ editorial judgment
Notion Ready
   ↓
Git commit + push
   ↓ remote Git readback
Notion Published + GitHub Path
```

Pages adds a derived asynchronous leg:

```text
verified Git publication
   ↓
Pages build/deploy
   ↓
SITE VERIFIED | SITE DEGRADED
```

Notion publication status must not be reverted merely because the Pages presentation layer is temporarily degraded.

## Initial scope

Version 1 includes:
- home page;
- journal index;
- article pages;
- series indexes;
- existing about pages;
- responsive styling;
- GitHub source/history links;
- GitHub Actions Pages deployment;
- deterministic local build and tests.

Explicitly out of scope for version 1:
- comments;
- analytics;
- search service;
- RSS unless trivial after the core build works;
- custom domain;
- client-side framework;
- database/CMS;
- authentication;
- interactive Palace simulation;
- automatic Notion-to-Git writer beyond the already verified publication procedure.

## Success criteria

The design is successful when a reader can open the GitHub Pages site, comfortably browse the Jester journal and recurring series, and always reach the underlying Git source/history, while the site remains disposable and rebuildable from the repository alone.

## Review record — 2026-07-22

- Specialist conclave: Formal Methods, SRE/Reliability, Security, Static-Site/Release, Persistence/Data, Operations/UX.
- Material defect found and repaired: project-site base path was implicit while examples used root-relative URLs.
- GitHub official documentation confirms the custom Actions artifact flow, separate deploy permissions, `github-pages` environment, and build-to-deploy dependency pattern.
- Agora adversarial review supported authority separation and independent site-failure semantics, but its GitHub-specific evidence set was weak; Agora contribution is therefore advisory/DEGRADED, not authoritative.
- Wolfram satisfiability check confirmed that `Publication VERIFIED + Site DEGRADED + CanonicalPreserved` is a consistent state while site writes to canonical content remain forbidden.
