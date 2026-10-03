'use strict';
const inventoryController = {
  data: null,
  endpoint: '/api/lab',
  filename: 'lab.json',
  inventoryOnly: true,
  render: renderInventoryList,
};
function renderInventoryList() {
  const host = $('#inventoryList');
  ['inventoryAdd', 'inventoryAudit', 'inventoryBackup'].forEach((id) => {
    $('#' + id).hidden = !isAdmin;
  });
  if (!inventoryState) {
    host.textContent = 'Loading recorded inventory…';
    return;
  }
  const query = $('#inventorySearch').value.trim().toLowerCase(),
    filter = $('#inventoryFilter').value;
  const entries = Object.entries(inventoryState.items)
    .filter(([id, item]) => {
      const stocks = Object.values(inventoryState.stocks).filter(
        (stock) => stock.itemId === id,
      );
      const terms = [
        item.name,
        item.category,
        item.keywords,
        item.description,
        item.vendor,
        item.notes,
        item.productLink,
        ...stocks.map(
          (stock) => stock.notes + ' ' + inventoryLocation(stock).label,
        ),
      ]
        .join(' ')
        .toLowerCase();
      const matchesFilter =
        filter === 'all' ||
        stocks.some((stock) =>
          filter === 'archived'
            ? stock.archived
            : !stock.archived &&
              (filter === 'mapped'
                ? inventoryLocation(stock).mapped
                : !inventoryLocation(stock).mapped),
        );
      return terms.includes(query) && matchesFilter;
    })
    .sort((a, b) => a[1].name.localeCompare(b[1].name));
  host.replaceChildren();
  $('#inventoryCount').textContent =
    `${entries.length} items · inventory revision ${inventoryState.revision}`;
  if (!entries.length) {
    host.append(
      inventoryNode(
        'p',
        Object.keys(inventoryState.items).length
          ? 'No matching inventory. Try another search or location filter.'
          : 'No structured inventory recorded yet. Existing shelf and bin descriptions are preserved as notes. Sign in and add your first item here or open a shelf/bin on LAB MAP.',
        'inventory-empty',
      ),
    );
  }
  for (const [itemId, item] of entries) {
    const card = inventoryNode('article', '', 'inventory-card');
    card.dataset.inventoryItem = itemId;
    const heading = inventoryNode('h2', '');
    heading.append(
      inventoryButton(item.name, () => showInventoryDetails(itemId)),
    );
    card.append(heading);
    if (item.category || item.vendor)
      card.append(
        inventoryNode(
          'p',
          [item.category, item.vendor].filter(Boolean).join(' · '),
          'muted',
        ),
      );
    if (item.description) card.append(inventoryNode('p', item.description));
    const stocks = Object.values(inventoryState.stocks).filter(
      (stock) => stock.itemId === itemId,
    );
    if (!stocks.length)
      card.append(inventoryNode('p', 'No stock locations recorded.'));
    for (const stock of stocks) {
      const place = inventoryLocation(stock);
      const row = inventoryNode('div', '', 'inventory-location-row');
      row.append(
        inventoryNode('strong', place.label),
        inventoryNode('span', inventoryStockText(stock)),
      );
      if (stock.archived)
        row.append(inventoryNode('small', 'Archived · stock preserved'));
      if (!place.mapped)
        row.append(
          inventoryNode(
            'small',
            stock.shelfId ? 'Unmapped · stock preserved' : 'Unassigned',
          ),
        );
      if (place.hidden)
        row.append(inventoryNode('small', 'Bin hidden by Simple mode'));
      if (place.mapped)
        row.append(
          inventoryButton('Show on map', () =>
            navigateInventoryLocation(stock),
          ),
        );
      card.append(row);
    }
    card.append(
      inventoryButton('Item details / all locations', () =>
        showInventoryDetails(itemId),
      ),
    );
    host.append(card);
  }
}
$('#inventorySearch').addEventListener('input', renderInventoryList);
$('#inventoryFilter').addEventListener('change', renderInventoryList);
$('#inventoryAdd').addEventListener('click', () => openInventoryEditor());
$('#inventoryRefresh').addEventListener('click', refreshInventory);
$('#inventoryBackup').addEventListener('click', async () => {
  try {
    download(await api('/api/backup'), 'itr-full-lab-backup.json');
    message(
      'Full saved lab backup downloaded · includes layout, shelves, inventory, audit/history and defaults; excludes private drafts',
    );
  } catch (error) {
    message(error.message, true);
  }
});
$('#inventoryAudit').addEventListener('click', async () => {
  try {
    const entries = await api('/api/inventory/history');
    const host = $('#inventoryAuditList');
    host.replaceChildren();
    if (!entries.length)
      host.append(inventoryNode('p', 'No inventory changes yet.'));
    for (const entry of entries) {
      const row = inventoryNode('article', '', 'inventory-card');
      row.append(
        inventoryNode(
          'p',
          `Revision ${entry.revision} · ${entry.reason || 'Initial inventory'} · ${entry.savedAt ? new Date(entry.savedAt).toLocaleString() : ''}`,
        ),
      );
      row.append(
        inventoryButton('Download audit snapshot', async () => {
          try {
            download(
              await api('/api/inventory/history/' + entry.revision),
              `inventory-audit-${entry.revision}.json`,
            );
            message(
              'Audit reference downloaded. Full lab backup is required for complete recovery.',
            );
          } catch (error) {
            message(error.message, true);
          }
        }),
      );
      host.append(row);
    }
    $('#inventoryAuditDialog').showModal();
  } catch (error) {
    message(error.message, true);
  }
});
$('#inventoryAuditClose').addEventListener('click', () =>
  $('#inventoryAuditDialog').close(),
);
document.addEventListener('inventory-updated', renderInventoryList);
startApp(inventoryController);
