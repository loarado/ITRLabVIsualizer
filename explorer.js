'use strict';
let explorerRequest = 0,
  explorerCloseTimer;
function infoField(title, value) {
  const block = document.createElement('div');
  block.className = 'info-field';
  const heading = document.createElement('h3');
  heading.textContent = title;
  const text = document.createElement('p');
  text.textContent = value || 'Not recorded';
  block.append(heading, text);
  return block;
}
function renderShelfInformation(
  host,
  data,
  fallbackName = 'Shelf',
  targetBin = null,
) {
  host._disposeShelfGrid?.();
  host._disposeShelfGrid = null;
  const shelf = normalizeShelf(data, fallbackName);
  host.replaceChildren();
  const label = document.createElement('p');
  label.className = 'eyebrow';
  label.textContent =
    shelf.mode === 'simple' ? 'Simple shelf' : 'Complex shelf';
  const title = document.createElement('h2');
  title.textContent = shelf.name || fallbackName;
  host.append(
    label,
    title,
    infoField('Descriptive notes', shelf.contents),
    infoField('Keywords', shelf.keywords),
  );
  const stockPanel = document.createElement('section');
  inventoryLocationPanel(stockPanel, shelf.id, null, true);
  host.append(stockPanel);
  if (targetBin && shelf.mode === 'simple')
    host.append(
      infoField(
        'Retained bin',
        'Simple mode hides bins on the shelf canvas. This navigation preview exposes the retained bin and its inventory.',
      ),
    );
  if (shelf.mode === 'complex' || shelf.decor.length || targetBin)
    readOnlyShelfGrid(
      host,
      targetBin ? { ...shelf, mode: 'complex' } : shelf,
      targetBin,
    );
  if (shelf.mode === 'complex' || targetBin) {
    const list = document.createElement('div');
    list.className = 'bin-information';
    let count = 0;
    shelfBins(shelf).forEach(({ bin, r, c }) => {
      count++;
      const card = document.createElement('article');
      card.className = 'bin-card';
      const name = document.createElement('h3');
      name.textContent = bin.name || 'Unnamed bin';
      const location = document.createElement('p');
      location.className = 'muted';
      location.textContent = `Row ${r + 1} · Column ${c + 1} · ${bin.w} × ${bin.h} cells`;
      card.append(
        name,
        location,
        infoField('Descriptive notes', bin.contents),
        infoField('Keywords', bin.keywords),
      );
      card.dataset.binId = bin.id;
      card.classList.toggle('inventory-target', bin.id === targetBin);
      card.tabIndex = -1;
      const stockPanel = document.createElement('section');
      inventoryLocationPanel(stockPanel, shelf.id, bin.id);
      card.append(stockPanel);
      list.append(card);
    });
    const heading = document.createElement('h3');
    heading.textContent = `Bins (${count})`;
    host.append(heading, list);
    if (!count) host.append(infoField('Inventory', 'No bins recorded.'));
    if (targetBin) {
      const target = Array.from(list.children).find(
        (card) => card.dataset.binId === targetBin,
      );
      if (target)
        requestAnimationFrame(() => {
          target.scrollIntoView({ block: 'nearest' });
          target.focus({ preventScroll: true });
        });
      else
        host.append(
          infoField(
            'Location unavailable',
            'The requested bin is absent from this shelf. Its stock remains in LAB INVENTORY for relocation.',
          ),
        );
    }
  }
}
function closeExplorer(immediate = false) {
  const panel = $('#explorerPanel');
  if (!panel) return;
  explorerRequest++;
  clearTimeout(explorerCloseTimer);
  $('#explorerContent')._disposeShelfGrid?.();
  if (immediate) {
    panel.close();
    panel.classList.remove('closing');
    return;
  }
  panel.classList.add('closing');
  explorerCloseTimer = setTimeout(() => {
    panel.close();
    panel.classList.remove('closing');
  }, 180);
}
function openExplorer() {
  const panel = $('#explorerPanel');
  clearTimeout(explorerCloseTimer);
  panel.classList.remove('closing');
  if (!panel.open) panel.showModal();
}
async function inspectShelf(item, targetBin = null, allowEditor = false) {
  if (isAdmin && !allowEditor) return;
  const admin = isAdmin;
  const ticket = ++explorerRequest;
  $('#explorerContent').textContent = 'Loading shelf…';
  openExplorer();
  try {
    const cached = admin
      ? await api('/api/drafts/shelves/' + encodeURIComponent(item.id))
      : null;
    const data =
      cached?.data ||
      (await api(`/api/shelves/${encodeURIComponent(item.id)}`));
    if (ticket !== explorerRequest || isAdmin !== admin) return;
    renderShelfInformation($('#explorerContent'), data, item.name, targetBin);
    $('#explorerContent').append(
      infoField('Location ID', item.locationId || item.id),
    );
    if (admin) {
      const edit = inventoryButton('Open shelf editor', () =>
        leaveEditor(
          'shelf_editor.html?id=' +
            encodeURIComponent(item.id) +
            (targetBin ? '&bin=' + encodeURIComponent(targetBin) : ''),
        ),
      );
      $('#explorerContent').append(edit);
    }
  } catch (error) {
    if (ticket === explorerRequest)
      $('#explorerContent').textContent = error.message;
  }
}
if ($('#explorerPanel')) {
  $('#closeExplorer').addEventListener('click', () => closeExplorer());
  $('#explorerPanel').addEventListener('cancel', (event) => {
    event.preventDefault();
    closeExplorer();
  });
  $('#explorerPanel').addEventListener('click', (event) => {
    const rect = event.currentTarget.getBoundingClientRect();
    if (
      event.target === event.currentTarget &&
      (event.clientX < rect.left ||
        event.clientX > rect.right ||
        event.clientY < rect.top ||
        event.clientY > rect.bottom)
    )
      closeExplorer();
  });
}
function inspectSection(section) {
  if (isAdmin) return;
  explorerRequest++;
  const host = $('#explorerContent');
  host.replaceChildren();
  const title = document.createElement('h2');
  title.textContent = section.name;
  const contained = lab.data.items.filter(
    (item) =>
      item.kind !== 'section' && sectionFor(item, lab.data)?.id === section.id,
  );
  host.append(
    title,
    infoField('Area', section.name),
    infoField(
      'Access',
      section.restricted ? 'No access — restricted area' : 'Lab section',
    ),
    infoField(
      'In this section',
      contained.length
        ? contained.map((item) => item.name).join('\n')
        : 'No listed items.',
    ),
  );
  openExplorer();
}
function inspectItem(item) {
  if (isAdmin) return;
  explorerRequest++;
  const host = $('#explorerContent');
  host.replaceChildren();
  const title = document.createElement('h2');
  title.textContent = item.name;
  host.append(
    title,
    infoField('Type', item.kind),
    infoField('Area', itemArea(item, lab.data)),
    infoField('Location ID', item.locationId || item.id),
  );
  openExplorer();
}
function renderExplorerResults(items, query) {
  const host = $('#explorerResults');
  host.replaceChildren();
  host.hidden = isAdmin || !query;
  if (host.hidden) return;
  if (!items.length) {
    host.textContent = 'No matching shelves or items.';
    return;
  }
  items.forEach((item) => {
    const button = document.createElement('button');
    button.textContent = `${shelfIndex[item.id]?.name || item.name} · ${item.locationId || item.id}`;
    if (shelfIndex[item.id]?.structuredItems?.length)
      button.textContent +=
        ' · Structured inventory: ' +
        shelfIndex[item.id].structuredItems.join(', ');
    button.addEventListener('click', () => choose(item.id));
    host.append(button);
  });
}
