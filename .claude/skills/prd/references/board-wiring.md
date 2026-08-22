# Board wiring — add an issue to the Documents project

Shared by the `prd` and `triage-issue` skills. Four commands, not a convention: an issue that
is not on the "Nuke Raider — Documents" board is invisible to it, and one with no `Status` is
invisible to anyone reading the board for what is in flight.

Resolve **every field id and option id by name** — option ids are regenerated whenever the
field's option set is edited (`tools/factory_publish.py` already resolves `Log`, `Todo`,
`In Progress` and `Done` this way). The project id (`PVT_kwHOAv4a5M4BepB5`) is a stable
constant and is written literally, as `factory_publish.py` also does.

The calling skill supplies `<Type>` (per the title-prefix table in
`docs/document-conventions.md`) and `<Status>` (normally `Todo`).

```sh
# a. add the issue to the project, capturing the new item id
gh project item-add 3 --owner MatthieuGagne --url <issue URL> --format json
```

```sh
# b. resolve the Type field id + its <Type> option id, and the Status field id
#    + its <Status> option id — one call, both fields
gh project field-list 3 --owner MatthieuGagne --format json
```

```sh
# c. set Type = <Type> on the item created in (a)
gh project item-edit --id <item id from a> --project-id PVT_kwHOAv4a5M4BepB5 \
  --field-id <Type field id from b> --single-select-option-id <Type option id from b>
```

```sh
# d. set Status = <Status> on the same item
gh project item-edit --id <item id from a> --project-id PVT_kwHOAv4a5M4BepB5 \
  --field-id <Status field id from b> --single-select-option-id <Status option id from b>
```
