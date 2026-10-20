"""Key-value storage for serverless hosting: data files and editor memory live in Redis.

Files are stored compressed in one Redis hash keyed by their path relative to the
data directory. StorePath mimics the small part of pathlib that server.py uses, so
the validation and transaction logic is shared with the local server unchanged.
"""
import base64
from fnmatch import fnmatch
import json
import os
import secrets
import time
import urllib.error
import urllib.request
import zlib


def pack(text):
    return base64.b64encode(zlib.compress(text.encode('utf-8'), 6)).decode('ascii')


def unpack(value):
    return zlib.decompress(base64.b64decode(value)).decode('utf-8')


class StoreError(OSError):
    pass


class Redis:
    """Minimal Upstash-compatible Redis REST client (no dependencies)."""

    def __init__(self, url, token):
        self.url = url.rstrip('/')
        self.token = token

    def _post(self, path, body):
        request = urllib.request.Request(self.url + path, data=json.dumps(body).encode(), method='POST', headers={
            'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.loads(response.read())
        except (urllib.error.URLError, OSError, ValueError) as error:
            raise StoreError('Storage request failed: ' + str(error)) from error

    def call(self, *command):
        reply = self._post('', [str(part) for part in command])
        if 'error' in reply:
            raise StoreError('Storage error: ' + str(reply['error']))
        return reply['result']

    def pipeline(self, commands):
        if not commands:
            return []
        replies = self._post('/pipeline', [[str(part) for part in c] for c in commands])
        for reply in replies:
            if 'error' in reply:
                raise StoreError('Storage error: ' + str(reply['error']))
        return [reply['result'] for reply in replies]


class MemoryRedis:
    """In-process stand-in used when no Redis is configured (nothing persists)."""

    def __init__(self):
        self.data = {}

    def call(self, op, key, *args):
        op = op.upper()
        if op == 'HGETALL':
            return [x for pair in self.data.get(key, {}).items() for x in pair]
        if op == 'HKEYS':
            return list(self.data.get(key, {}))
        if op == 'HMGET':
            return [self.data.get(key, {}).get(field) for field in args]
        if op == 'HSET':
            self.data.setdefault(key, {}).update(zip(args[::2], args[1::2]))
            return len(args) // 2
        if op == 'HDEL':
            return sum(self.data.get(key, {}).pop(field, None) is not None for field in args)
        if op == 'SET':
            if 'NX' in args and key in self.data:
                return None
            self.data[key] = args[0]
            return 'OK'
        if op == 'GET':
            return self.data.get(key)
        if op == 'EVAL':  # Only used for lock release: EVAL script 1 lock-key token.
            return int(self.data.pop(args[1], None) is not None)
        raise StoreError('Unsupported in-memory command ' + op)

    def pipeline(self, commands):
        return [self.call(*c) for c in commands]


class FileStore:
    """All data files in one hash, cached for the duration of a locked request."""

    def __init__(self, redis, prefix):
        self.redis = redis
        self.key = prefix + ':files'
        self.begin()

    def begin(self):
        self.names = None
        self.values = {}

    def keys(self):
        if self.names is None:
            self.names = set(self.redis.call('HKEYS', self.key))
        return self.names

    def exists(self, name):
        return name in self.keys()

    def prefetch(self, names):
        missing = [n for n in names if n not in self.values]
        for start in range(0, len(missing), 200):
            batch = missing[start:start+200]
            for name, value in zip(batch, self.redis.call('HMGET', self.key, *batch)):
                if value is not None:
                    self.values[name] = unpack(value)

    def read(self, name):
        if name not in self.values:
            self.prefetch([name])
        if name not in self.values:
            raise FileNotFoundError(name)
        return self.values[name]

    def write(self, name, text):
        self.redis.call('HSET', self.key, name, pack(text))
        self.values[name] = text
        self.keys().add(name)

    def delete(self, name):
        self.redis.call('HDEL', self.key, name)
        self.values.pop(name, None)
        self.keys().discard(name)

    def seed(self, directory):
        """Copy bundled JSON files into an empty store, in request-sized batches."""
        batch, size = [], 0
        for path in sorted(directory.rglob('*.json')):
            if path.name == 'pending-save.json':
                continue
            packed = pack(path.read_text(encoding='utf-8'))
            batch += [path.relative_to(directory).as_posix(), packed]
            size += len(packed)
            if size > 2_000_000:
                self.redis.call('HSET', self.key, *batch)
                batch, size = [], 0
        if batch:
            self.redis.call('HSET', self.key, *batch)
        self.begin()


class StorePath:
    """The subset of pathlib.Path that server.py uses for its data directory."""

    def __init__(self, store, name=''):
        self.store = store
        self.key = name.strip('/')

    def __truediv__(self, other):
        return StorePath(self.store, (self.key + '/' + str(other)).strip('/'))

    def __str__(self):
        return 'store:/' + self.key

    def __eq__(self, other):
        return isinstance(other, StorePath) and other.key == self.key

    def __lt__(self, other):
        return self.key < other.key

    def __hash__(self):
        return hash(self.key)

    @property
    def name(self):
        return self.key.rsplit('/', 1)[-1]

    @property
    def stem(self):
        return self.name.rsplit('.', 1)[0] if '.' in self.name else self.name

    @property
    def parent(self):
        return StorePath(self.store, self.key.rsplit('/', 1)[0] if '/' in self.key else '')

    def resolve(self):
        return self

    def as_posix(self):
        return self.key

    def relative_to(self, other):
        if other.key and not self.key.startswith(other.key + '/'):
            raise ValueError(self.key + ' is not inside ' + other.key)
        return StorePath(self.store, self.key[len(other.key):])

    def exists(self):
        return self.store.exists(self.key) or any(k.startswith(self.key + '/') for k in self.store.keys())

    def read_text(self, encoding=None):
        return self.store.read(self.key)

    def write_text(self, text, encoding=None):
        self.store.write(self.key, text)

    def unlink(self):
        self.store.delete(self.key)

    def mkdir(self, parents=False, exist_ok=False):
        pass

    def _match(self, pattern, recursive):
        base = self.key + '/' if self.key else ''
        found = sorted(k for k in self.store.keys() if k.startswith(base) and
                       (recursive or '/' not in k[len(base):]) and fnmatch(k.rsplit('/', 1)[-1], pattern))
        self.store.prefetch(found)  # Callers read what they list; fetch it in one round trip.
        return [StorePath(self.store, k) for k in found]

    def glob(self, pattern):
        return self._match(pattern, False)

    def rglob(self, pattern):
        return self._match(pattern, True)


def encode_key(key):
    return json.dumps(list(key) if isinstance(key, tuple) else key)


def decode_key(raw):
    key = json.loads(raw)
    return tuple(key) if isinstance(key, list) else key


class VolatileState:
    """Sessions, rate limits and draft memory, loaded and saved around each request."""
    NAMES = ('sessions', 'attempts', 'report_attempts', 'drafts', 'draft_epochs', 'inventory_states')

    def __init__(self, redis, prefix):
        self.redis = redis
        self.key = prefix + ':state'
        self.loaded = {}

    def load(self, target):
        flat = self.redis.call('HGETALL', self.key)
        self.loaded = {field: unpack(value) for field, value in zip(flat[::2], flat[1::2])}
        values = {name: {} for name in self.NAMES}
        for field, text in self.loaded.items():
            name, _, key = field.partition(' ')
            if name in values:
                values[name][decode_key(key)] = json.loads(text)
        for name, value in values.items():
            setattr(target, name, value)

    def save(self, target):
        after = {name + ' ' + encode_key(k): json.dumps(v, sort_keys=True)
                 for name in self.NAMES for k, v in getattr(target, name).items()}
        changed = [x for field, text in after.items() if self.loaded.get(field) != text for x in (field, pack(text))]
        removed = [field for field in self.loaded if field not in after]
        self.redis.pipeline(([['HSET', self.key, *changed]] if changed else []) +
                            ([['HDEL', self.key, *removed]] if removed else []))
        self.loaded = after


class Lock:
    """Cross-instance mutual exclusion so revision checks stay authoritative."""
    RELEASE = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end"

    def __init__(self, redis, prefix, ttl_ms=60_000, wait=25):
        self.redis, self.key, self.ttl_ms, self.wait = redis, prefix + ':lock', ttl_ms, wait

    def __enter__(self):
        self.token = secrets.token_hex(16)
        deadline = time.time() + self.wait
        while self.redis.call('SET', self.key, self.token, 'NX', 'PX', self.ttl_ms) is None:
            if time.time() > deadline:
                raise StoreError('The lab is busy saving another change. Try again in a moment.')
            time.sleep(0.05)
        return self

    def __exit__(self, *exc):
        try:
            self.redis.call('EVAL', self.RELEASE, 1, self.key, self.token)
        except StoreError:
            pass  # The lock expires on its own.


def connect():
    """Redis from Vercel/Upstash environment variables, or None when unconfigured."""
    url = os.environ.get('KV_REST_API_URL') or os.environ.get('UPSTASH_REDIS_REST_URL')
    token = os.environ.get('KV_REST_API_TOKEN') or os.environ.get('UPSTASH_REDIS_REST_TOKEN')
    return Redis(url, token) if url and token else None
