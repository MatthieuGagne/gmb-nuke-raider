# Native sub-issue wiring

Per `docs/document-conventions.md`'s **Sub-issues.** rule, a body-text `Refines #<epic>` line
does not populate the board's `Parent issue` field — only native wiring does, and the Epics view
groups on it. The API takes the child's numeric REST `id` — not its `node_id` and not its issue
number:

```sh
child_id=$(gh api repos/<owner>/<child repo>/issues/<new PRD number> --jq .id)
gh api -X POST repos/<owner>/<epic repo>/issues/<epic number>/sub_issues \
  -F sub_issue_id=$child_id
```

The child id is read from the **PRD's own** repo; the POST goes to the **epic's** repo — the two
can differ. Wiring works cross-repo under one owner, so a Garage PRD may be wired to a game-repo
epic. Verify by running the same summary command **twice** — once before the POST and once
after — and confirming the total rose by one:

```sh
gh api repos/<owner>/<epic repo>/issues/<epic number> --jq .sub_issues_summary.total
```

A count alone cannot catch a child id resolved from the wrong repo, so also confirm the new
PRD's own number appears in the epic's sub-issue list:

```sh
gh api repos/<owner>/<epic repo>/issues/<epic number>/sub_issues --jq '.[].number'
```
