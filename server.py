#!/usr/bin/env python3
"""ITR lab editor: static UI, authenticated JSON persistence, no dependencies."""
import argparse
from datetime import datetime, timezone
import hashlib
import hmac
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
KINDS = {'section', 'shelf', 'table', 'cart', 'machine', 'wall', 'text'}
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
        if item['kind'] == 'section' and (type(item.get('showLabel')) is not bool or type(item.get('restricted')) is not bool):
            raise ValueError('Invalid section settings.')
    def points(values, minimum):
        if not isinstance(values, list) or not minimum <= len(values) <= 500:
            return False
        return all(isinstance(p, list) and len(p) == 2 and all(type(v) in (int, float) for v in p)
                   and 0 <= p[0] <= doc['cols'] and 0 <= p[1] <= doc['rows'] for p in values)
    if not points(doc.get('outline'), 3):
        raise ValueError('Outline needs at least three valid grid points.')
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
    occupied = set()
    for r, row in enumerate(matrix):
        if not isinstance(row, list) or len(row) != cols:
            raise ValueError('Every matrix row must match cols.')
        for c, cell in enumerate(row):
            if cell is None:
                continue
            if (not isinstance(cell, dict) or not style(cell) or not text(cell.get('name')) or
                    not text(cell.get('contents'), 10000) or not text(cell.get('keywords'), 2000)):
                raise ValueError('Invalid bin text or style.')
            w, h = cell.get('w'), cell.get('h')
            if not integer(w, 1, cols-c) or not integer(h, 1, rows-r):
                raise ValueError('Bin extends outside the shelf.')
            for rr in range(r, r+h):
                for cc in range(c, c+w):
                    if (rr, cc) in occupied:
                        raise ValueError('Shelf bins overlap.')
                    occupied.add((rr, cc))


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


class LabServer(ThreadingHTTPServer):
    def __init__(self, address, data_dir, password):
        super().__init__(address, Handler)
        self.data_dir = Path(data_dir)
        self.password_hash = hashlib.sha256(password.encode()).digest()
        self.sessions = {}
        self.attempts = {}
        self.lock = threading.RLock()
        self.drafts = {}

    def prune_drafts(self):
        now = time.time()
        self.drafts = {k:v for k,v in self.drafts.items()
                       if v['expires'] > now and self.sessions.get(k[0], 0) > now}

    def archive_lab(self, doc, reason='Saved layout', replace=False):
        path = self.data_dir / 'history' / 'lab' / f"{doc['revision']}.json"
        if replace or not path.exists():
            write_json(path, {'savedAt': datetime.now(timezone.utc).isoformat(),
                              'reason': reason, 'layout': doc})

    def persist_lab(self, doc, reason):
        current = json.loads((self.data_dir / 'lab.json').read_text())
        self.archive_lab(current)
        for item in doc['items']:
            if item['kind'] == 'shelf':
                target = self.data_dir / 'shelves' / (item['id'] + '.json')
                if not target.exists():
                    write_json(target, blank_shelf(item['id'], item['name']))
        # An uncommitted snapshot is excluded from history by the live revision.
        self.archive_lab(doc, reason, replace=True)
        write_json(self.data_dir / 'lab.json', doc)


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
                        else:
                            validate_shelf(doc, key[2].split('/')[1])
                    if key not in self.server.drafts and len(self.server.drafts) >= 100:
                        raise ValueError('Draft cache is full. Close unused sessions and try again.')
                    self.server.drafts[key] = {'expires': time.time()+8*3600, 'state': body}
                    return self.json_response(200, {'cached': True})
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
        public = {'lab_overview.html', 'shelf_editor.html', 'shelf_inventory_editor.html', 'editor.css', 'editor_groups.js', 'common.js', 'lab.js', 'lab_tools.js', 'map_editor.js', 'shelf.js', 'shelf_model.js', 'explorer.js'}
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
                    if version == 'original':
                        doc = json.loads((ROOT / 'defaults' / 'lab.json').read_text())
                    elif re.fullmatch(r'\d{1,12}', version) and int(version) <= current['revision']:
                        file = self.server.data_dir / 'history' / 'lab' / f'{int(version)}.json'
                        if int(version) == current['revision']:
                            doc = current.copy()
                        elif not file.exists():
                            return self.json_response(404, {'error': 'Saved version not found.'})
                        else:
                            doc = json.loads(file.read_text())['layout']
                    else:
                        raise ValueError('Invalid saved version.')
                    validate_lab(doc)
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
                if not shelf_id:
                    self.server.persist_lab(doc, doc['versionName'])
                else:
                    write_json(file, doc)
                return self.json_response(200, {'revision': doc['revision']})
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
