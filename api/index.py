"""Vercel entrypoint: runs server.py's request handler as a WSGI app backed by Redis."""
import base64
from datetime import datetime, timezone
import gzip
from http.client import parse_headers
import io
import json
import os
from pathlib import Path
import secrets
import sys
import tarfile
import threading
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cloud_store import FileStore, Lock, MemoryRedis, StoreError, StorePath, VolatileState, connect  # noqa: E402
from server import Handler, LabState  # noqa: E402

PREFIX = os.environ.get('ITR_STORE_PREFIX', 'itr')
PASSWORD = os.environ.get('ITR_ADMIN_PASSWORD', '')
COMPRESSIBLE = ('application/json', 'text/', 'application/javascript')


class CloudLab(LabState):
    def __init__(self, redis):
        self.redis = redis
        self.store = FileStore(redis, PREFIX)
        self.volatile = VolatileState(redis, PREFIX)
        self.persistent = not isinstance(redis, MemoryRedis)
        with Lock(redis, PREFIX):
            if redis.call('SET', PREFIX + ':seeded', datetime.now(timezone.utc).isoformat(), 'NX') is not None:
                self.store.seed(ROOT / 'data')
            # An unset password must never fall back to a guessable default on the internet.
            self.init_state(StorePath(self.store), PASSWORD or secrets.token_urlsafe(32), ROOT / 'defaults')

    def backup(self, label):
        """Checkpoint current records (history files are append-only) inside Redis."""
        name = 'before-' + label + '-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + secrets.token_hex(4) + '.tar.gz'
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
            for path in self.data_dir.rglob('*.json'):
                if path.key.startswith('history/'):
                    continue
                raw = path.read_text().encode('utf-8')
                info = tarfile.TarInfo('data/' + path.key)
                info.size = len(raw)
                archive.addfile(info, io.BytesIO(raw))
            archive.add(self.defaults_dir, arcname='defaults')
        self.redis.call('HSET', PREFIX + ':backups', name, base64.b64encode(buffer.getvalue()).decode('ascii'))
        return name


class CloudHandler(Handler):
    """Drives the stdlib handler from an in-memory request instead of a socket."""

    def __init__(self, raw, client_ip, lab):
        self.rfile = io.BytesIO(raw)
        self.wfile = io.BytesIO()
        self.client_address = (client_ip, 0)
        self.server = lab
        self.handle_one_request()

    def consistent_request(self, callback, recover=False):
        if not self.path.startswith('/api/'):
            return callback()  # Static assets never touch stored data.
        if self.command != 'GET' and not self.server.persistent and self.path.split('?')[0] != '/api/session':
            return self.json_response(503, {'error': 'Saving is disabled: this deployment has no Redis storage connected. Add an Upstash Redis store in Vercel, then redeploy.'})
        if self.command == 'POST' and self.path.split('?')[0] == '/api/login' and not PASSWORD:
            return self.json_response(503, {'error': 'Admin login is disabled until ITR_ADMIN_PASSWORD is set in the Vercel project settings.'})
        return super().consistent_request(callback, recover)

    def same_origin(self):
        origin = self.headers.get('Origin')
        if origin and self.headers.get('X-Forwarded-Host') and origin == 'https://' + self.headers['X-Forwarded-Host']:
            return self.headers.get('Sec-Fetch-Site') != 'cross-site'
        return super().same_origin()

    def log_message(self, format, *args):
        pass  # Vercel records request logs itself.


LAB = None
INSTANCE_LOCK = threading.Lock()


def lab():
    global LAB
    if LAB is None:
        LAB = CloudLab(connect() or MemoryRedis())
    return LAB


def raw_request(environ):
    path = environ.get('RAW_URI') or (quote(environ.get('PATH_INFO', '/')) + ('?' + environ['QUERY_STRING'] if environ.get('QUERY_STRING') else ''))
    length = int(environ.get('CONTENT_LENGTH') or 0)
    body = environ['wsgi.input'].read(length) if length else b''
    lines = [f"{environ['REQUEST_METHOD']} {path} HTTP/1.1"]
    for key, value in environ.items():
        if key.startswith('HTTP_'):
            lines.append(key[5:].replace('_', '-').title() + ': ' + value)
    if environ.get('CONTENT_TYPE'):
        lines.append('Content-Type: ' + environ['CONTENT_TYPE'])
    lines.append('Content-Length: ' + str(len(body)))
    return ('\r\n'.join(lines) + '\r\n\r\n').encode('latin-1') + body


def handle(environ):
    forwarded = environ.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
    client = forwarded or environ.get('HTTP_X_REAL_IP') or environ.get('REMOTE_ADDR', '0.0.0.0')
    raw = raw_request(environ)
    if not environ.get('PATH_INFO', '/').startswith('/api/'):
        return CloudHandler(raw, client, None).wfile.getvalue()
    with INSTANCE_LOCK:
        state = lab()
        with Lock(state.redis, PREFIX):
            state.store.begin()
            state.volatile.load(state)
            output = CloudHandler(raw, client, state).wfile.getvalue()
            state.volatile.save(state)
            return output


def app(environ, start_response):
    try:
        output = handle(environ)
    except StoreError as error:
        body = json.dumps({'error': str(error)}).encode()
        start_response('503 Service Unavailable', [('Content-Type', 'application/json'), ('Content-Length', str(len(body)))])
        return [body]
    head, _, body = output.partition(b'\r\n\r\n')
    status_line, _, header_block = head.partition(b'\r\n')
    status = status_line.decode('latin-1').split(' ', 1)[1]
    headers = [(k, v) for k, v in parse_headers(io.BytesIO(header_block + b'\r\n\r\n')).items()
               if k.lower() not in ('server', 'date', 'content-length', 'connection')]
    secure = environ.get('HTTP_X_FORWARDED_PROTO', 'https') == 'https'
    headers = [(k, v + '; Secure' if secure and k.lower() == 'set-cookie' else v) for k, v in headers]
    content_type = next((v for k, v in headers if k.lower() == 'content-type'), '')
    # Vercel caps responses at 4.5 MB; the full JSON backup only fits compressed.
    if len(body) > 1024 and 'gzip' in environ.get('HTTP_ACCEPT_ENCODING', '') and content_type.startswith(COMPRESSIBLE):
        body = gzip.compress(body, 6)
        headers += [('Content-Encoding', 'gzip'), ('Vary', 'Accept-Encoding')]
    headers.append(('Content-Length', str(len(body))))
    start_response(status, headers)
    return [body]
