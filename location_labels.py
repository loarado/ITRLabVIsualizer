"""Human labels are reserved independently of immutable shelf IDs."""
import copy
import re

GENERATED = re.compile(r'^S-[a-fA-F0-9]{8,}$')


def empty_labels():
    return dict(schemaVersion=1, labels={}, reserved={})


def assign_labels(layout, registry, repair=False):
    """Pure allocation. The caller holds the server lock and journals reservations."""
    registry = copy.deepcopy(registry)
    labels, reserved = registry['labels'], registry['reserved']
    seen = set()
    for item in layout['items']:
        if item['kind'] != 'shelf':
            continue
        sid = item['id']
        requested = item.get('locationId', '').strip()
        if not requested or (requested == sid and GENERATED.fullmatch(sid)):
            requested = labels.get(sid, '')
            if not requested and not GENERATED.fullmatch(sid):
                requested = sid
        if requested and (requested.casefold() in seen or reserved.get(requested.casefold(), sid) != sid):
            if not repair and sid in labels:
                raise ValueError('Location ID already belongs to another shelf: ' + requested)
            requested = labels.get(sid, '')
            if requested and (requested.casefold() in seen or reserved.get(requested.casefold(),sid) != sid):
                requested = ''
        if not requested:
            number = 1
            used_numbers = {int(match.group(1)) for label in reserved for match in [re.fullmatch(r's-(\d+)',label)] if match}
            while number in used_numbers or 's-' + str(number) in seen:
                number += 1
            requested = 'S-' + str(number)
        item['locationId'] = requested
        labels[sid] = requested
        reserved[requested.casefold()] = sid
        seen.add(requested.casefold())
    return registry


def validate_labels(doc):
    if not isinstance(doc, dict) or doc.get('schemaVersion') != 1 or not isinstance(doc.get('labels'),dict) or not isinstance(doc.get('reserved'),dict):
        raise ValueError('Invalid location-label registry.')
    for sid, label in doc['labels'].items():
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',sid) or not isinstance(label,str) or not label.strip() or len(label)>100 or doc['reserved'].get(label.casefold()) != sid:
            raise ValueError('Invalid reserved location label.')
    for label, sid in doc['reserved'].items():
        if not isinstance(label,str) or not label or len(label)>100 or not isinstance(sid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',sid):
            raise ValueError('Invalid retained location label.')
