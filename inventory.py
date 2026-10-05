"""Structured stock independent of geometry history; dependency-free JSON model."""
import copy
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import hashlib
import json
import re

SAFE_ID = re.compile(r'^[A-Za-z0-9_-]{1,64}$')


def identify_bins(doc):
    """Deterministic, conservative legacy identities; never modifies its input."""
    result = copy.deepcopy(doc)
    used = {cell['id'] for row in result.get('matrix', []) for cell in row if cell and 'id' in cell}
    for r, row in enumerate(result.get('matrix', [])):
        for c, cell in enumerate(row):
            if cell and 'id' not in cell:
                signature = json.dumps([doc['id'], r, c, cell], sort_keys=True, ensure_ascii=False)
                candidate = 'legacy-' + hashlib.sha256(signature.encode()).hexdigest()[:32]
                while candidate in used:
                    candidate += 'x'
                cell['id'] = candidate
                used.add(candidate)
    return result


def empty_inventory():
    return dict(schemaVersion=1, revision=0, items={}, stocks={})


def location_key(shelf_id, bin_id=None):
    return shelf_id + ('/' + bin_id if bin_id else '')


def decimal_value(value, field, optional=True):
    if value is None or value == '':
        if optional:
            return None
        raise ValueError(f'{field} is required.')
    if not isinstance(value, str) or not re.fullmatch(r'\d{1,12}(\.\d{1,6})?', value):
        raise ValueError(f'{field} must be a nonnegative decimal (up to six decimal places).')
    try:
        number = Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f'Invalid {field}.') from error
    return format(number.normalize(), 'f')


def clean_text(value, field, limit=2000):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(f'Invalid {field} (maximum {limit} characters).')
    return value.strip()


def validate_item(item):
    if not isinstance(item, dict):
        raise ValueError('Invalid item.')
    result = {key: clean_text(item.get(key, ''), key, 10000 if key in ('description', 'notes') else 2000)
              for key in ('name', 'category', 'keywords', 'description', 'productLink', 'vendor', 'notes', 'priceUnit')}
    if not result['name'] or len(result['name']) > 500:
        raise ValueError('An item needs a name (maximum 500 characters).')
    if result['productLink'] and not re.match(r'^https?://[^\s]+$', result['productLink']):
        raise ValueError('Product links must use http:// or https://.')
    result['unitPrice'] = decimal_value(item.get('unitPrice'), 'Unit price')
    result['currency'] = clean_text(item.get('currency', ''), 'currency', 3).upper()
    if result['unitPrice'] is not None and (not re.fullmatch(r'[A-Z]{3}', result['currency']) or not result['priceUnit']):
        raise ValueError('A known price needs a three-letter currency and the priced unit (e.g. each or pack).')
    return result


def validate_stock(stock, items, locations, previous=None):
    if not isinstance(stock, dict) or stock.get('itemId') not in items:
        raise ValueError('Choose an existing item.')
    result = {key: stock.get(key) for key in ('itemId', 'shelfId', 'binId')}
    for key in ('shelfId', 'binId'):
        if result[key] is not None and (not isinstance(result[key], str) or not SAFE_ID.fullmatch(result[key])):
            raise ValueError('Invalid location ID.')
    if result['binId'] and not result['shelfId']:
        raise ValueError('A bin requires a shelf.')
    key = location_key(result['shelfId'], result['binId']) if result['shelfId'] else ''
    unchanged = previous and (previous.get('shelfId'), previous.get('binId')) == (result['shelfId'], result['binId'])
    if key and (key not in locations or not locations[key]['mapped']) and not unchanged:
        raise ValueError('Save this shelf/bin in a named layout first, or choose Unassigned.')
    result['tracking'] = stock.get('tracking', 'presence')
    if result['tracking'] not in ('exact', 'availability', 'presence'):
        raise ValueError('Choose exact quantity, availability, or presence only.')
    result['quantity'] = decimal_value(stock.get('quantity'), 'Quantity') if result['tracking'] == 'exact' else None
    result['availability'] = stock.get('availability', 'available') if result['tracking'] == 'availability' else None
    if result['tracking'] == 'availability' and result['availability'] not in ('available', 'low', 'out-of-stock'):
        raise ValueError('Invalid availability.')
    result['unit'] = clean_text(stock.get('unit', 'each'), 'unit', 100)
    if not result['unit']:
        raise ValueError('Enter a unit, such as each or pack.')
    result['notes'] = clean_text(stock.get('notes', ''), 'stock notes', 10000)
    result['archived'] = bool(previous and previous.get('archived'))
    result['locationLabel'] = locations.get(key, {}).get('label', previous.get('locationLabel', key) if previous else key) if key else 'Unassigned'
    return result


def estimated_value(item, stock):
    if (stock['tracking'] != 'exact' or stock.get('quantity') is None or item.get('unitPrice') is None or
            stock['unit'] != item.get('priceUnit')):
        return None
    # ISO currencies with zero/three/four minor digits; other codes use two.
    digits = 0 if item['currency'] in {'JPY','KRW','VND','CLP','ISK','PYG','RWF','UGX','XAF','XOF','XPF','BIF','DJF','GNF','KMF','VUV'} else 3 if item['currency'] in {'BHD','IQD','JOD','KWD','LYD','OMR','TND'} else 4 if item['currency'] in {'CLF','UYW'} else 2
    quantum = Decimal(1).scaleb(-digits)
    with localcontext() as context:
        context.prec = 50
        return dict(amount=format((Decimal(stock['quantity']) * Decimal(item['unitPrice'])).quantize(quantum, rounding=ROUND_HALF_UP), 'f'), currency=item['currency'])


def retire_bin_fields(doc):
    """Keep imported/restored prose recoverable without reviving editable bin fields."""
    result = copy.deepcopy(doc)
    legacy = result.setdefault('legacyBinText', {})
    if not isinstance(legacy, dict):
        raise ValueError('Invalid preserved bin text.')
    for row in result.get('matrix', []):
        for cell in row:
            if not cell:
                continue
            contents, keywords = cell.pop('contents', ''), cell.pop('keywords', '')
            clean_text(contents, 'Legacy bin contents', 10000)
            clean_text(keywords, 'Legacy bin keywords', 2000)
            if contents.strip() or keywords.strip():
                source = dict(contents=contents, keywords=keywords, converted=False)
                records = legacy.setdefault(cell['id'], [])
                if not isinstance(records, list):
                    raise ValueError('Invalid preserved bin text.')
                if source not in records:
                    records.append(source)
            if keywords.strip():
                cell['hasLegacyDescription'] = True
    if not legacy:
        result.pop('legacyBinText')
    return result


def convert_bin_contents(inventory, shelves):
    """Pure one-time conversion of current files, never historical snapshots."""
    doc = copy.deepcopy(inventory)
    converted_shelves = {}
    report = dict(schemaVersion=1, completed=True, converted=0, skippedDuplicates=0, needsReview=0, sources=[])
    for sid, original in sorted(shelves.items()):
        shelf = identify_bins(original)
        for row in shelf.get('matrix', []):
            for cell in row:
                if not cell:
                    continue
                contents, keywords = cell.get('contents', ''), cell.get('keywords', '')
                if not contents.strip() and not keywords.strip():
                    continue
                record = dict(shelfId=sid, binId=cell['id'], binName=cell['name'], contents=contents,
                              keywords=keywords, entries=[])
                for name in (part.strip() for part in contents.split(',')):
                    if not name:
                        continue
                    candidates = [(stock_id, stock) for stock_id, stock in doc['stocks'].items()
                                  if not stock.get('archived') and stock.get('shelfId') == sid
                                  and stock.get('binId') == cell['id']
                                  and doc['items'][stock['itemId']]['name'].strip().casefold() == name.casefold()]
                    if len(candidates) > 1 or len(name) > 500:
                        record['entries'].append(dict(name=name, status='review', candidates=[stock_id for stock_id, _ in candidates]))
                        report['needsReview'] += 1
                    elif candidates:
                        report['skippedDuplicates'] += 1
                        record['entries'].append(dict(name=name, status='duplicate', stockId=candidates[0][0]))
                    else:
                        fingerprint = hashlib.sha256(json.dumps([sid,cell['id'],name],ensure_ascii=False).encode()).hexdigest()[:32]
                        item_id, stock_id = 'MI-'+fingerprint, 'MS-'+fingerprint
                        if item_id in doc.get('deletedItems', {}):
                            record['entries'].append(dict(name=name, status='deleted', candidates=[]))
                            continue
                        if item_id in doc['items'] or stock_id in doc['stocks']:
                            report['needsReview'] += 1
                            record['entries'].append(dict(name=name, status='review', candidates=[]))
                            continue
                        doc['items'][item_id] = validate_item(dict(name=name))
                        doc['stocks'][stock_id] = dict(itemId=item_id,shelfId=sid,binId=cell['id'],tracking='presence',
                            quantity=None,availability=None,unit='each',notes='',archived=False,
                            locationLabel=(shelf.get('name') or sid)+' / '+cell['name'])
                        report['converted'] += 1
                        record['entries'].append(dict(name=name, status='converted',stockId=stock_id))
                report['sources'].append(record)
        retired = retire_bin_fields(shelf)
        outcomes = {(source['binId'], source['contents'], source['keywords']):
                    not any(entry['status'] == 'review' for entry in source['entries'])
                    for source in report['sources'] if source['shelfId'] == sid}
        for bin_id, records in retired.get('legacyBinText', {}).items():
            for record in records:
                source_key = (bin_id, record['contents'], record['keywords'])
                if source_key in outcomes:
                    record['converted'] = outcomes[source_key]
        converted_shelves[sid] = retired
    return doc, converted_shelves, report


def bin_display_name(bin, shelf_id, inventory, shelf=None):
    name = bin.get('name', '')
    if name.strip().casefold() != 'new bin':
        return name or 'Unnamed bin'
    meaningful = bool(bin.get('contents', '').strip() or bin.get('keywords', '').strip() or
                      bin.get('notes', '').strip() or bin.get('description', '').strip() or bin.get('hasLegacyDescription'))
    sources = (shelf or {}).get('legacyBinText', {}).get(bin.get('id'), [])
    meaningful = meaningful or any(source.get('keywords', '').strip() or
        (not source.get('converted') and source.get('contents', '').strip()) for source in sources)
    populated = any(not stock.get('archived') and stock.get('shelfId') == shelf_id and stock.get('binId') == bin.get('id')
                    for stock in inventory.get('stocks', {}).values())
    return name if meaningful or populated else 'empty'
