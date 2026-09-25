#!/usr/bin/env python3
"""ITR lab editor: static UI, authenticated JSON persistence, no dependencies."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import hmac
import math
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import threading
import time
from urllib.parse import urlsplit, unquote

ROOT = Path(__file__).resolve().parent
ID = re.compile(r'^[A-Za-z0-9_-]{1,64}$')
HEX = re.compile(r'^#[0-9a-fA-F]{6}$')
KINDS = {'section', 'shelf', 'table', 'cart', 'machine', 'wall', 'text', 'misc'}
FONTS = {'system-ui', 'Arial', 'Georgia', 'monospace'}
MAX_BODY = 4_000_000


def integer(value, low, high):
    return type(value) is int and low <= value <= high


def style(obj):
    return (HEX.fullmatch(str(obj.get('background', ''))) and
            HEX.fullmatch(str(obj.get('color', ''))) and
            integer(obj.get('fontSize'), 6, 96) and obj.get('fontFamily') in FONTS and
            type(obj.get('bold')) is bool)


def text(value, limit=500):
    return isinstance(value, str) and len(value) <= limit


def validate_lab(doc):
    if not isinstance(doc, dict) or not integer(doc.get('cols'), 10, 200) or not integer(doc.get('rows'), 10, 200):
        raise ValueError('Lab grid dimensions must be integers from 10 to 200.')
    items = doc.get('items')
    if not isinstance(items, list) or len(items) > 1000:
        raise ValueError('Invalid item list (maximum 1,000).')
    ids = set()
    for item in items:
        if not isinstance(item, dict) or not ID.fullmatch(str(item.get('id', ''))) or item['id'] in ids:
            raise ValueError('Every item needs a unique safe ID.')
        ids.add(item['id'])
        if (item.get('kind') not in KINDS or not text(item.get('name')) or not text(item.get('area', '')) or
                not style(item) or type(item.get('locked')) is not bool):
            raise ValueError('Invalid item type, label, or style.')
        for key, maximum in [('x', doc['cols']), ('w', doc['cols']), ('y', doc['rows']), ('h', doc['rows'])]:
            if not integer(item.get(key), 1, maximum):
                raise ValueError('Invalid grid coordinates.')
        if item['x'] + item['w'] - 1 > doc['cols'] or item['y'] + item['h'] - 1 > doc['rows']:
            raise ValueError('An item extends outside the grid.')
        if item['kind'] == 'misc':
            if item.get('shape', 'square') not in ('square','line','triangle','circle') or type(item.get('showLabel', True)) is not bool:
                raise ValueError('Invalid Misc shape or label visibility.')
            if item.get('lineDirection','horizontal') not in ('horizontal','vertical','diagonal-down','diagonal-up') or not integer(item.get('lineWidth',4),1,20):
                raise ValueError('Invalid Misc line direction or thickness.')
        if item['kind'] == 'section' and (type(item.get('showLabel')) is not bool or type(item.get('restricted')) is not bool):
            raise ValueError('Invalid section settings.')
    def points(values, minimum):
        if not isinstance(values, list) or not minimum <= len(values) <= 500:
            return False
        return all(isinstance(p, list) and len(p) == 2 and all(type(v) in (int, float) for v in p)
                   and 0 <= p[0] <= doc['cols'] and 0 <= p[1] <= doc['rows'] for p in values)
    if not points(doc.get('outline'), 3):
        raise ValueError('Outline needs at least three valid grid points.')
    walls = doc.get('walls', [])
    if not isinstance(walls, list) or len(walls) > 500:
        raise ValueError('Invalid walls (maximum 500).')
    wall_ids = set()
    for wall in walls:
        if not isinstance(wall, dict) or not ID.fullmatch(str(wall.get('id',''))) or wall['id'] in wall_ids:
            raise ValueError('Walls require unique IDs.')
        wall_ids.add(wall['id'])
        ends = [wall.get('a'), wall.get('b')]
        if not points(ends, 2) or ends[0] == ends[1] or any(not all(type(n) is int for n in p) for p in ends):
            raise ValueError('Wall endpoints must be distinct integer grid points.')
        thickness = wall.get('thickness')
        if type(thickness) not in (int,float) or not .1 <= thickness <= 2:
            raise ValueError('Wall thickness must be between 0.1 and 2.')
    doors = doc.get('doors', [])
    if not isinstance(doors, list) or len(doors) > 500:
        raise ValueError('Invalid doors (maximum 500).')
    door_ids = set()
    for door in doors:
        if not isinstance(door, dict) or not ID.fullmatch(str(door.get('id',''))) or door['id'] in door_ids:
            raise ValueError('Doors require unique IDs.')
        door_ids.add(door['id'])
        orientation = door.get('orientation')
        if orientation not in ('NW','NE','SW','SE') or not integer(door.get('radius'),1,20):
            raise ValueError('Invalid door orientation or radius.')
        x,y,r = door.get('x'),door.get('y'),door['radius']
        if not integer(x,0,doc['cols']) or not integer(y,0,doc['rows']):
            raise ValueError('Door hinge must be on the grid.')
        if not 0 <= x+(r if 'E' in orientation else -r) <= doc['cols'] or not 0 <= y+(r if 'S' in orientation else -r) <= doc['rows']:
            raise ValueError('Door extends outside the grid.')
    routes = doc.get('routes')
    if not isinstance(routes, list) or len(routes) > 100 or not all(points(p, 2) for p in routes):
        raise ValueError('Invalid traffic paths.')


def validate_shelf(doc, shelf_id):
    if not isinstance(doc, dict) or doc.get('id') != shelf_id:
        raise ValueError('Shelf ID does not match the file.')
    if doc.get('mode', 'simple') not in ('simple', 'complex'):
        raise ValueError('Shelf mode must be simple or complex.')
    for field, limit in [('name', 500), ('contents', 10000), ('keywords', 2000)]:
        if not text(doc.get(field, ''), limit):
            raise ValueError('Invalid shelf metadata.')
    rows, cols = doc.get('rows'), doc.get('cols')
    if not integer(rows, 1, 60) or not integer(cols, 1, 60):
        raise ValueError('Shelf dimensions must be integers from 1 to 60.')
    matrix = doc.get('matrix')
    if not isinstance(matrix, list) or len(matrix) != rows:
        raise ValueError('Matrix row count does not match rows.')
    occupied = []
    bin_ids = set()
    for r, row in enumerate(matrix):
        if not isinstance(row, list) or len(row) != cols:
            raise ValueError('Every matrix row must match cols.')
        for c, cell in enumerate(row):
            if cell is None:
                continue
            if (not isinstance(cell, dict) or not style(cell) or not text(cell.get('name')) or
                    not text(cell.get('contents'), 10000) or not text(cell.get('keywords'), 2000)):
                raise ValueError('Invalid bin text or style.')
            if 'id' in cell:
                if not isinstance(cell['id'],str) or not ID.fullmatch(cell['id']) or cell['id'] in bin_ids:
                    raise ValueError('Bin IDs must be unique.')
                bin_ids.add(cell['id'])
            w, h = cell.get('w'), cell.get('h')
            ox, oy = cell.get('offsetX', 0), cell.get('offsetY', 0)
            if any(type(v) not in (int, float) or not math.isfinite(v) or v*2 != int(v*2) for v in (w,h,ox,oy)) or ox not in (0,.5) or oy not in (0,.5):
                raise ValueError('Bin geometry must use half-grid increments; offsets are 0 or 0.5.')
            x, y = c+ox, r+oy
            if w < 1 or h < 1 or x+w > cols or y+h > rows:
                raise ValueError('Bin extends outside the shelf or is smaller than one cell.')
            if any(x < xx+ww and x+w > xx and y < yy+hh and y+h > yy for xx,yy,ww,hh in occupied):
                raise ValueError('Shelf bins overlap.')
            occupied.append((x,y,w,h))


def normalize_shelf(doc, name=''):
    """Read legacy matrices without rewriting files or dropping dormant bins."""
    result = dict(doc)
    result.setdefault('schemaVersion', 2)
    result.setdefault('mode', 'complex' if any(cell is not None for row in doc.get('matrix', []) for cell in row) else 'simple')
    result.setdefault('name', name)
    result.setdefault('contents', '')
    result.setdefault('keywords', '')
    return result


def blank_shelf(shelf_id, name=''):
    return normalize_shelf(dict(id=shelf_id, revision=0, rows=34, cols=30, matrix=[[None]*30 for _ in range(34)]), name)


def write_json(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    # One matrix row per line keeps shelf files easy to hand-edit.
    if 'matrix' in doc:
        header = {k: v for k, v in doc.items() if k != 'matrix'}
        payload = json.dumps(header, indent=2)[:-2] + ',\n  "matrix": [\n' + ',\n'.join(
            '    ' + json.dumps(row, ensure_ascii=False) for row in doc['matrix']) + '\n  ]\n}\n'
    else:
        payload = json.dumps(doc, indent=2, ensure_ascii=False) + '\n'
    temporary = path.with_suffix('.tmp')
    with temporary.open('w') as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporary, path)


class RevisionConflict(ValueError):
    pass


class LabServer(ThreadingHTTPServer):
    def __init__(self, address, data_dir, password):
        super().__init__(address, Handler)
        self.data_dir = Path(data_dir)
        self.password_hash = hashlib.sha256(password.encode()).digest()
        self.sessions = {}
        self.attempts = {}
        self.lock = threading.RLock()
        self.drafts = {}
        self.inventory_states = {}
        # Roll forward a fully validated, explicitly saved transaction after interruption.
        self.finish_transaction()

    def finish_transaction(self):
        journal = self.data_dir / 'pending-save.json'
        if journal.exists():
            for name, doc in json.loads(journal.read_text()).items():
                write_json(self.data_dir / name, doc)
            journal.unlink()

    def shelf_snapshot(self, lab):
        result = {}
        for item in lab['items']:
            if item['kind'] == 'shelf':
                path = self.data_dir / 'shelves' / (item['id'] + '.json')
                result[item['id']] = normalize_shelf(json.loads(path.read_text()), item['name']) if path.exists() else blank_shelf(item['id'], item['name'])
        return result

    def prune_drafts(self):
        now = time.time()
        self.inventory_states = {k:v for k,v in self.inventory_states.items() if self.sessions.get(k[0], 0) > now}
        self.drafts = {k:v for k,v in self.drafts.items()
                       if v['expires'] > now and self.sessions.get(k[0], 0) > now}

    def remember_inventory(self, prefix, shelves):
        reference = secrets.token_hex(16)
        self.inventory_states[(*prefix, reference)] = copy.deepcopy(shelves)
        return reference

    def apply_inventory(self, prefix, shelves):
        for sid, shelf in shelves.items():
            validate_shelf(shelf, sid)
        for sid, shelf in shelves.items():
            target = self.data_dir / 'shelves' / (sid+'.json')
            restored = copy.deepcopy(shelf)
            restored['revision'] = json.loads(target.read_text())['revision'] if target.exists() else 0
            key = (*prefix, 'shelves/'+sid)
            previous = self.drafts.get(key)
            history = [previous['state']['data']] if previous else []
            self.drafts[key] = {'expires': time.time()+8*3600, 'state': dict(data=restored, history=history, future=[], dirty=True)}

    def archive_lab(self, doc, reason='Saved layout', replace=False, shelves=None):
        path = self.data_dir / 'history' / 'lab' / f"{doc['revision']}.json"
        if replace or not path.exists():
            write_json(path, {'savedAt': datetime.now(timezone.utc).isoformat(),
                              'reason': reason, 'layout': doc, 'shelves': shelves if shelves is not None else self.shelf_snapshot(doc)})

    def persist_lab(self, doc, reason, shelves):
        doc = {key:value for key,value in doc.items() if key not in ('_inventoryState','_previousInventoryState')}
        current = json.loads((self.data_dir / 'lab.json').read_text())
        self.archive_lab(current)
        writes = {f'shelves/{sid}.json': shelf for sid, shelf in shelves.items()}
        writes[f"history/lab/{doc['revision']}.json"] = {
            'savedAt': datetime.now(timezone.utc).isoformat(), 'reason': reason,
            'layout': doc, 'shelves': shelves}
        writes['lab.json'] = doc
        write_json(self.data_dir / 'pending-save.json', writes)
        self.finish_transaction()

    def commit_version(self, doc, prefix, overrides=None):
        self.prune_drafts()
        shelves = self.shelf_snapshot(doc)
        overrides = overrides or {}
        updated = []
        for sid, persisted in shelves.items():
            cached = self.drafts.get((*prefix, 'shelves/'+sid))
            if sid in overrides:
                shelves[sid] = overrides[sid]
                if cached:
                    updated.append((cached, overrides[sid]))
            elif cached and cached['state']['dirty']:
                draft = copy.deepcopy(cached['state']['data'])
                validate_shelf(draft, sid)
                if draft.get('revision') != persisted['revision']:
                    raise RevisionConflict(f'Shelf {sid} changed on the server. Reload that shelf before saving the lab.')
                draft['revision'] += 1
                draft['versionName'] = doc['versionName']
                shelves[sid] = draft
                updated.append((cached, draft))
        shelves.update(overrides)
        self.persist_lab(doc, doc['versionName'], shelves)
        for cached, draft in updated:
            cached['state']['data'] = draft
            cached['state']['dirty'] = False


class Handler(BaseHTTPRequestHandler):
    def json_response(self, code, data, cookie=None):
        raw = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(raw)))
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(raw)

    def token(self):
        jar = cookies.SimpleCookie()
        try:
            jar.load(self.headers.get('Cookie', ''))
            return jar['itr_session'].value if 'itr_session' in jar else ''
        except cookies.CookieError:
            return ''

    def admin(self):
        return self.server.sessions.get(self.token(), 0) > time.time()

    def read_body(self):
        length = int(self.headers.get('Content-Length', '0'))
        if not 0 < length <= MAX_BODY:
            raise ValueError('Missing or oversized request body.')
        return json.loads(self.rfile.read(length))

    def same_origin(self):
        # Cookies alone are insufficient: reject cross-origin mutations.
        origin = self.headers.get('Origin')
        if self.headers.get('Sec-Fetch-Site') == 'cross-site':
            return False
        return not origin or origin == 'http://' + self.headers.get('Host', '')

    def resource(self):
        path = urlsplit(self.path).path
        if path == '/api/lab':
            return self.server.data_dir / 'lab.json', None
        match = re.fullmatch(r'/api/shelves/([A-Za-z0-9_-]{1,64})', path)
        if match:
            return self.server.data_dir / 'shelves' / (match[1] + '.json'), match[1]
        return None, None

    def draft_key(self):
        path = urlsplit(self.path).path
        match = re.fullmatch(r'/api/drafts/(lab|shelves/[A-Za-z0-9_-]{1,64})', path)
        instance = self.headers.get('X-Editor-Instance', '')
        if not match or not ID.fullmatch(instance):
            raise ValueError('A valid editor instance is required.')
        return self.token(), instance, match[1]

    def draft_has_shelf(self, shelf_id):
        key = (self.token(), self.headers.get('X-Editor-Instance', ''), 'lab')
        cached = self.server.drafts.get(key)
        return self.admin() and cached and cached['expires'] > time.time() and any(
            item['id'] == shelf_id and item['kind'] == 'shelf'
            for item in cached['state']['data']['items'])

    def shelf_name(self, shelf_id):
        cached = self.server.drafts.get((self.token(), self.headers.get('X-Editor-Instance', ''), 'lab')) if self.admin() else None
        lab = cached['state']['data'] if cached else json.loads((self.server.data_dir / 'lab.json').read_text())
        return next((i['name'] for i in lab['items'] if i['id'] == shelf_id), shelf_id)

    def draft_request(self, write=False):
        if not self.admin() or (write and not self.same_origin()):
            return self.json_response(403, {'error': 'Admin login required for draft memory.'})
        with self.server.lock:
            try:
                key = self.draft_key()
                self.server.prune_drafts()
                if write:
                    body = self.read_body()
                    if not isinstance(body, dict) or type(body.get('dirty')) is not bool:
                        raise ValueError('Invalid draft.')
                    for stack in ('history', 'future'):
                        if not isinstance(body.get(stack), list) or len(body[stack]) > 40:
                            raise ValueError('Draft history is limited to 40 steps.')
                    for doc in [body.get('data')] + body['history'] + body['future']:
                        if key[2] == 'lab':
                            validate_lab(doc)
                            if doc.get('_inventoryState') is not None and (not isinstance(doc['_inventoryState'],str) or (*key[:2], doc['_inventoryState']) not in self.server.inventory_states):
                                raise ValueError('Inventory undo memory has expired. Reload the saved version.')
                        else:
                            validate_shelf(doc, key[2].split('/')[1])
                    if key not in self.server.drafts and len(self.server.drafts) >= 100:
                        raise ValueError('Draft cache is full. Close unused sessions and try again.')
                    inventory_changed = False
                    if key[2] == 'lab':
                        reference = body['data'].get('_inventoryState')
                        previous = self.server.drafts.get(key)
                        if reference and (not previous or reference != previous['state']['data'].get('_inventoryState')):
                            self.server.apply_inventory(key[:2], self.server.inventory_states[(*key[:2], reference)])
                            inventory_changed = True
                    self.server.drafts[key] = {'expires': time.time()+8*3600, 'state': body}
                    return self.json_response(200, {'cached': True, 'inventoryChanged': inventory_changed})
                cached = self.server.drafts.get(key)
                return self.json_response(200, cached['state'] if cached else None)
            except (ValueError, UnicodeDecodeError) as error:
                return self.json_response(400, {'error': str(error)})

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/api/session':
            return self.json_response(200, {'admin': self.admin()})
        if path.startswith('/api/drafts/'):
            return self.draft_request()
        if path == '/api/shelf-index':
            with self.server.lock:
                try:
                    self.server.prune_drafts()
                    prefix = (self.token(), self.headers.get('X-Editor-Instance', ''))
                    cached_lab = self.server.drafts.get((*prefix, 'lab')) if self.admin() else None
                    lab = cached_lab['state']['data'] if cached_lab else json.loads((self.server.data_dir/'lab.json').read_text())
                    index = {}
                    for item in lab['items']:
                        if item['kind'] != 'shelf':
                            continue
                        cached = self.server.drafts.get((*prefix, 'shelves/'+item['id'])) if self.admin() else None
                        file = self.server.data_dir/'shelves'/f"{item['id']}.json"
                        doc = cached['state']['data'] if cached else json.loads(file.read_text()) if file.exists() else blank_shelf(item['id'], item['name'])
                        doc = normalize_shelf(doc, item['name'])
                        terms = [doc['name'], doc['contents'], doc['keywords']]
                        if doc['mode'] == 'complex':
                            for row in doc['matrix']:
                                for bin in row:
                                    if bin:
                                        terms.extend([bin['name'], bin['contents'], bin['keywords']])
                        index[item['id']] = {key: doc[key] for key in ('name', 'mode', 'contents', 'keywords')}
                        index[item['id']]['searchText'] = ' '.join(terms).lower()
                        index[item['id']]['draftDirty'] = bool(cached and cached['state']['dirty'])
                    return self.json_response(200, index)
                except (OSError, ValueError, KeyError, TypeError):
                    return self.json_response(500, {'error': 'Could not index shelf files. Check their JSON.'})
        if path == '/api/lab/history':
            with self.server.lock:
                try:
                    current = json.loads((self.server.data_dir / 'lab.json').read_text())
                    versions = []
                    for file in (self.server.data_dir / 'history' / 'lab').glob('*.json'):
                        record = json.loads(file.read_text())
                        revision = record['layout']['revision']
                        if revision <= current['revision']:
                            versions.append({'version': str(revision), 'revision': revision,
                                             'savedAt': record['savedAt'], 'reason': record['reason'],
                                             'name': record['layout'].get('versionName', record['reason'])})
                    if not any(v['revision'] == current['revision'] for v in versions):
                        versions.append({'version': str(current['revision']), 'revision': current['revision'],
                                         'savedAt': None, 'reason': 'Current saved layout',
                                         'name': current.get('versionName', 'Current saved layout')})
                    versions.sort(key=lambda v: v['revision'], reverse=True)
                    return self.json_response(200, {'currentRevision': current['revision'], 'versions': versions})
                except (OSError, ValueError, KeyError):
                    return self.json_response(500, {'error': 'Could not read layout history.'})
        file, shelf_id = self.resource()
        if file:
            with self.server.lock:
                if not file.exists():
                    if shelf_id and self.draft_has_shelf(shelf_id):
                        return self.json_response(200, blank_shelf(shelf_id, self.shelf_name(shelf_id)))
                    return self.json_response(404, {'error': 'Shelf not found.'})
                try:
                    doc = json.loads(file.read_text())
                    return self.json_response(200, normalize_shelf(doc, self.shelf_name(shelf_id)) if shelf_id else doc)
                except (OSError, ValueError):
                    return self.json_response(500, {'error': 'Cannot read data file. Check its JSON.'})
        public = {'lab_overview.html', 'shelf_editor.html', 'shelf_inventory_editor.html', 'editor.css', 'editor_groups.js', 'common.js', 'lab.js', 'lab_tools.js', 'map_editor.js', 'map_geometry.js', 'map_elements.js', 'shelf.js', 'shelf_model.js', 'explorer.js'}
        name = unquote(path).lstrip('/') or 'lab_overview.html'
        if name not in public:
            return self.json_response(404, {'error': 'Not found.'})
        try:
            raw = (ROOT / name).read_bytes()
        except OSError:
            return self.json_response(404, {'error': 'Not found.'})
        self.send_response(200)
        self.send_header('Content-Type', mimetypes.guess_type(name)[0] or 'application/octet-stream')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        if not self.same_origin():
            return self.json_response(403, {'error': 'Cross-origin requests are not allowed.'})
        path = urlsplit(self.path).path
        with self.server.lock:
            if path == '/api/lab/restore':
                if not self.admin():
                    return self.json_response(403, {'error': 'Admin login required to restore a layout.'})
                try:
                    body = self.read_body()
                    if not isinstance(body, dict):
                        raise ValueError('Invalid restore request.')
                    current = json.loads((self.server.data_dir / 'lab.json').read_text())
                    if type(body.get('revision')) is not int or body['revision'] != current['revision']:
                        return self.json_response(409, {'error': 'The lab changed. Reload saved before restoring a version.'})
                    version = str(body.get('version', ''))
                    restored_shelves = None
                    if version == 'original':
                        doc = json.loads((ROOT / 'defaults' / 'lab.json').read_text())
                    elif re.fullmatch(r'\d{1,12}', version) and int(version) <= current['revision']:
                        file = self.server.data_dir / 'history' / 'lab' / f'{int(version)}.json'
                        if file.exists():
                            record = json.loads(file.read_text())
                            doc = record['layout']
                            restored_shelves = record.get('shelves')
                        elif int(version) == current['revision']:
                            doc = current.copy()
                        elif not file.exists():
                            return self.json_response(404, {'error': 'Saved version not found.'})
                        else:
                            doc = json.loads(file.read_text())['layout']
                    else:
                        raise ValueError('Invalid saved version.')
                    validate_lab(doc)
                    instance = self.headers.get('X-Editor-Instance', '')
                    if restored_shelves is not None and ID.fullmatch(instance):
                        prefix = (self.token(), instance)
                        cached_lab = self.server.drafts.get((*prefix, 'lab'))
                        before = self.server.shelf_snapshot(cached_lab['state']['data'] if cached_lab else current)
                        for key, cached in self.server.drafts.items():
                            if key[:2] == prefix and key[2].startswith('shelves/'):
                                before[key[2].split('/')[1]] = cached['state']['data']
                        doc['_previousInventoryState'] = self.server.remember_inventory(prefix, before)
                        doc['_inventoryState'] = self.server.remember_inventory(prefix, restored_shelves)
                        self.server.apply_inventory(prefix, restored_shelves)
                    # Restoring loads a draft. Only an explicit named PUT commits it.
                    doc['revision'] = current['revision']
                    return self.json_response(200, doc)
                except (ValueError, KeyError, UnicodeDecodeError) as error:
                    return self.json_response(400, {'error': str(error)})
                except OSError:
                    return self.json_response(500, {'error': 'Could not load the saved layout.'})
            if path == '/api/logout':
                self.server.sessions.pop(self.token(), None)
                self.server.prune_drafts()
                return self.json_response(200, {'admin': False}, 'itr_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0')
            if path != '/api/login':
                return self.json_response(404, {'error': 'Not found.'})
            now = time.time()
            ip = self.client_address[0]
            attempts = [t for t in self.server.attempts.get(ip, []) if t > now-60]
            if len(attempts) >= 10:
                return self.json_response(429, {'error': 'Too many attempts. Try again in a minute.'})
            try:
                data = self.read_body()
                password = data.get('password', '') if isinstance(data, dict) else ''
                if not isinstance(password, str):
                    raise ValueError('Invalid password.')
            except (ValueError, UnicodeDecodeError):
                return self.json_response(400, {'error': 'Invalid login request.'})
            if not hmac.compare_digest(hashlib.sha256(password.encode()).digest(), self.server.password_hash):
                self.server.attempts[ip] = attempts + [now]
                return self.json_response(401, {'error': 'Incorrect password.'})
            self.server.attempts.pop(ip, None)
            self.server.sessions = {k:v for k,v in self.server.sessions.items() if v > now}
            token = secrets.token_urlsafe(32)
            self.server.sessions[token] = now + 8*3600
            return self.json_response(200, {'admin': True}, f'itr_session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=28800')

    def do_PUT(self):
        if urlsplit(self.path).path.startswith('/api/drafts/'):
            return self.draft_request(write=True)
        if not self.same_origin() or not self.admin():
            return self.json_response(403, {'error': 'Admin login required to save changes.'})
        file, shelf_id = self.resource()
        if not file:
            return self.json_response(404, {'error': 'Not found.'})
        with self.server.lock:
            try:
                if not file.exists() and not (shelf_id and self.draft_has_shelf(shelf_id)):
                    return self.json_response(404, {'error': 'Shelf not found.'})
                doc = self.read_body()
                if not isinstance(doc, dict) or not text(doc.get('versionName'), 120) or not doc['versionName'].strip():
                    raise ValueError('Enter a version name (1–120 characters) before saving.')
                doc['versionName'] = doc['versionName'].strip()
                if shelf_id:
                    doc = normalize_shelf(doc, self.shelf_name(shelf_id))
                    validate_shelf(doc, shelf_id)
                else:
                    validate_lab(doc)
                current = json.loads(file.read_text()) if file.exists() else blank_shelf(shelf_id)
                if type(doc.get('revision')) is not int or doc['revision'] != current['revision']:
                    return self.json_response(409, {'error': 'Another admin saved changes. Export your draft, then reload before editing again.'})
                doc['revision'] += 1
                prefix = (self.token(), self.headers.get('X-Editor-Instance', ''))
                if not shelf_id:
                    self.server.commit_version(doc, prefix)
                else:
                    # Save from either editor commits one coherent named lab version.
                    current_lab = json.loads((self.server.data_dir/'lab.json').read_text())
                    cached_lab = self.server.drafts.get((*prefix, 'lab'))
                    lab_doc = copy.deepcopy(cached_lab['state']['data'] if cached_lab else current_lab)
                    if lab_doc['revision'] != current_lab['revision']:
                        raise RevisionConflict('The lab changed on the server. Reload the lab before saving this instance.')
                    lab_doc.update(revision=current_lab['revision']+1, versionName=doc['versionName'])
                    validate_lab(lab_doc)
                    self.server.commit_version(lab_doc, prefix, {shelf_id: doc})
                    if cached_lab:
                        cached_lab['state']['data'] = lab_doc
                        cached_lab['state']['dirty'] = False
                return self.json_response(200, {'revision': doc['revision']})
            except RevisionConflict as error:
                return self.json_response(409, {'error': str(error)})
            except (ValueError, UnicodeDecodeError) as error:
                return self.json_response(400, {'error': str(error)})
            except OSError:
                return self.json_response(500, {'error': 'Could not save to disk. Your local draft is still open.'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--data-dir', default=str(ROOT / 'data'))
    args = parser.parse_args()
    try:
        server = LabServer((args.host, args.port), args.data_dir, os.environ.get('ITR_ADMIN_PASSWORD', 'itr'))
    except OSError as error:
        parser.exit(1, f'Could not start server: {error}\nStop the old server with Ctrl+C, or choose --port 8001.\n')
    host = 'localhost' if args.host in ('127.0.0.1', '0.0.0.0') else args.host
    print(f'Lab editor: http://{host}:{args.port}/\nPress Ctrl+C to stop.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
