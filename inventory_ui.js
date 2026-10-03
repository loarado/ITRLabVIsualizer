'use strict';
let inventoryState = null,
  inventoryTicket = 0,
  inventoryEntry = null,
  inventoryEntryDirty = false,
  inventoryDetailId = null,
  inventoryTransferEntry = null,
  inventoryTransferDirty = false;
const itemInputKeys = [
  'name',
  'category',
  'keywords',
  'description',
  'productLink',
  'vendor',
  'unitPrice',
  'currency',
  'priceUnit',
  'notes',
];
const stockInputKeys = [
  'tracking',
  'quantity',
  'availability',
  'unit',
  'notes',
];
function inventoryNode(tag, text, className = '') {
  const node = document.createElement(tag);
  node.textContent = text;
  node.className = className;
  return node;
}
function inventoryButton(text, action) {
  const button = inventoryNode('button', text);
  button.type = 'button';
  button.addEventListener('click', action);
  return button;
}
function inventoryLocation(stock) {
  const key = stock.shelfId
    ? stock.shelfId + (stock.binId ? '/' + stock.binId : '')
    : '';
  const location = inventoryState?.locations[key];
  return {
    key,
    location,
    label: stock.shelfId
      ? location?.label || stock.locationLabel || stock.shelfId
      : 'Unassigned',
    mapped: !!location?.mapped,
    hidden: !!location?.hidden,
  };
}
function inventoryStockText(stock) {
  return stock.tracking === 'exact'
    ? `${stock.quantity === null ? 'Quantity unknown' : stock.quantity} ${stock.unit}`
    : stock.tracking === 'availability'
      ? `${stock.availability.replaceAll('-', ' ')} · ${stock.unit}`
      : `Present · counts not tracked · ${stock.unit}`;
}
async function refreshInventory() {
  const ticket = ++inventoryTicket;
  try {
    const state = await api('/api/inventory');
    if (ticket !== inventoryTicket) return;
    inventoryState = state;
    document.querySelectorAll('[data-stock-shelf]').forEach((host) => {
      inventoryLocationPanel(
        host,
        host.dataset.stockShelf,
        host.dataset.stockBin || null,
        host.dataset.stockAll === 'true',
      );
    });
    if (inventoryDetailId && $('#inventoryDetails').open)
      showInventoryDetails(inventoryDetailId);
    document.dispatchEvent(new Event('inventory-updated'));
  } catch (error) {
    message('Inventory could not load: ' + error.message, true);
  }
}
function inventoryLocationPanel(
  host,
  shelfId,
  binId = null,
  includeBins = false,
) {
  host.dataset.stockShelf = shelfId;
  host.dataset.stockBin = binId || '';
  host.dataset.stockAll = String(includeBins);
  host.classList.add('stock-panel');
  host.replaceChildren(inventoryNode('h3', 'Structured inventory'));
  host.append(
    inventoryNode(
      'p',
      'Shelf/bin contents and keywords are descriptive notes. Only the entries below record actual inventory.',
      'hint',
    ),
  );
  if (!inventoryState) {
    host.append(inventoryNode('p', 'Loading inventory…'));
    return;
  }
  const entries = Object.entries(inventoryState.stocks).filter(
    ([, stock]) =>
      !stock.archived &&
      stock.shelfId === shelfId &&
      (includeBins || stock.binId === binId),
  );
  if (!entries.length)
    host.append(
      inventoryNode(
        'p',
        'No inventory entries here yet. Descriptive notes have been kept as notes.',
        'muted',
      ),
    );
  for (const [, stock] of entries) {
    const row = inventoryNode('div', '', 'stock-row');
    const item = inventoryState.items[stock.itemId];
    row.append(
      inventoryButton(item.name, () => showInventoryDetails(stock.itemId)),
      inventoryNode('span', inventoryStockText(stock)),
    );
    if (includeBins && stock.binId)
      row.append(inventoryNode('small', inventoryLocation(stock).label));
    if (!inventoryLocation(stock).mapped)
      row.append(
        inventoryNode('small', 'Unmapped stock · preserved for relocation'),
      );
    if (inventoryLocation(stock).hidden)
      row.append(
        inventoryNode(
          'small',
          'Bin hidden by Simple mode · view or relocate in item details',
        ),
      );
    host.append(row);
  }
  if (isAdmin) {
    const key = shelfId + (binId ? '/' + binId : '');
    const location = inventoryState.locations[key];
    const add = inventoryButton(
      binId ? 'Add inventory to this bin' : 'Add inventory to this shelf',
      () => openInventoryEditor({ shelfId, binId }),
    );
    add.disabled = !location?.saved || !location?.mapped;
    host.append(add);
    if (add.disabled)
      host.append(
        inventoryNode(
          'p',
          'Save this location in a named layout before recording stock.',
          'hint',
        ),
      );
  }
}
function showInventoryDetails(itemId) {
  const item = inventoryState?.items[itemId];
  if (!item) return;
  inventoryDetailId = itemId;
  const host = $('#inventoryDetailContent');
  host.replaceChildren(inventoryNode('h2', item.name));
  for (const [key, title] of [
    ['category', 'Category'],
    ['keywords', 'Keywords'],
    ['description', 'Description'],
    ['vendor', 'Vendor'],
    ['notes', 'Item notes'],
  ]) {
    if (item[key])
      host.append(inventoryNode('h3', title), inventoryNode('p', item[key]));
  }
  if (item.productLink) {
    const link = inventoryNode('a', 'Product link');
    link.href = item.productLink;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    host.append(link);
  }
  host.append(
    inventoryNode(
      'p',
      item.unitPrice === null
        ? 'Unit price unknown'
        : `${item.currency} ${item.unitPrice} per ${item.priceUnit}`,
    ),
  );
  if (isAdmin)
    host.append(
      inventoryButton('Edit item details', () =>
        openInventoryEditor({ itemId, itemOnly: true }),
      ),
      inventoryButton('Add this item to another location', () =>
        openInventoryEditor({ itemId }),
      ),
    );
  host.append(inventoryNode('h3', 'All recorded locations'));
  const entries = Object.entries(inventoryState.stocks).filter(
    ([, stock]) => stock.itemId === itemId,
  );
  if (!entries.length)
    host.append(inventoryNode('p', 'No stock recorded yet.'));
  for (const [stockId, stock] of entries) {
    const card = inventoryNode('article', '', 'inventory-card');
    const place = inventoryLocation(stock);
    card.append(
      inventoryNode('h4', place.label + (stock.archived ? ' · Archived' : '')),
      inventoryNode('p', inventoryStockText(stock)),
    );
    if (!place.mapped)
      card.append(
        inventoryNode(
          'p',
          stock.shelfId
            ? 'Unmapped location · stock is preserved and can be relocated.'
            : 'Unassigned · choose a location when known.',
          'hint',
        ),
      );
    else {
      if (place.hidden)
        card.append(
          inventoryNode(
            'p',
            'This bin is retained but hidden by Simple shelf mode.',
            'hint',
          ),
        );
      card.append(
        inventoryButton('Show on map', () => navigateInventoryLocation(stock)),
      );
    }
    if (stock.notes) card.append(inventoryNode('p', stock.notes));
    if (stock.estimatedValue)
      card.append(
        inventoryNode(
          'p',
          `Estimated inventory value: ${stock.estimatedValue.currency} ${stock.estimatedValue.amount}`,
        ),
      );
    if (isAdmin) {
      card.append(
        inventoryButton('Edit stock / relocate', () =>
          openInventoryEditor({ itemId, stockId }),
        ),
      );
      if (
        !stock.archived &&
        stock.tracking === 'exact' &&
        stock.quantity !== null
      )
        card.append(
          inventoryButton('Transfer quantity', () =>
            openStockTransfer(stockId),
          ),
        );
      card.append(
        inventoryButton(
          stock.archived ? 'Reactivate entry' : 'Archive entry',
          async () => {
            if (
              !confirm(
                stock.archived
                  ? 'Reactivate this preserved stock entry?'
                  : 'Archive this entry? Its quantity and history remain recorded and visible in item details.',
              )
            )
              return;
            await inventoryMutation({
              action: stock.archived ? 'reactivate' : 'archive',
              stockId,
            });
          },
        ),
      );
    }
    host.append(card);
  }
  if (!$('#inventoryDetails').open) $('#inventoryDetails').showModal();
}
async function navigateInventoryLocation(stock) {
  const place = inventoryLocation(stock);
  if (!place.mapped) {
    message(
      'This location is unavailable on the current map. Its stock remains recorded.',
      true,
    );
    return;
  }
  $('#inventoryDetails').close();
  const target = `lab_overview.html?shelf=${encodeURIComponent(stock.shelfId)}${stock.binId ? '&bin=' + encodeURIComponent(stock.binId) : ''}`;
  if (app?.showInventoryLocation)
    await app.showInventoryLocation(stock.shelfId, stock.binId);
  else await leaveEditor(target);
}
function locationOptions(select, stock = {}) {
  select.replaceChildren(new Option('Unassigned', ''));
  Object.entries(inventoryState.locations)
    .filter(([, loc]) => loc.mapped && loc.saved)
    .forEach(([key, loc]) =>
      select.add(
        new Option(loc.label + (loc.hidden ? ' (hidden bin)' : ''), key),
      ),
    );
  const key = stock.shelfId
    ? stock.shelfId + (stock.binId ? '/' + stock.binId : '')
    : '';
  if (key && !Array.from(select.options).some((o) => o.value === key))
    select.add(new Option((stock.locationLabel || key) + ' (unmapped)', key));
  select.value = key;
}
function readInventoryForm() {
  const item = {},
    stock = {};
  itemInputKeys.forEach((key) => {
    item[key] = $('#inv-item-' + key).value;
  });
  stockInputKeys.forEach((key) => {
    stock[key] = $('#inv-stock-' + key).value;
  });
  const [shelfId, binId] = $('#inv-location').value.split('/');
  stock.shelfId = shelfId || null;
  stock.binId = binId || null;
  return {
    ...inventoryEntry,
    item,
    ...(!inventoryEntry.itemOnly ? { stock } : {}),
    reason: $('#inv-reason').value || 'Inventory correction / entry',
  };
}
function fillInventoryForm(entry) {
  itemInputKeys.forEach((key) => {
    $('#inv-item-' + key).value =
      entry.item?.[key] ??
      (key === 'currency' ? 'USD' : key === 'priceUnit' ? 'each' : '');
  });
  stockInputKeys.forEach((key) => {
    $('#inv-stock-' + key).value =
      entry.stock?.[key] ??
      ({ tracking: 'presence', availability: 'available', unit: 'each' }[key] ||
        '');
  });
  locationOptions($('#inv-location'), entry.stock);
  $('#inv-reason').value = entry.reason || '';
  $('#inv-stock-fields').hidden = !!entry.itemOnly;
  updateInventoryTracking();
}
function updateInventoryTracking() {
  $('#inv-quantity-field').hidden = $('#inv-stock-tracking').value !== 'exact';
  $('#inv-availability-field').hidden =
    $('#inv-stock-tracking').value !== 'availability';
}
function inventoryEntryKey() {
  return recoveryContext ? recoveryKey('inventory-entry') : null;
}
function stashInventoryEntry() {
  if (!inventoryEntry || !inventoryEntryDirty || !recoveryContext) return;
  try {
    localStorage.setItem(
      inventoryEntryKey(),
      JSON.stringify({
        format: 1,
        timestamp: Date.now(),
        entry: readInventoryForm(),
      }),
    );
  } catch {
    $('#inv-feedback').textContent =
      'Browser recovery storage is unavailable. Keep this entry open until saved.';
  }
}
function clearInventoryEntry() {
  try {
    if (inventoryEntryKey()) localStorage.removeItem(inventoryEntryKey());
  } catch {}
  inventoryEntryDirty = false;
  inventoryEntry = null;
}
function openInventoryEditor(options = {}, recovered = null) {
  if (!isAdmin || !inventoryState) return;
  const stock = inventoryState.stocks[options.stockId];
  const itemId = stock?.itemId || options.itemId || null;
  inventoryEntry = recovered || {
    action: 'save',
    revision: inventoryState.revision,
    operationId: 'op-' + uniqueId(),
    itemId,
    stockId: options.stockId || null,
    itemOnly: !!options.itemOnly,
  };
  const existing = $('#inv-existing');
  existing.replaceChildren(new Option('Create a new, distinct item', ''));
  Object.entries(inventoryState.items)
    .sort((a, b) => a[1].name.localeCompare(b[1].name))
    .forEach(([id, item]) => existing.add(new Option(item.name, id)));
  existing.value = inventoryEntry.itemId || '';
  existing.disabled = !!inventoryEntry.stockId || inventoryEntry.itemOnly;
  const entry = recovered || {
    ...inventoryEntry,
    item: inventoryState.items[itemId],
    stock: stock || {
      shelfId: options.shelfId || null,
      binId: options.binId || null,
    },
  };
  fillInventoryForm(entry);
  inventoryEntryDirty = !!recovered;
  $('#inv-feedback').textContent = recovered
    ? 'Recovered unsaved entry. Review it, then Save inventory.'
    : '';
  $('#inv-conflict').hidden = true;
  if (!$('#inventoryEditor').open) $('#inventoryEditor').showModal();
  $('#inv-item-name').focus();
}
async function inventoryMutation(body) {
  try {
    const result = await api('/api/inventory', 'POST', {
      revision: inventoryState.revision,
      operationId: 'op-' + uniqueId(),
      ...body,
    });
    await refreshInventory();
    try {
      localStorage.setItem('itr-inventory-changed', String(Date.now()));
    } catch {}
    message('Inventory saved · layout history unchanged');
    return result;
  } catch (error) {
    message(error.message, true);
    return null;
  }
}
function openStockTransfer(stockId, recovered = null) {
  inventoryTransferEntry = recovered || {
    operationId: 'op-' + uniqueId(),
    stockId,
    revision: inventoryState.revision,
  };
  inventoryTransferDirty = !!recovered;
  $('#transfer-stock').value = stockId;
  $('#transfer-amount').value = recovered?.amount || '';
  $('#transfer-feedback').textContent = '';
  locationOptions($('#transfer-location'), recovered || {});
  $('#transfer-revision').value = inventoryTransferEntry.revision;
  $('#inventoryTransfer').showModal();
}
async function inventoryAuthChanged(admin) {
  if (!admin) {
    inventoryEntryDirty = false;
    inventoryEntry = null;
    inventoryTransferDirty = false;
    inventoryTransferEntry = null;
    $('#inventoryEditor')?.close();
    $('#inventoryTransfer')?.close();
    $('#inventoryDetails')?.close();
  }
  await refreshInventory();
  if (admin && recoveryContext && !inventoryEntry) {
    try {
      const raw = localStorage.getItem(inventoryEntryKey());
      const record = raw && JSON.parse(raw);
      if (
        record?.format === 1 &&
        Number.isFinite(record.timestamp) &&
        Date.now() - record.timestamp < recoveryLifetime &&
        record.timestamp <= Date.now() + 60000 &&
        record.entry?.action === 'save' &&
        Number.isInteger(record.entry.revision)
      )
        openInventoryEditor({}, record.entry);
    } catch {
      message('Could not recover the unsaved inventory entry.', true);
    }
  }
  if (admin && recoveryContext && !inventoryEntry && !inventoryTransferEntry) {
    try {
      const raw = localStorage.getItem(recoveryKey('inventory-transfer'));
      const record = raw && JSON.parse(raw);
      if (
        record?.entry?.action === 'transfer' &&
        Date.now() - record.timestamp < recoveryLifetime &&
        record.timestamp <= Date.now() + 60000
      )
        openStockTransfer(record.entry.stockId, record.entry);
    } catch {
      message('Could not recover the unsaved stock transfer.', true);
    }
  }
}
function readTransferForm() {
  const [shelfId, binId] = $('#transfer-location').value.split('/');
  return {
    ...inventoryTransferEntry,
    action: 'transfer',
    amount: $('#transfer-amount').value,
    shelfId: shelfId || null,
    binId: binId || null,
  };
}
function stashTransfer() {
  if (!inventoryTransferEntry || !recoveryContext) return;
  try {
    localStorage.setItem(
      recoveryKey('inventory-transfer'),
      JSON.stringify({ timestamp: Date.now(), entry: readTransferForm() }),
    );
  } catch {
    $('#transfer-feedback').textContent =
      'Browser recovery storage is unavailable. Keep this transfer open until saved.';
  }
}
function clearTransfer() {
  inventoryTransferDirty = false;
  inventoryTransferEntry = null;
  try {
    localStorage.removeItem(recoveryKey('inventory-transfer'));
  } catch {}
}
function setupInventoryEditor() {
  const dialog = document.createElement('dialog');
  dialog.id = 'inventoryEditor';
  dialog.className = 'inventory-dialog';
  const labels = {
    name: 'Item name *',
    category: 'Category',
    keywords: 'Keywords',
    description: 'Description',
    productLink: 'Product link',
    vendor: 'Vendor',
    unitPrice: 'Unit price (blank = unknown)',
    currency: 'Currency',
    priceUnit: 'Price per unit (each / pack)',
    notes: 'Item notes',
  };
  const fields = itemInputKeys
    .map(
      (key) =>
        `<label class="field">${labels[key]}<${['description', 'notes'].includes(key) ? 'textarea' : 'input'} id="inv-item-${key}" ${key === 'name' ? 'required maxlength="500"' : ''}${['unitPrice'].includes(key) ? ' inputmode="decimal"' : ''}>${['description', 'notes'].includes(key) ? '</textarea>' : ''}</label>`,
    )
    .join('');
  dialog.innerHTML = `<form id="inventoryForm"><h2>Inventory entry</h2><p class="hint">Save inventory writes shared item and stock records immediately. It does not save or restore a map version. Blank quantity or price stays unknown.</p><label class="field">Item identity<select id="inv-existing"></select></label><p class="hint">Choose an existing item to keep the same identity across locations. Editing its details updates every location. Similar names are never merged automatically.</p><div class="inventory-form-grid">${fields}</div><fieldset id="inv-stock-fields"><legend>Stock at this location</legend><label class="field">Location<select id="inv-location"></select></label><label class="field">Tracking<select id="inv-stock-tracking"><option value="presence">Presence only (no counts)</option><option value="exact">Exact quantity (or unknown)</option><option value="availability">Approximate availability</option></select></label><label class="field" id="inv-quantity-field">Quantity (blank = unknown)<input id="inv-stock-quantity" inputmode="decimal"></label><label class="field" id="inv-availability-field">Availability<select id="inv-stock-availability"><option value="available">Available</option><option value="low">Low</option><option value="out-of-stock">Out of stock</option></select></label><label class="field">Unit of measure *<input id="inv-stock-unit" value="each"></label><p class="hint">Use “each” for individual pieces or “pack” for packages. A quantity of 3 packs is not 3 individual pieces. Estimated value is shown only when stock and priced units match.</p><label class="field">Stock notes<textarea id="inv-stock-notes"></textarea></label></fieldset><label class="field">Correction / movement note<input id="inv-reason" maxlength="500"></label><div id="inv-conflict" hidden><h3>Latest saved record</h3><pre id="inv-latest"></pre><button id="inv-reconcile" type="button">I reviewed the latest record; keep my correction</button><button id="inv-use-latest" type="button">Use latest saved values</button></div><p id="inv-feedback" role="alert"></p><div class="actions"><button class="primary" id="inv-save" type="submit">Save inventory</button><button id="inv-cancel" type="button">Cancel</button></div></form>`;
  const details = document.createElement('dialog');
  details.id = 'inventoryDetails';
  details.className = 'inventory-dialog';
  details.innerHTML =
    '<div id="inventoryDetailContent"></div><button id="inventoryDetailClose">Close item details</button>';
  const transfer = document.createElement('dialog');
  transfer.id = 'inventoryTransfer';
  transfer.innerHTML =
    '<form id="transferForm"><h2>Transfer quantity</h2><p class="hint">Moves stock in the same unit. The source decreases and destination increases together.</p><input id="transfer-stock" type="hidden"><input id="transfer-revision" type="hidden"><label class="field">Amount<input id="transfer-amount" inputmode="decimal" required></label><label class="field">Destination<select id="transfer-location"></select></label><p id="transfer-feedback" role="alert"></p><div class="actions"><button class="primary" type="submit">Transfer stock</button><button id="transfer-cancel" type="button">Cancel</button></div></form>';
  document.body.append(dialog, details, transfer);
  $('#inventoryDetailClose').addEventListener('click', () => {
    inventoryDetailId = null;
    details.close();
  });
  const cancel = (event) => {
    event?.preventDefault();
    if (
      inventoryEntryDirty &&
      !confirm('Discard this unsaved inventory entry?')
    )
      return;
    clearInventoryEntry();
    dialog.close();
  };
  $('#inv-cancel').addEventListener('click', cancel);
  dialog.addEventListener('cancel', cancel);
  $('#inventoryForm').addEventListener('input', () => {
    inventoryEntryDirty = true;
    inventoryEntry.operationId = 'op-' + uniqueId();
    updateInventoryTracking();
    stashInventoryEntry();
  });
  $('#inventoryForm').addEventListener('change', stashInventoryEntry);
  $('#inv-existing').addEventListener('change', () => {
    inventoryEntry.itemId = $('#inv-existing').value || null;
    itemInputKeys.forEach((key) => {
      $('#inv-item-' + key).value =
        inventoryState.items[inventoryEntry.itemId]?.[key] ??
        (key === 'currency' ? 'USD' : key === 'priceUnit' ? 'each' : '');
    });
    inventoryEntryDirty = true;
    stashInventoryEntry();
  });
  $('#inventoryForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const body = readInventoryForm();
    inventoryEntryDirty = true;
    stashInventoryEntry();
    $('#inv-save').disabled = true;
    $('#inventoryForm').inert = true;
    try {
      await api('/api/inventory', 'POST', body);
      clearInventoryEntry();
      dialog.close();
      await refreshInventory();
      try {
        localStorage.setItem('itr-inventory-changed', String(Date.now()));
      } catch {}
      message('Inventory saved · layout history unchanged');
    } catch (error) {
      $('#inv-feedback').textContent =
        error.message +
        (!error.status || error.status >= 500
          ? ' Entry retained. Retry without changing the form to check whether the save committed.'
          : '');
      if (error.status === 409) {
        await refreshInventory();
        const latestItem = inventoryState.items[body.itemId],
          latestStock = inventoryState.stocks[body.stockId];
        const details = [
          `Saved inventory revision ${inventoryState.revision}`,
          inventoryState.lastChange?.reason || '',
        ];
        if (latestItem)
          itemInputKeys.forEach((key) =>
            details.push(
              `${key === 'name' ? 'Item name' : key}: ${latestItem[key] ?? 'Unknown'}`,
            ),
          );
        else
          details.push(
            'Recorded items: ' +
              Object.values(inventoryState.items)
                .map((item) => item.name)
                .join(', '),
          );
        if (latestStock)
          details.push(
            'Location: ' + inventoryLocation(latestStock).label,
            'Stock: ' + inventoryStockText(latestStock),
            'Stock notes: ' + (latestStock.notes || ''),
          );
        $('#inv-latest').textContent = details.filter(Boolean).join('\n');
        Object.entries(inventoryState.items).forEach(([id, item]) => {
          if (
            !Array.from($('#inv-existing').options).some(
              (option) => option.value === id,
            )
          )
            $('#inv-existing').add(new Option(item.name, id));
        });
        $('#inv-conflict').hidden = false;
      }
    } finally {
      $('#inv-save').disabled = !isAdmin;
      $('#inventoryForm').inert = false;
    }
  });
  $('#inv-reconcile').addEventListener('click', () => {
    inventoryEntry.revision = inventoryState.revision;
    inventoryEntry.operationId = 'op-' + uniqueId();
    $('#inv-conflict').hidden = true;
    $('#inv-feedback').textContent =
      'Correction kept after review. Save inventory to apply it.';
    stashInventoryEntry();
  });
  $('#inv-use-latest').addEventListener('click', () =>
    openInventoryEditor(inventoryEntry),
  );
  const cancelTransfer = (event) => {
    event?.preventDefault();
    if (inventoryTransferDirty && !confirm('Discard this unsaved transfer?'))
      return;
    clearTransfer();
    transfer.close();
  };
  $('#transfer-cancel').addEventListener('click', cancelTransfer);
  transfer.addEventListener('cancel', cancelTransfer);
  $('#transferForm').addEventListener('input', () => {
    inventoryTransferDirty = true;
    inventoryTransferEntry.operationId = 'op-' + uniqueId();
    stashTransfer();
  });
  $('#transferForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    inventoryTransferDirty = true;
    stashTransfer();
    const submit = event.submitter;
    submit.disabled = true;
    $('#transferForm').inert = true;
    const result = await inventoryMutation(readTransferForm());
    submit.disabled = !isAdmin;
    $('#transferForm').inert = false;
    if (result) {
      clearTransfer();
      transfer.close();
    } else
      $('#transfer-feedback').textContent =
        $('#status').textContent +
        ' Retry the same transfer to check a failed save; after a conflict, cancel and reopen using current stock.';
  });
  window.addEventListener('beforeunload', (event) => {
    if (inventoryEntryDirty || inventoryTransferDirty) {
      stashInventoryEntry();
      if (inventoryTransferDirty) stashTransfer();
      event.preventDefault();
      event.returnValue = '';
    }
  });
  window.addEventListener('storage', (event) => {
    if (event.key === 'itr-inventory-changed') refreshInventory();
  });
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) refreshInventory();
  });
}
setupInventoryEditor();

const sectionNavigation = document.createElement('nav');
sectionNavigation.className = 'section-navigation';
sectionNavigation.setAttribute('aria-label', 'Lab sections');
for (const [name, target] of [
  ['LAB MAP', 'lab_overview.html'],
  ['LAB INVENTORY', 'lab_inventory.html'],
]) {
  const link = inventoryNode('a', name, 'button');
  link.href = target;
  if (
    location.pathname.endsWith('lab_inventory.html') ===
    (target === 'lab_inventory.html')
  )
    link.setAttribute('aria-current', 'page');
  link.addEventListener('click', async (event) => {
    event.preventDefault();
    await leaveEditor(target);
  });
  sectionNavigation.append(link);
}
$('header').after(sectionNavigation);
