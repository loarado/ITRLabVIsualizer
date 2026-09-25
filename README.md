# ITR Lab Visualizer

An editable CSS-grid lab floor plan with independent shelf inventory matrices and shared, password-protected saving. Python 3 is the only runtime dependency. The new editors use no external libraries or CDNs.

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

## Explore the lab (View Only)

Visitors see **Lab Explorer**, a red interface with technical UI typography and the map's original item fonts/colors. **Admin Login** and **View Only** remain visible. Editor sidebars, coordinate fields, export, history, and save controls are hidden.

Click a shelf to open a read-only information drawer. Simple shelves show shelf metadata; Complex shelves show the physical grid, including half-cell bins. Complex shelves initially fit the whole grid in the viewing area. Use **+ / −** to inspect bins and **Fit shelf** to return to the overview; zoomed shelves can be scrolled. Hover or focus a bin for its name, contents, and keywords; the list below provides full details. The grid cannot be edited in View Only. Click a section to see its area, access status, and contained items. Close the drawer with **Close**, **Escape**, or its backdrop.

The grouped **Sections**, **Paths**, **Storage**, **Tables**, **Carts / seating**, and **Machines / tools** checkboxes only affect visibility. Hidden objects have no map hit targets. They never modify saved data. Search matches partial text without regard to case, including shelf names, contents, keywords, and active Complex bin metadata. Matching results can be opened directly. Narrow screens support horizontal map scrolling and zoom.

## Edit normal items (Admin)

- Use **Add to Lab** at the top of the sidebar for shelves, tables, carts/seating, machines, walls, and labels.
- The **Item Directory** groups these types into independent collapsible categories. Search reveals matching groups without changing your normal collapse preferences.
- Select an item to edit its name, position, dimensions, colors, font, or position lock. Area is computed from the item center and the current section names. When sections overlap, the smallest containing section wins, then section ID breaks ties; outside sections the value is Lab. Drag unlocked items or use arrow keys to move by one cell.
- Equipment cannot overlap other equipment or leave the outline. It may be dragged across walls and doors, but an invalid final placement is reverted. Paste uses the same validator. Labels wrap/shrink within their boxes.
- Use **Ctrl/Cmd+C** and **Ctrl/Cmd+V** to duplicate a selected normal item into nearby clear space. Copies have new IDs. Copied shelves start with a deep copy of the source inventory and save to separate files. Text fields retain normal copy/paste.
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

Restoring loads the selected layout into this editor instance’s draft. Undo/redo of a version restore also switches its associated inventory draft through private backend memory; those memory references are excluded from saved/exported files. It does **not** write to disk or add a version. Opening history, Undo, Redo, and Reload saved also do not add versions. New saved versions also restore their shelf inventories into the private draft. Original and older map-only versions preserve the current inventories because they have no inventory snapshot. Click **Save changes**, enter a version name, and click **Save version** to make the draft persistent. Saved versions show their names in the history menu.

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
2. New shelves default to **Simple**: enter **Shelf name**, **Shelf contents**, and **Keywords**. The bin grid and matrix controls are hidden.
3. To use detailed inventory, choose **Complex** in **Shelf mode** and click **Apply mode**. This activates the existing matrix editor.
4. In Complex mode, select an empty half-cell to **Add bin here**, or edit an existing bin's name, contents, keywords, position, size, and style. Dragging and arrow keys snap to 0.5 units; dimensions use 0.5 steps with a minimum of 1. **Ctrl/Cmd+C/V** copies the selected bin with its metadata/style into the nearest valid space, or refuses if the shelf is full. Matrix resizing preserves bins.
5. Switching either way preserves all metadata and every bin. Dormant bins remain stored in Simple mode but are not shown or indexed until Complex mode is active again.
6. Save a named version and reload to share and verify the shelf contents.

Each editor opens its saved contents or recovers its cached draft for this instance. **Save changes** (or Ctrl/Cmd+S) opens a version-name dialog; only confirming **Save version** writes changes to disk. Canceling the dialog leaves the draft unsaved. Saving from either editor commits the instance’s lab and included shelf drafts as one named lab version, while keeping inventories in independent files. This includes edits cached while moving between editors. Saved versions capture the corresponding inventories. Other browsers see saved data, not your draft.

**Undo**, **Redo**, **Export JSON**, and **Reload saved** are available in both editors. Shelf JSON can also be imported. If another admin has saved the same lab or shelf since you loaded it, saving is blocked rather than overwriting their changes. Export your draft, then reload the latest version to reconcile it.

## Instance memory and Undo

Each signed-in browser tab has an independent lab draft and independent shelf drafts. The backend caches the draft plus up to **40 Undo/Redo steps** in RAM, keyed by login session, tab instance, and editor. A refresh or navigation between the lab and a shelf in the same tab recovers this memory. Another tab or user cannot access that instance’s draft.

- **Ctrl/Cmd+Z** undoes a grid edit; **Ctrl/Cmd+Shift+Z** or **Ctrl+Y** redoes it. When typing in a field, the browser’s normal text undo remains available.
- Draft caching happens shortly after edits and is flushed before editor navigation. Caching never creates a persistent version.
- Drafts are temporary: server restart, logout, session expiry, or eight hours without cache updates clears them. A fresh tab starts a new instance. Use a named save or Export JSON to retain work permanently.
- A saved version is shared; a cached draft is private to its instance. Save-conflict checks still prevent overwriting another admin’s newer saved version.

## Files and matrix format

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

Legacy matrix-only shelf files are normalized in memory: populated matrices become Complex; empty matrices become Simple. Missing metadata gets safe defaults, with the lab label as the legacy shelf-name fallback. Reads never rewrite the source file; an explicit named save writes the new fields. Complex grids are retained even in Simple mode. Existing lab section entries remain in their legacy JSON representation for compatibility, while the UI treats them exclusively as map structure.

Supported fonts are `system-ui`, `Arial`, `Georgia`, and `monospace`. Colors are six-digit hex strings. Font sizes range from 6–96; rows and columns range from 1–60. Each shelf file stores one matrix row per line for easier manual editing.

Prefer the editor or JSON import for changes. If hand-editing files while browsers are open, increment `revision` so stale browser drafts cannot overwrite those changes. **Reload saved** after editing a file. Back up the `data/` directory to back up all layouts and inventory.

New shelf files are created when the lab is explicitly saved; saving a new shelf from a cached lab draft can also create its file. Removing a shelf from the map retains its inventory file; Undo or restoring an item with the same ID reconnects it. A shared HTML editor loads the selected shelf file; there is no duplicated HTML per shelf.

## Tests

Backend tests use temporary data seeded from the original layout; they do not change your saved lab:

```bash
python3 -m unittest discover -s tests -v
```

The optional browser checks require Playwright and Chromium:

```bash
python3 -m pip install playwright
python3 -m playwright install chromium
python3 tests/browser_smoke.py
python3 tests/browser_features.py -v
python3 tests/browser_updates.py Updates -v
```

The feature suite covers visitor, Admin, and Lab Map Editor flows; visibility/data separation; categories; adding every item type; outline selection, dragging, keyboard input, deletion; shelf mode persistence/migration; aggregated search; read-only panels; theme transitions; and 1440/768/390-pixel layouts. Tests use isolated fixture data.

## Geometry and saved-state details

Map zoom ranges from **75% to 300%**; the new minimum is 25% smaller than the old 100% minimum. Fit returns to 100%. Panning uses the viewport scrollbars, and all editing converts pointer positions through the actual rendered map bounds.

Interior `walls` are arrays of `{id, a: [x,y], b: [x,y], thickness}`. `doors` are arrays of `{id, x, y, radius, orientation}` with hinge coordinates and NW/NE/SW/SE orientation. Missing arrays mean no elements and are not added merely by reading an older file. They save with the map and appear read-only outside Lab Map Editor. Legacy rectangular wall items still load separately.

Shelf schema 3 retains the matrix and adds optional half-cell offsets and bin IDs (new/duplicated bins get fresh IDs); integer bins and schema 2/legacy files remain valid. For a six-unit shelf, four bins of width 1.5 have anchor columns 0, 1, 3, and 4, with offsetX values 0, 0.5, 0, and 0.5. Both shelf views use doubled CSS grid tracks so half-unit positions and sizes remain exact. Bin collisions compare logical rectangles, not integer occupancy or rounded pixels.

Wall placement uses the grid line as the boundary: items can sit flush against it without leaving an empty cell for the painted stroke. A wall may not pass through an item’s interior, and an item may not be completely contained in a thick wall’s body. Doors reserve their drawn quarter-disk swing and thin outline, not their entire bounding square. These checks are shared by normal placement and paste. Visibility does not change collision constraints or persistent geometry. The display layers put paths, walls, and doors below equipment, with editing handles above it.

Named versions contain both `layout` and `shelves` snapshots. Saves validate all included shelf revisions before writing. A disk journal (`data/pending-save.json`) allows an interrupted, explicitly requested save to finish on the next server start; atomic file replacement and the server lock prevent normal requests from seeing partial saves. Do not edit the journal manually. No inventory snapshot can reconstruct shelf changes that were already lost before this fix.

## Misc markers

In **Add to Lab**, choose **Misc item**, then **Add item**. Use these for fire extinguishers and other map annotations. Choose **Square**, **Line**, **Triangle**, or **Circle**; adjust width/height, shape color (Background), and text styling. **Show text label** toggles the label while keeping the name available in search and the information panel. Lines also have direction and thickness controls.

Misc markers can overlap equipment, walls, doors, other markers, and areas outside the floor-plan outline, anywhere within the map grid. They do not block equipment placement. Dragging, arrow keys, copy/paste, undo/redo, named saves, and read-only viewing work as for other items. The **Misc items** visibility checkbox hides markers without changing saved data.
