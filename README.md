# ITR Lab Visualizer

An editable CSS-grid lab floor plan and structured inventory, with shared password-protected editing. LAB MAP and LAB INVENTORY use the same item and stock records; shelf matrices describe physical layout. Python 3 is the only runtime dependency. The new editors use no external libraries or CDNs.

## Run

Stop the old `python3 -m http.server` process with **Ctrl+C**, then run this from the project directory:

```bash
python3 server.py
```

Open **http://localhost:8000/**. The root page opens the red **Lab Explorer**. Signing in switches to the blue **Lab Editor**.

Click **Admin login** and enter **`itr`** to edit. Anyone can view; the server requires an authenticated admin session for every save. Keep the terminal running. Press **Ctrl+C** to stop it. After application updates, restart the server to load its updated API and asset routes.

If port 8000 is occupied, stop the old server or use:

```bash
python3 server.py --port 8001
```

Then open **http://localhost:8001/**. Do not use `0.0.0.0` as a browser address.

**The old static-server command and opening HTML directly do not support the editors' loading, login, or saving APIs.**

### Share on your lab network

```bash
python3 server.py --host 0.0.0.0
```

Other computers should open `http://<server-computer-LAN-IP>:8000/`. They see the same files and can sign in with the same admin password. This is a local/LAN development server; use HTTPS and a production deployment before exposing it to the internet.

To change the starting password, set `ITR_ADMIN_PASSWORD` before starting the server:

```bash
ITR_ADMIN_PASSWORD='your-new-password' python3 server.py
```

## Structured inventory: LAB MAP and LAB INVENTORY

Use the **LAB MAP** and **LAB INVENTORY** links at the top of every active page.
Inventory is optional and can be recorded incrementally. Existing shelf/bin names,
contents, keywords, modes, matrices and decor are retained. Contents fields are
**descriptive notes**, not stock entries, and are never parsed into items or counts.

- An **item** identifies a supply/equipment type. It has a required name and optional
  category, keywords, description, product link, vendor, unit price/currency and notes.
  Similar names remain separate unless you deliberately choose an existing item.
- A **location** is a shelf ID plus an optional bin ID. Bin identity is **shelf-scoped**:
  previously copied shelves can contain the same nested bin IDs without sharing stock.
  Names, visible Location ID labels and geometry can change without breaking links.
- A **stock entry** connects one item to one location (or Unassigned). Multiple items
  can occupy one bin; one item can occupy many locations. One active entry is allowed
  per item/location/unit, so add to an existing entry rather than duplicating it.

As an admin, select a shelf/bin and use **Add inventory to this shelf/bin**, or use
**Add inventory** in LAB INVENTORY. Save a new physical location in a named layout
before entering its stock. Choose an existing item to record it elsewhere; choose
**Create a new, distinct item** when it is a different type. Item-detail edits apply
at every location. Required inputs are only item name and a unit (default: `each`).
Location is filled automatically for contextual entry; Unassigned is also valid.

Tracking supports **Exact quantity** (blank = unknown), **Approximate availability**
(available, low, out of stock), and **Presence only** (counts unnecessary). Record
individual pieces as `each` and packages as `pack`, with contents per pack in notes.
Counts and prices are decimal strings, not floating-point values. Blank prices/counts
never become zero. A known exact count and price with matching units produces a
currency-rounded **estimated inventory value** for that entry. Values are never
summed across units or currencies, and never represent historical spending or a budget.

**Save inventory** writes stock immediately, with success/error feedback and no named
map version. **Save changes** continues to save a named geometry/description version.
Inventory edits from either page refresh the same records and panels. Other tabs receive
an update signal; a focused page refreshes inventory when it becomes visible. Use
**Refresh inventory** to check changes from other browsers. Saves reject stale inventory
revisions. The editor retains the unsaved form, shows the latest saved record, and lets
you explicitly review your correction or use the latest values before saving again.

**Edit stock / relocate** corrects a count, tracking method, notes or the entire location.
**Transfer quantity** moves a positive known exact amount in the same unit: source and
destination update in one transaction. It refuses negative counts, excessive transfers,
same-location transfers and merges into an unknown/non-exact destination. Failed-save
retries reuse an operation ID to prevent duplicate transfers or entries. Retry an uncertain
save without changing its form to confirm its outcome. Approximate/presence entries
can be relocated as a whole using Edit stock. **Archive entry** preserves its quantity
and history; it is still visible in item details and the Archived filter. Reactivation
refuses conflicting active entries.

Search LAB INVENTORY by item name or metadata, open details for all locations, and
choose **Show on map**. It reveals the shelf even when storage visibility was disabled,
opens the shelf drawer and highlights the exact bin by stable identity. Simple-mode
bins are exposed in a navigation preview with an explanation. Unassigned/unmapped
stock has no misleading map button; use Edit stock to relocate it. Map search continues
to match legacy descriptions and marks structured inventory results explicitly.

Removing a shelf/bin or importing replacement structure preserves stock; a stocked
location prompts with that consequence before removal. Missing locations remain
unmapped and searchable. Restoring the same IDs reconnects the **current** stock.
Map undo/redo and named-version restores never reverse stock edits or recreate stock.
Copying shelves/bins preserves descriptive notes as template information and excludes
all structured stock. There is no automatic item merging or stock copying.

Unsaved inventory entries and transfers have a local safety copy scoped to project,
authenticated session and tab, with the existing eight-hour recovery lifetime. Refresh
recovers their fields and original inventory revision; navigation/refresh is protected
while editing. Explicit cancel discards the safety copy. Logout clears this session's
copies. These forms are not backend map drafts and cannot be committed by a layout
save. Save before logout/session expiry/server restart for durable entry.

## Inventory storage, migration and coordinated recovery

Layouts remain in their existing JSON files. Structured records live in
`data/inventory.json`; audit snapshots live in `data/history/inventory/<revision>.json`.
JSON reuses the server lock and `pending-save.json` atomic-write/roll-forward journal,
so inventory and its audit snapshots commit together. Pending transactions finish
on startup or an authorized write retry. Reads return an error while recovery is
pending and never change saved data or expose partial files. Location status is derived from geometry, so deleting or
restoring layout needs no second stock transaction. SQLite would add a second
transaction/backup system without improving this first version; no runtime dependency
or geometry-storage rewrite is introduced.

On the first updated server startup, missing bin IDs are assigned in current shelf
files, including unplaced shelves. Existing shelf/bin IDs, metadata, geometry and
revision values are retained. No structured stock is invented. The server first writes
a recoverable `../.itr-backups/before-locations-*.tar.gz` checkpoint containing data and
defaults, then journals the migration. Repeating startup is a no-op when IDs exist.
Historical snapshots stay unchanged. Legacy reads resolve deterministic IDs in memory
without changing disk. A restored old bin lacking an ID reconnects only when its
shelf, anchor and complete legacy contents match the originally migrated bin. An
ambiguous old location remains separate and existing stock stays unmapped for explicit
relocation; names/coordinates are never used to guess an existing identity after edits.
Shelf imports assign fresh IDs and do not restore stock. Use layout versions for layout
restoration and full backups for complete recovery.

**Before updating a running server, save or export your active layout drafts and save
inventory entries. Restarting loses authenticated sessions and RAM drafts.** Then start
`python3 server.py` normally; migration is automatic and checkpointed. Development
checks never operate on your populated data.

Use **Download full lab backup** (admin only) in LAB INVENTORY for a coherent saved
snapshot of layout, every shelf file including unplaced shelves, structured inventory,
map and inventory histories, and defaults. It excludes private unsaved drafts. The JSON
is labelled `itr-full-backup`; Export JSON in map/shelf editors contains geometry and
notes only. Audit downloads are reference snapshots, not complete recovery backups.
Alternatively, save drafts, stop the server, and copy `data/` and `defaults/` together;
include any pending journal when recovering an interrupted save. Retain the external
migration checkpoint separately. Do not restore only an inventory file over a different
layout and assume its missing locations have been recovered.

To recover a downloaded full backup, validate and restore into a **new directory**:

```bash
python3 restore_backup.py /path/itr-full-lab-backup.json /path/recovered-lab
python3 server.py --data-dir /path/recovered-lab/data --defaults-dir /path/recovered-lab/defaults --port 8001
```

The restore tool validates every document/path and stock record before writing,
rejects incomplete or malformed backups and existing destinations, and publishes
only a complete recovered directory. Review the recovered server before deliberately
switching your usual server to those paths. The original data directory remains
available. Full recovery deliberately restores the backed-up stock state; ordinary
layout restoration does not. Inventory activity and audit snapshots let you inspect
older counts and make an explicit current correction without rolling stock backward.
Do not run multiple server processes against the same data directory. No Python
packages or runtime dependencies have been added.

## Explore the lab (View Only)

Visitors see **Lab Explorer**, a red interface with technical UI typography and the map's original item fonts/colors. **Admin Login** and **View Only** remain visible. Editor sidebars, coordinate fields, export, history, and save controls are hidden.

Click a shelf to open a read-only information drawer. Simple shelves show shelf metadata; Complex shelves show the physical grid, including half-cell bins. Complex shelves initially fit the whole grid in the viewing area. Use **+ / −** to inspect bins and **Fit shelf** to return to the overview; zoomed shelves can be scrolled. Hover or focus a bin for its name, contents, and keywords; the list below provides full details. The grid cannot be edited in View Only. Click a section to see its area, access status, and contained items. Close the drawer with **Close**, **Escape**, or its backdrop.

The grouped **Sections**, **Paths**, **Storage**, **Tables**, **Carts / seating**, and **Machines / tools** checkboxes only affect visibility. Hidden objects have no map hit targets. They never modify saved data. Search matches partial text without regard to case, including shelf names, contents, keywords, and active Complex bin metadata. Matching results can be opened directly. Narrow screens support horizontal map scrolling and zoom.

## Edit normal items (Admin)

- Use **Add to Lab** at the top of the sidebar for shelves, tables, carts/seating, machines, walls, and labels.
- The **Item Directory** groups these types into independent collapsible categories. Search reveals matching groups without changing your normal collapse preferences.
- Select an item to edit its name, position, dimensions, colors, font, or position lock. Area is computed from the item center and the current section names. When sections overlap, the smallest containing section wins, then section ID breaks ties; outside sections the value is Lab. Drag unlocked items or use arrow keys to move by one cell.
- Equipment cannot overlap other equipment or leave the outline. It may be dragged across walls and doors, but an invalid final placement is reverted. Paste uses the same validator. Labels wrap between whole words and shrink to fit their boxes, so words such as “Table” are not split across lines.
- Use **Ctrl/Cmd+C** and **Ctrl/Cmd+V** to duplicate a selected normal item into nearby clear space. Copies have new IDs. Copied shelves retain bins, decor, style, descriptive notes and keywords, with fresh child bin IDs, and save to separate files. Structured inventory assignments and quantities are excluded; source stock is unchanged. Text fields retain normal copy/paste.
- Sections, interior walls, doors, and arrows are map-level elements. Their controls and direct editing are unavailable in normal item mode.

Editor groups use short ease-in/ease-out transitions, respect reduced-motion preferences, and remove collapsed controls from keyboard/pointer interaction.

## Lab Map Editor

As an admin, click **Lab Map Editor** in the header. Normal item controls disappear; physical items remain dimmed as context and cannot be dragged. Use the map groups to edit:

- **Outline & grid:** click a vertex, drag it, or use arrow keys for one-cell movements. Selected-point X/Y inputs and the full coordinate list stay available. Use **Delete point**, Delete/Backspace, or **Insert point after selected**. At least three distinct points with nonzero area must remain inside the grid. Arrow keys do not edit the map while typing.
- **Center lab in grid:** after applying larger grid dimensions, use this button in **Outline & grid** to center the whole floor plan. It moves the outline, all items (including locked items), sections, arrows, walls, and doors together, preserving their spacing and shelf inventories. Movement snaps to whole cells, so opposite margins may differ by one cell. Undo reverses it; Save changes records it as a named version.
- **Sections:** select an existing section or **Add section**. Edit its name, colors, fonts, and hatching. Existing section positions start locked; uncheck **Lock position and size** before moving/resizing. Section labels are placed in available space to avoid equipment.
- **Interior walls:** enter start/end grid coordinates and thickness, then **Add wall**. Select a wall to drag it, drag its endpoint handles, use arrow keys, or edit coordinates and **Update wall**. **Delete wall** removes it.
- **Doors:** enter hinge coordinates, radius (1–20 units), and one of four swing quadrants (NW, NE, SW, SE), then **Add door**. Select it to drag, move with arrow keys, change radius/orientation with **Update door**, or delete it. The quarter-circle swing footprint is reserved against final equipment placement.
- **Traffic arrows:** use the controls described below to move or reshape routes.

**Leave Lab Map Editor** returns to item editing and removes map-editing hit targets/handles. Changes remain in your instance draft until you explicitly save a named version. Login/logout and visibility/theme changes do not rewrite the saved lab.

The initial outline and placements remain the existing grid interpretation of the supplied floor-plan sketch, not a surveyed architectural drawing.

## Reset and saved-version history

Click **Version history / reset** in the lab toolbar. Select **Original layout** or a timestamped saved revision, then click **Restore selected layout**. Admin login is required to restore.

Restoring loads the selected layout into this editor instance’s draft. Undo/redo of a version restore also switches its associated shelf-layout draft through private backend memory; those memory references are excluded from saved/exported files. It does **not** write to disk or add a version. Opening history, Undo, Redo, and Reload saved also do not add versions. New saved versions also restore their shelf layouts and descriptive notes into the private draft. Structured item/stock records have independent history and are never restored by a map operation. Original and older map-only versions preserve the current shelf layouts because they have no shelf snapshot. Click **Save changes**, enter a version name, and click **Save version** to make the draft persistent. Saved versions show their names in the history menu.

History is persisted in `data/history/lab/` and survives browser reloads and server restarts. The original floor plan is kept separately in `defaults/lab.json`. History starts with the layout saved when this feature was added; older, previously unrecorded revisions are not available. Back up `data/` and `defaults/` together.

## Edit traffic arrows

Inside **Lab Map Editor**, select a red dotted arrow or choose it in **Traffic arrows**. You can:

- Drag the line to move the entire arrow, snapping to whole grid cells.
- Drag circular handles to move endpoints or bends, snapping to tenths of a cell.
- Edit the **Route points** coordinates and click **Apply points**. Add or remove lines to add or remove bends (at least two points are required).
- Use arrow keys to move the selected route, **Reverse arrow** to change direction, or **Delete arrow** to remove it.
- Click **Add arrow** to create another route.

Arrow changes remain in the draft and support Undo, Redo, and version restore. Coordinates start at zero and must remain inside the grid. The **Paths** checkbox controls visibility only.

## Edit a shelf

1. As an admin, select a shelf and click **Open this shelf’s inventory**. Lab drafts are cached before navigation.
2. New shelves default to **Simple**: enter **Shelf name**, **Shelf descriptive notes**, and **Keywords**. The canvas supports visual Shelf Decor; inventory bins remain hidden until Complex mode.
3. To use detailed inventory, choose **Complex** in **Shelf mode** and click **Apply mode**. This activates the existing matrix editor.
4. In Complex mode, select an empty half-cell to **Add bin here**, or edit an existing bin's name, contents, keywords, position, size, and style. Dragging and arrow keys snap to 0.5 units; dimensions use 0.5 steps with a minimum of 1. **Ctrl/Cmd+C/V** copies the selected bin with its metadata/style into the nearest valid space, or refuses if the shelf is full. Matrix resizing preserves bins.
5. Switching either way preserves all metadata and every bin. Dormant bins remain stored in Simple mode. Their structured inventory remains searchable in LAB INVENTORY and map inventory search; item details can expose a retained bin or relocate its stock. Legacy bin descriptions remain indexed only in Complex mode.
6. Save a named version and reload to share and verify the shelf contents.

Each layout editor opens its saved contents or recovers its cached draft for this instance. **Save changes** (or Ctrl/Cmd+S) opens a version-name dialog; only confirming **Save version** writes changes to disk. Canceling the dialog leaves the draft unsaved. Saving from either editor commits the instance’s lab and included shelf drafts as one named lab version, while keeping shelf layouts in independent files. This includes layout edits cached while moving between editors. Saved versions capture the corresponding matrices and descriptive notes. Structured inventory uses its separate Save inventory workflow. Other browsers see saved data, not your draft.

**Undo**, **Redo**, **Export JSON**, and **Reload saved** are available in both editors. Shelf JSON can also be imported as structure and descriptive notes. Every imported bin gets a fresh ID; existing stock remains linked to its former locations and is discoverable as unmapped when those locations are absent. Imports never import stock or quantities. Undo can recover the replaced location identities before saving. If another admin has saved the same lab or shelf since you loaded it, saving is blocked rather than overwriting their changes. Export your draft, then reload the latest version to reconcile it.

## Instance memory and Undo

Each signed-in browser tab has an independent lab draft and independent shelf drafts. The backend caches the draft plus up to **40 Undo/Redo steps** in RAM, keyed by login session, tab instance, and editor. Another tab does not automatically load that working copy; **Manage drafts** can list and delete working copies across tabs in the same authenticated session. Other login sessions cannot access them.

- **Ctrl/Cmd+Z** undoes a grid edit; **Ctrl/Cmd+Shift+Z** or **Ctrl+Y** redoes it. When typing in a field, the browser’s normal text undo remains available.
- Draft caching happens shortly after edits and is flushed before editor navigation. Caching never creates a persistent version.
- Drafts are temporary: server restart, logout, session expiry, or eight hours without cache updates clears them. A fresh tab starts a new instance. Use a named save or Export JSON to retain work permanently.
- A saved version is shared; a cached draft is private to its instance. Save-conflict checks still prevent overwriting another admin’s newer saved version.

### Shelf Decor

**Shelf Decor** in the shelf sidebar adds rectangles/squares, circles/ellipses, and triangles. Drag a shape to move it and use its bottom-right handle or width/height fields to resize. Positions and dimensions snap to quarter-cells, with a minimum size of 0.25 cells. Arrow keys move selected decor by a quarter-cell. Outline thickness (0–20 px), outline/fill/text colors, and optional wrapping text are editable. Delete Decor or Delete/Backspace removes only the selected shape; typing fields retain normal keyboard behavior.

Bins stay above decor. If a bin covers a shape, select the shape from the sidebar. Turn off **Edit decor on canvas** to reach empty cells under shapes. Use **Ctrl/Cmd+C/V** to copy selected decor, including appearance and text, into a nearby quarter-cell position. Pasted shapes get fresh IDs and become selected; Undo/Redo, recovery, export and named saving work normally. Decor may overlap bins and other shapes. A shape filling the whole canvas has no distinct nearby paste position; an oversized shape or the 200-shape limit is explained without changing the draft. Copying a bin replaces the decor clipboard and vice versa; clipboard contents are local to this shelf page and cleared on logout/reset/reload. Text fields keep normal copy/paste.

Decor belongs to the shelf, remains in both modes, and appears read-only in the Explorer with bin tooltips still available. Canvas shrinking cannot cut off bins or decor.

Shelf JSON gains an optional `decor` array of objects with `id`, `shape`, `x`, `y`, `w`, `h`, `text`, `outlineWidth`, `outlineColor`, `fillColor`, and `textColor`. Coordinates are zero-based shelf cells. IDs are unique within a shelf. Existing files without decor need no migration. Decor is excluded from inventory indexing/search and is preserved by shelf export/import, copies, drafts, named saves, and versions. Rendering is shared in `shelf_model.js`; `shelf_decor.js` adds editing behavior.

### Delete temporary drafts

Open **Manage drafts** from either editor, choose **Delete Draft**, and confirm with the red button. Cancel or Escape makes no change. Deletion removes exactly that session/tab/resource working copy from backend memory and its browser recovery record. It never removes saved JSON, inventory files, or version history. Deleting the active copy loads the latest saved state; deleting the last copy leaves an empty list. A draft-only shelf falls back to its blank inventory while its parent map draft still exists, or returns to the lab if it no longer exists. Other drafts remain untouched. Server deletion counters prevent late writes or stale recovery records from recreating deleted drafts; subsequent deliberate edits can create a new working copy.

### Refresh recovery

`editor_recovery.js` keeps a small localStorage safety copy of each working document after meaningful edits and drag-end, before the delayed server cache write. A pending text-field edit is flushed through its normal change handler on refresh. Keys are scoped by browser origin, a server-provided project/session identifier, tab instance, and lab/shelf resource. Records include format, timestamp, committed lab revision, document revision, and draft-deletion counter. UI recovery includes editing mode, zoom, scroll, and expanded groups; selections are cleared.

On load, authentication and recovery context are established first. The map recovers before inventories so newly added shelves can load. Pending browser copies pass the existing server draft validation before the working document is displayed and editing is enabled. Normal server drafts retain undo history; the emergency browser copy preserves current data rather than duplicating the full undo stack. Invalid, expired (eight hours), deleted, or older-revision snapshots are ignored. Storage failures show a warning and leave server caching available.

Successful **Save changes** clears the committed browser copies and preserves edits made during the save. Failed saves retain recovery data. Intentional logout clears browser recovery for that login session, discards its server drafts, and loads committed visitor data. Recovery creates no saved versions. Because sessions remain temporary and are held in server memory, this is refresh protection during an active session, not a replacement for saving/exporting before logout, session expiry, or server restart.

When updating the running application, save or export active work before restarting `server.py` to load new API routes. Development tests use disposable data and do not restart your live server.

## Files and matrix format

- `inventory.py`, `inventory_ui.js`, `inventory_list.js`, `lab_inventory.html` — Structured item/stock model, shared contextual editor, catalog, and stable map links.
- `restore_backup.py` — Validated full-backup recovery into a new directory.
- `data/inventory.json`, `data/history/inventory/` — Stock records and independent audit snapshots.
- `server.py` — Dependency-free Python server, admin sessions, validation, revision checks, and atomic JSON writes.
- `lab_overview.html`, `lab.js`, `lab_tools.js` — Main lab editor, traffic arrow tools, and restore controls.
- `shelf_editor.html`, `shelf.js`, `shelf_model.js` — Simple/Complex shelf interface and backward-compatible model helpers, opened with a shelf ID such as `shelf_editor.html?id=R01`.
- `map_editor.js` — Explicit map-editing mode and interactive outline controls.
- `map_elements.js`, `map_geometry.js` — Wall/door tools, logical collision geometry, and derived section containment.
- `explorer.js` — Read-only shelf/section drawers and search results.
- `editor_groups.js` — Accessible animated collapsible groups.
- `common.js`, `editor.css` — Auth, named saves, draft history, shared styling, and distinct themes.
- `data/lab.json` — Lab grid, sections, fixtures, footprint, paths, interior walls, and doors.
- `data/shelves/R01.json`, `R02.json`, etc. — **One independent file per shelf**, initially 34 rows × 30 columns. New files default to Simple mode while retaining an empty matrix for optional Complex use.
- `shelf_inventory_editor.html` — Original standalone editor, retained unchanged as a legacy reference. Its JSON format differs from the new matrices, and it does not use shared admin saving.

Each matrix cell is either `null` or a bin object. A bin is stored at the integer cell containing its top-left corner. Optional `offsetX`/`offsetY` values of `0.5` place that corner halfway through the cell (omitted means zero). Width/height and positions accept 0.5 increments, with each dimension at least 1. Covered cells remain `null`. No overlapping bins are allowed. A small complete shelf file looks like:

```json
{
  "id": "R01",
  "revision": 0,
  "schemaVersion": 3,
  "mode": "complex",
  "name": "Hardware shelf",
  "contents": "Fasteners and small parts",
  "keywords": "assembly",
  "rows": 2,
  "cols": 3,
  "matrix": [
    [{"name":"M4 bolts","contents":"Hex bolts","keywords":"hardware","w":2,"h":1,"background":"#dc4545","color":"#ffffff","fontSize":14,"fontFamily":"system-ui","bold":true}, null, null],
    [null, null, null]
  ]
}
```

Legacy matrix-only shelf files are normalized in memory: populated matrices become Complex; empty matrices become Simple. Missing metadata gets safe defaults, with the lab label as the legacy shelf-name fallback. Reads never rewrite the source file; an explicit named save writes the new fields. Startup performs the checkpointed bin-ID migration described below, without rewriting historical snapshots or resetting revision numbers. Complex grids are retained even in Simple mode. Existing lab section entries remain in their legacy JSON representation for compatibility, while the UI treats them exclusively as map structure.

Supported fonts are `system-ui`, `Arial`, `Georgia`, and `monospace`. Colors are six-digit hex strings. Font sizes range from 6–96; rows and columns range from 1–60. Each shelf file stores one matrix row per line for easier manual editing.

Prefer the editor or JSON import for changes. If hand-editing files while browsers are open, increment `revision` so stale browser drafts cannot overwrite those changes. **Reload saved** after editing a file. Back up `data/` and `defaults/` together, or download a full lab backup from LAB INVENTORY. This includes `inventory.json` and both history trees; a layout export alone is not an inventory backup.

New shelf files are created when the lab is explicitly saved; saving a new shelf from a cached lab draft can also create its file. Removing a shelf from the map retains its inventory file; Undo or restoring an item with the same ID reconnects it. A shared HTML editor loads the selected shelf file; there is no duplicated HTML per shelf.

## Development checks

Running the application still requires only Python: `python3 server.py`. Node, npm,
Prettier, ESLint, and Playwright are optional development tools; there is no build step.
Do not use a live lab server for testing or restart it with unsaved work.

For formatting and linting, install Node.js 22.13+ (22.x) or 24+ (with npm), then run from
the project root:

```bash
npm ci --ignore-scripts
npm run format:check
npm run lint
```

`package-lock.json` pins the development dependencies. `npm run format` applies
Prettier to the same explicit scope: the three active HTML pages and their 15
first-party JavaScript files, listed in `package.json`. It excludes data, defaults,
history, the legacy standalone editor, CSS, documentation, and installed/generated
files. `.prettierignore` also limits formatting to this approved source list.
Strict HTML whitespace handling intentionally places some tag brackets on adjacent
lines to preserve inline spacing; embedded-language formatting is disabled to
preserve inline code and template contents.

Lint runs without autofix. `eslint.config.mjs` models each page's classic-script
loading group and derives shared globals only from actual top-level declarations.
Update those groups and the explicit package script lists when adding or removing
an active script. The configuration itself uses a separate Node environment.
The small rule set catches undefined names, invalid global assignments, duplicate
arguments/keys/cases, unreachable code, invalid regular expressions, and invalid
`typeof` comparisons; it does not enforce another formatting style.

### Backend tests

No Node or third-party Python packages are needed:

```bash
python3 -m unittest discover -s tests -v
```

With development tooling installed, `npm run test:backend` runs the same command.
This verifies the backend only, not browser behavior.

### Browser tests

Optional browser verification requires Playwright and Chromium. For example:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install playwright
python3 -m playwright install chromium
python3 tests/browser_smoke.py
python3 tests/run_browser_suite.py
```

On Linux, Chromium also needs its system libraries; if they are missing,
`python3 -m playwright install-deps chromium` installs them and may require
administrator access. Keep the virtual environment activated when running the
npm test commands so `python3` resolves to the environment with Playwright.

```bash
npm run test:browser
npm test
```

`test:browser` runs the standalone smoke script, then the browser suite. The suite
runs each distinct inherited test once and deliberately excludes the smoke script.
`npm test` runs backend tests followed by both browser entry points. These commands
stop and return a failure when a command fails; missing Playwright or Chromium is
not a browser pass. Report any skipped checks separately from a complete result.

Tests use disposable fixture data and independent servers on randomly assigned
local ports. They cover saved versions, draft recovery/deletion, shelf modes and
decor, copying, undo/redo, exports, map geometry, visitor/Admin controls, and
responsive layouts. They do not write to the populated `data/` or `defaults/`
directories. Browser screenshots go to the system temporary directory.

## Geometry and saved-state details

Map zoom ranges from **75% to 300%**; the new minimum is 25% smaller than the old 100% minimum. Fit returns to 100%. Panning uses the viewport scrollbars, and all editing converts pointer positions through the actual rendered map bounds.

Interior `walls` are arrays of `{id, a: [x,y], b: [x,y], thickness}`. `doors` are arrays of `{id, x, y, radius, orientation}` with hinge coordinates and NW/NE/SW/SE orientation. Missing arrays mean no elements and are not added merely by reading an older file. They save with the map and appear read-only outside Lab Map Editor. Legacy rectangular wall items still load separately.

Shelf schema 3 retains the matrix and adds optional half-cell offsets and bin IDs (new/duplicated bins get fresh IDs); integer bins and schema 2/legacy files remain valid. For a six-unit shelf, four bins of width 1.5 have anchor columns 0, 1, 3, and 4, with offsetX values 0, 0.5, 0, and 0.5. Both shelf views use doubled CSS grid tracks so half-unit positions and sizes remain exact. Bin collisions compare logical rectangles, not integer occupancy or rounded pixels.

Wall placement uses the grid line as the boundary: items can sit flush against it without leaving an empty cell for the painted stroke. A wall may not pass through an item’s interior, and an item may not be completely contained in a thick wall’s body. Doors reserve the interior of their quarter-disk swing. Items can touch its straight sides or curved boundary without an extra clearance cell; the decorative stroke does not block placement. These checks are shared by normal placement and paste. Visibility does not change collision constraints or persistent geometry. The display layers put paths, walls, and doors below equipment, with editing handles above it.

Named versions contain both `layout` and `shelves` snapshots. Saves validate all included shelf revisions before writing. A disk journal (`data/pending-save.json`) allows an interrupted, explicitly requested save to finish on the next server start; atomic file replacement and the server lock prevent normal requests from seeing partial saves. Do not edit the journal manually. No shelf snapshot can reconstruct shelf changes that were already lost before this fix.

## Misc markers

In **Add to Lab**, choose **Misc item**, then **Add item**. Use these for fire extinguishers and other map annotations. Choose **Square**, **Line**, **Triangle**, or **Circle**; adjust width/height, shape color (Background), and text styling. **Show text label** toggles the label while keeping the name available in search and the information panel. Lines also have direction and thickness controls.

Misc markers can overlap equipment, walls, doors, other markers, and areas outside the floor-plan outline, anywhere within the map grid. They do not block equipment placement. Dragging, arrow keys, copy/paste, undo/redo, named saves, and read-only viewing work as for other items. The **Misc items** visibility checkbox hides markers without changing saved data.

Misc shapes stretch to their grid width and height: squares become rectangles and circles become ellipses. Select a misc item to edit its outline color and thickness (0 hides the outline). Line outlines surround the colored line.

Select a shelf in the lab editor to edit its **Location ID**. This searchable location label appears in the directory and visitor information. Its inventory file and link keep their stable internal ID. Location labels and misc styling support undo and become persistent with Save changes.
