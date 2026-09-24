# ITR Lab Visualizer

An editable CSS-grid lab floor plan with independent shelf inventory matrices and shared, password-protected saving. Python 3 is the only runtime dependency. The new editors use no external libraries or CDNs.

## Run

Stop the old `python3 -m http.server` process with **Ctrl+C**, then run this from the project directory:

```bash
python3 server.py
```

Open **http://localhost:8000/**. The root page opens the red **Lab Explorer**. Signing in switches to the blue **Lab Editor**.

Click **Admin login** and enter **`itr`** to edit. Anyone can view; the server requires an authenticated admin session for every save. Keep the terminal running. Press **Ctrl+C** to stop it.

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

Click a shelf to open a read-only information drawer. Simple shelves show shelf metadata; Complex shelves also list bins with names, contents, keywords, and matrix locations. Click a section to see its area, access status, and contained items. Close the drawer with **Close**, **Escape**, or its backdrop.

The grouped **Sections** and **Paths** checkboxes only affect visibility. They never modify saved data. Search matches partial text without regard to case, including shelf names, contents, keywords, and active Complex bin metadata. Matching results can be opened directly. Narrow screens support horizontal map scrolling and zoom.

## Edit normal items (Admin)

- Use **Add to Lab** at the top of the sidebar for shelves, tables, carts/seating, machines, walls, and labels.
- The **Item Directory** groups these types into independent collapsible categories. Search reveals matching groups without changing your normal collapse preferences.
- Select an item to edit its name, area, position, dimensions, colors, font, or position lock. Drag unlocked items or use arrow keys to move by one cell.
- Equipment cannot overlap other equipment or leave the outline. Labels wrap/shrink within their boxes.
- Sections and arrows are map-level elements. Their controls and direct editing are unavailable in normal item mode.

Editor groups use short ease-in/ease-out transitions, respect reduced-motion preferences, and remove collapsed controls from keyboard/pointer interaction.

## Lab Map Editor

As an admin, click **Lab Map Editor** in the header. Normal item controls disappear; physical items remain dimmed as context and cannot be dragged. Use the map groups to edit:

- **Outline & grid:** click a vertex, drag it, or use arrow keys for one-cell movements. Selected-point X/Y inputs and the full coordinate list stay available. Use **Delete point**, Delete/Backspace, or **Insert point after selected**. At least three distinct points with nonzero area must remain inside the grid. Arrow keys do not edit the map while typing.
- **Sections:** select an existing section or **Add section**. Edit its name, area, colors, fonts, and hatching. Existing section positions start locked; uncheck **Lock position and size** before moving/resizing. Section labels are placed in available space to avoid equipment.
- **Traffic arrows:** use the controls described below to move or reshape routes.

**Leave Lab Map Editor** returns to item editing and removes map-editing hit targets/handles. Changes remain in your instance draft until you explicitly save a named version. Login/logout and visibility/theme changes do not rewrite the saved lab.

The initial outline and placements remain the existing grid interpretation of the supplied floor-plan sketch, not a surveyed architectural drawing.

## Reset and saved-version history

Click **Version history / reset** in the lab toolbar. Select **Original layout** or a timestamped saved revision, then click **Restore selected layout**. Admin login is required to restore.

Restoring loads the selected layout into this editor instance’s draft. It does **not** write to disk or add a version. Opening history, Undo, Redo, and Reload saved also do not add versions. Shelf inventory files are unaffected. Click **Save changes**, enter a version name, and click **Save version** to make the draft persistent. Saved versions show their names in the history menu.

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
4. In Complex mode, select an empty cell to **Add bin here**, or edit an existing bin's name, contents, keywords, position, size, and style. Dragging, keyboard movement, and safe matrix resizing continue to work.
5. Switching either way preserves all metadata and every bin. Dormant bins remain stored in Simple mode but are not shown or indexed until Complex mode is active again.
6. Save a named version and reload to share and verify the shelf contents.

Each editor opens its saved contents or recovers its cached draft for this instance. **Save changes** (or Ctrl/Cmd+S) opens a version-name dialog; only confirming **Save version** writes changes to disk. Canceling the dialog leaves the draft unsaved. Saved lab versions appear in lab history; named shelf saves update that shelf’s independent file. Other browsers see saved data, not your draft.

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
- `explorer.js` — Read-only shelf/section drawers and search results.
- `editor_groups.js` — Accessible animated collapsible groups.
- `common.js`, `editor.css` — Auth, named saves, draft history, shared styling, and distinct themes.
- `data/lab.json` — Lab grid, sections, fixtures, footprint, and paths.
- `data/shelves/R01.json`, `R02.json`, etc. — **One independent file per shelf**, initially 34 rows × 30 columns. New files default to Simple mode while retaining an empty matrix for optional Complex use.
- `shelf_inventory_editor.html` — Original standalone editor, retained unchanged as a legacy reference. Its JSON format differs from the new matrices, and it does not use shared admin saving.

Each matrix cell is either `null` or a bin object. A bin is stored at its top-left cell; its `w` and `h` cover adjacent cells, which remain `null`. No overlapping bins are allowed. A small complete shelf file looks like:

```json
{
  "id": "R01",
  "revision": 0,
  "schemaVersion": 2,
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
```

The feature suite covers visitor, Admin, and Lab Map Editor flows; visibility/data separation; categories; adding every item type; outline selection, dragging, keyboard input, deletion; shelf mode persistence/migration; aggregated search; read-only panels; theme transitions; and 1440/768/390-pixel layouts. Tests use isolated fixture data.
