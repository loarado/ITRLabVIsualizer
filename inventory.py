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
    result['locationLabel'] = locations.get(key, {}).get('label', previous.get('locationLabel', 'Unassigned') if previous else 'Unassigned')
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
