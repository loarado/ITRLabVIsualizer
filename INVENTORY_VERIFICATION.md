# Structured inventory implementation and verification

Completed October 3, 2026. The current repository and saved lab were the source of truth.
No uploaded snapshot/default fixture was applied to current data. No live server was
restarted, and all mutation/deletion/restoration/transfer/recovery tests used disposable
servers and data. No runtime dependencies were added.

## Checkpoint and current data

The working tree was clean before implementation. Maintainability cleanup was already
present, so its patches were not reapplied. Before changing code, 118 current data,
default and history files were archived with a SHA-256 manifest at:

`/home/braulio/.codex/checkpoints/ITRLabVisualizer/20261003T065805Z/`

`pre-inventory.tar.gz` is the recoverable original checkpoint; `sha256.json` is its
manifest. Every original file still matches that manifest. A disposable copy of the
populated lab passed startup migration: 84 shelf files, 192 bins, 135 decor shapes,
18 missing bin IDs assigned. All other values, revisions and history were identical.
Repeat startup changed no JSON files. Migration has not been applied to live data:
it will run automatically, after another checkpoint, on the next updated server start.

## Separately reviewed stages

1. Decor clipboard: active bin/decor selection, Ctrl/Cmd shortcuts, repeated nearby
   quarter-cell pastes, appearance/text, fresh IDs, overlap, limits, selection, undo/redo,
   refresh recovery, named save/reload, text-field behavior and clipboard reset.
2. Model/migration: separate item, shelf-scoped location and stock identities; existing
   IDs retained; checkpointed/repeatable legacy-bin migration; unplaced files retained;
   read-only normalization and unchanged historical snapshots. Two legacy backend
   expectations were updated to include assigned IDs while preserving all old fields.
3. Stock safety before writes: shelf/bin structure copies generate new location IDs and
   exclude stock. Removal/import explains unmapped recovery; Simple mode and layout
   undo/redo/version restoration retain stock. Older ambiguous bins remain separate.
4. Shared inventory editor: contextual defaults, existing item reuse, minimal entry,
   exact/unknown/availability/presence tracking, units/packs, decimal price/value rules,
   corrections, relocation, atomic transfers, archive/reactivation, optimistic revision
   checks, operation-ID retries, durable audit, authorization, unsaved-form recovery.
5. Catalog/navigation: LAB MAP/LAB INVENTORY navigation, metadata search, location
   filters, empty states, item details/all locations, identifiable map inventory matches,
   exact shelf/bin targeting, visibility reveal, hidden-bin preview, unmapped recovery,
   immediate same-browser updates, keyboard controls and mobile layout.
6. Integration/recovery/docs: coherent authenticated full-backup download, validated
   recovery into a new directory, configurable defaults path, README workflows, and
   regression verification. Pending journal recovery is serialized with requests;
   ordinary GETs never finish a save or expose partial saved state.

## Verification results

- Baseline: 23 backend tests; browser smoke and 52 browser-suite tests; formatting
  and ESLint passed after temporary development tooling was made available.
- Final backend: all 31 tests passed with `python3 -m unittest discover -s tests -v`.
- Final browser: standalone smoke passed; all 62 tests in the full browser-suite run
  passed. The additional final transfer-refresh and retained-bin editor tests passed in focused
  four-test runs, bringing coverage to 64 distinct browser checks. The eight focused
  inventory/location backend checks and other focused browser checks also passed.
- `npm run format:check`, `npm run lint`, Python compilation and `git diff --check`
  passed. All active scripts/pages are included in existing format/lint tooling.
- Full-backup recovery preserved all JSON documents/defaults and successfully loaded
  a recovered disposable server. Invalid counts, unsafe paths, missing shelf files and
  existing destinations were refused before publishing a recovered directory.
- Interrupted stock save recovered stock plus audit snapshots on restart. Pending
  reads returned an error without changing the journal. Replaying the same operation
  did not duplicate inventory. Browser transfer retry after a simulated lost response
  did not double-count; unsaved transfers also recovered their fields/operation ID.
- Movement, resizing, shelf/bin renaming and editable location-label changes preserved
  stock identity and quantity. Unknown values and currency/unit value calculation,
  cross-origin/anonymous mutation rejection, imports, archive and version restore
  were verified with disposable records.

The shell initially lacked Node/npm, and Chromium could not launch because `libnspr4`
was missing. Node 22.14 and extracted Chromium libraries were installed only under
`/tmp/itr-dev-tools`; checks used that PATH/LD_LIBRARY_PATH and the existing `.venv`
Playwright installation. No system package installation or testing-framework rewrite
was required. Initial tooling failures were resolved; no essential check remains blocked.
Test logs and screenshots are temporary artifacts under `/tmp/itr-*`.

## Operational limits and next action

Save/export any active layout drafts and save inventory entries before restarting the
updated Python server. Session/RAM drafts are temporary; startup creates the migration
checkpoint and assigns the missing IDs. Existing descriptions remain notes; enter real
inventory gradually from the map or catalog. Layout save/export/import never silently
carries structured stock. Ambiguous old restored bins may need explicit stock relocation.

Inventory uses one shared admin login and a whole-inventory revision check, so unrelated
concurrent inventory edits can also require review. Same-origin tabs refresh via update
signals; other browsers can use Refresh inventory or reopen the view. Full backups cover
saved data and both histories, not private unsaved drafts. The existing server is intended
for a single process per data directory. Future per-member accounts, dashboards, treasury
and purchasing automation remain outside this implementation's scope.
