"""Kaggle Scout: deterministic local discovery, no generative AI."""
import base64
import ctypes
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import copy
import time
from datetime import datetime, timezone, timedelta
import requests

UTC = timezone.utc
KST = timezone(timedelta(hours=9))
NOTIFY_KINDS = {'새 추천': '새 대회', '정보 변경': '정보 변경', '마감 임박': '마감 임박'}
AUDIENCES = {'general': '일반인 / 공개 참가', 'university': '대학생·대학원생',
             'youth': '청소년·초중고', 'student': '학생 (세부 구분 미공개)'}
TOPICS = {
    '정형 데이터 / SQL': ['tabular', 'structured data', 'regression', 'sql', 'analytics', 'predict house', 'predict sales'],
    '시계열': ['time series', 'time-series', 'forecast'],
    'NLP': ['nlp', 'natural language', 'text', 'language processing', 'translation'],
    'LLM / 생성형 AI': ['llm', 'language model', 'generative', 'gemma', 'reasoning', 'agent'],
    '이미지 / 영상': ['image', 'vision', 'video', 'segmentation', 'detection'],
    '음성': ['audio', 'speech', 'sound'],
    'AI 서비스 / 웹 개발': ['application', 'app development', 'web development', 'hackathon', 'agent'],
}
DEFAULT = {'name': '나의 프로필', 'topics': list(TOPICS), 'skills': 'Python, SQL',
           'gpu': 'RTX 5060 Ti', 'vram': 16, 'paid_api': False,
           'exclude_students': True, 'exclude_offline': True,
           'exclude_keywords': [], 'interval': 60, 'notify': True,
           'purposes': ['학습', '포트폴리오', '취업', '수상'], 'min_score': 0,
           'page_size': 10, 'audiences': ['general'], 'include_unknown_audience': True,
           'notify_kinds': list(NOTIFY_KINDS), 'notify_schedule': 'always',
           'notify_start': '09:00', 'notify_end': '22:00',
           'separate_education': True, 'education_playground': False,
           'notify_education': False}

def migrate_profile(value):
    value = dict(value)
    if 'audiences' not in value:
        value['audiences'] = ['general'] if value.get('exclude_students', True) else list(AUDIENCES)
    return {**copy.deepcopy(DEFAULT), **value}

def validate_profile(value):
    if not isinstance(value, dict):
        raise ValueError('프로필 형식 오류')
    for key in DEFAULT:
        if key in value and type(value[key]) is not type(DEFAULT[key]):
            raise ValueError('프로필 값 형식 오류')
    profile = migrate_profile({k: value[k] for k in DEFAULT if k in value})
    if not (15 <= profile['interval'] <= 1440 and 0 <= profile['vram'] <= 512 and 0 <= profile['min_score'] <= 100):
        raise ValueError('프로필 범위 오류')
    if profile['page_size'] not in (5, 10, 20, 50):
        raise ValueError('페이지 크기 오류')
    if profile['notify_schedule'] not in ('always', 'window'):
        raise ValueError('알림 시간 설정을 확인하세요.')
    for key in ('notify_start', 'notify_end'):
        if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', profile[key]):
            raise ValueError('알림 시간은 HH:MM 형식이어야 합니다.')
    if profile['notify_schedule'] == 'window' and profile['notify_start'] == profile['notify_end']:
        raise ValueError('알림 시작과 종료 시간을 다르게 선택하세요.')
    if len(profile['notify_kinds']) > len(NOTIFY_KINDS) or not all(isinstance(k, str) and k in NOTIFY_KINDS for k in profile['notify_kinds']):
        raise ValueError('알림 종류를 확인하세요.')
    for key, allowed in [('topics', TOPICS), ('audiences', AUDIENCES)]:
        if not all(isinstance(x, str) and x in allowed for x in profile[key]) or len(profile[key]) > len(allowed):
            raise ValueError('프로필 선택값 오류')
    words = profile['exclude_keywords']
    if len(words) > 50 or not all(isinstance(x, str) and len(x) <= 80 for x in words):
        raise ValueError('제외 키워드 길이 오류')
    for key, maximum in [('name', 100), ('gpu', 120), ('skills', 250)]:
        if len(profile[key]) > maximum:
            raise ValueError('프로필 텍스트 길이 오류')
    if not all(isinstance(x, str) and len(x) <= 80 for x in profile['purposes']) or len(profile['purposes']) > 20:
        raise ValueError('참가 목적 형식 오류')
    return profile

def read_json_file(path, maximum=65536):
    with Path(path).open('rb') as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError('파일 크기 초과')
    return json.loads(raw.decode('utf-8-sig'))

def validate_credentials(value):
    if not isinstance(value, dict):
        raise ValueError('인증 형식 오류')
    fields = ['token'] if value.get('token') else ['username', 'key']
    if any(not isinstance(value.get(k), str) or not value[k] or len(value[k]) > 8192 or
           any(ord(c) < 32 or ord(c) == 127 for c in value[k]) for k in fields):
        raise ValueError('인증 값 오류')
    return {key: value[key] for key in fields}

def detect_audience(text):
    university = re.search(r'(?:(?:university|college|graduate) students only|(?:open|available) only to (?:university|college|graduate) students|대학(?:원)?생\s*(?:전용|만\s*참가))', text)
    youth = re.search(r'(?:high school students only|(?:초중고|중고등|고등|중학)학생\s*(?:전용|만\s*참가)|청소년\s*전용)', text)
    student = re.search(r'(?:only (?:open|available) to (?:university |college )?students|students only|student-only|학생\s*전용|재학생만)', text)
    public = re.search(r'(?:open to (?:anyone|everyone|all)|anyone can (?:enter|participate)|일반인\s*참가\s*가능|누구나\s*참가)', text)
    if public and (student or university or youth):
        return [], '참가 대상: 문구가 혼재되어 원문 확인 필요'
    if university:
        return ['university'], '참가 대상: 대학생·대학원생 전용 문구 감지'
    if youth:
        return ['youth'], '참가 대상: 청소년·초중고 전용 문구 감지'
    if student:
        return ['student'], '참가 대상: 학생 전용 문구 감지 (세부 구분 미공개)'
    if public:
        return ['general'], '참가 대상: 일반 공개 문구 감지 · 세부 자격 원문 확인'
    return [], '참가 대상: 규칙 확인 필요'

def now():
    return datetime.now(UTC)

def date(value):
    if not value:
        return None
    try:
        text = str(value)
        if re.search(r'[+-]\d\d:\d\dZ$', text):
            text = text[:-1]
        d = datetime.fromisoformat(text.replace('Z', '+00:00'))
        return d.replace(tzinfo=UTC) if d.tzinfo is None else d
    except (ValueError, TypeError):
        return None

def display_date(value):
    d = date(value)
    return d.astimezone(KST).strftime('%Y-%m-%d %H:%M KST') if d else '확인 필요'

def plain(value):
    import html
    return html.unescape(re.sub('<[^>]+>', ' ', str(value or '')))

def fingerprint(item):
    # Popularity and rank change frequently; neither should trigger a change alert.
    fields = ('title', 'description', 'deadline', 'newEntrantDeadline', 'mergerDeadline',
              'reward', 'maxTeamSize', 'isKernelsSubmissionsOnly', 'submissionsDisabled', 'pages')
    return hashlib.sha256(json.dumps({k: item.get(k) for k in fields},
                                     sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def slug(item):
    value = str(item.get('ref', '')).rstrip('/').split('/')[-1]
    if not re.fullmatch(r'[A-Za-z0-9_-]+', value):
        raise ValueError('올바르지 않은 Kaggle 대회 식별자입니다.')
    return value

def education_info(item, profile):
    """Use category evidence, never a distant deadline, to identify practice contests."""
    category = re.sub(r'[^a-z0-9]', '', str(item.get('category', '')).lower())
    if category in ('gettingstarted', 'hostsegmentgettingstarted', 'competitioncategorygettingstarted'):
        return True, 'Kaggle Getting Started 카테고리'
    if profile.get('education_playground', False) and category in ('playground', 'hostsegmentplayground', 'competitioncategoryplayground'):
        return True, '설정에서 Playground를 교육용으로 포함'
    # Exact identifiers only; generic words such as "beginner" are not sufficient.
    starters = {'titanic', 'house-prices-advanced-regression-techniques', 'digit-recognizer', 'spaceship-titanic'}
    ref = str(item.get('ref', '')).rstrip('/').split('/')[-1].lower()
    if not category and ref in starters:
        return True, 'Kaggle 공식 입문 대회 식별자 (카테고리 미제공)'
    return False, '입문 카테고리 근거 없음 · 일반 대회로 표시'


def allow_new_recommendation(item, profile):
    return profile.get('notify_education', False) or not education_info(item, profile)[0]


def assess(item, profile, at=None):
    at = at or now()
    text = plain(' '.join([str(item.get(k, '')) for k in ('title', 'description', 'tags', 'pages')])).lower()
    matched = [name for name, words in TOPICS.items() if any(w in text for w in words)]
    reasons, excluded = [], []
    score = 20
    for topic in matched:
        if topic in profile['topics']:
            score += 12
            reasons.append(topic + ' 관련 키워드')
    category = str(item.get('category', '')).lower()
    if 'getting' in category or 'playground' in category:
        score += 15
        reasons.append('입문·연습 카테고리')
    if not reasons:
        reasons.append('분야 미분류 — 폭넓은 탐색 후보')
    end = date(item.get('deadline'))
    if end and end <= at:
        excluded.append('최종 제출 마감')
    entry = date(item.get('newEntrantDeadline'))
    if entry and entry <= at and not item.get('userHasEntered'):
        excluded.append('신규 참가 마감')
    if item.get('submissionsDisabled'):
        excluded.append('제출 비활성')
    groups, eligibility = detect_audience(text)
    offline = re.search(r'(?:in.person attendance (?:is )?required|mandatory (?:in.person|onsite)|오프라인\s*(?:참석\s*)?필수)', text)
    paid = re.search(r'(?:paid api (?:is )?required|requires? (?:a )?paid api|유료\s*api\s*필수)', text)
    selected_groups = profile.get('audiences', ['general'] if profile.get('exclude_students', True) else list(AUDIENCES))
    if groups and not set(groups).intersection(selected_groups):
        excluded.append('선택한 참가 구분과 다름 — 원문 검토 필요')
    if not groups and not profile.get('include_unknown_audience', True):
        excluded.append('참가 구분 미확인')
    if offline and profile['exclude_offline']:
        excluded.append('오프라인 필수 문구 감지 — 원문 검토 필요')
    if paid and not profile['paid_api']:
        excluded.append('유료 API 필수 문구 감지 — 원문 검토 필요')
    for word in profile.get('exclude_keywords', []):
        if word.strip() and word.lower() in text:
            excluded.append('제외 키워드: ' + word)
    # A conservative hint, never an assertion that the entire competition fits.
    gpu = f"{profile['gpu']} {profile['vram']}GB: 요구 VRAM 확인 필요"
    requirement = re.search(r'(?:requires?|minimum|at least)\s+(?:a\s+)?(\d+(?:\.\d+)?)\s*gb\s*(?:of\s*)?(?:gpu\s*)?(?:vram|gpu memory)', text)
    if requirement:
        needed = float(requirement[1])
        gpu = f"최소 VRAM {needed:g}GB 문구 감지 · 보유 {profile['vram']}GB · 원문 검토 필요"
        if needed > profile['vram']:
            excluded.append('최소 VRAM 요구 문구가 내 환경을 초과 — 원문 검토 필요')
        else:
            gpu += ' · 용량 조건 내 후보 (실행 보장 아님)'
    if '정형 데이터 / SQL' in matched:
        gpu += ' · 정형 데이터 기본 모델부터 검토 가능'
    if 'LLM / 생성형 AI' in matched or '이미지 / 영상' in matched:
        gpu += ' · 모델 크기·학습 방식·제출 제한 확인'
    education, education_reason = education_info(item, profile)
    return {'score': min(score, 100), 'topics': matched, 'reasons': reasons,
            'education': education, 'education_reason': education_reason,
            'excluded': excluded, 'gpu': gpu, 'eligibility': eligibility, 'audiences': groups,
            'api': '유료 API 필수 문구 감지' if paid else '유료 API 필요 여부: 규칙 확인 필요'}

EXCLUSION_LABELS = {'deadline': '마감', 'audience': '참가 대상', 'gpu': 'GPU 용량',
                    'paid_api': '유료 API', 'offline': '오프라인', 'keyword': '제외 키워드',
                    'score': '추천 점수', 'status': '제출 상태', 'other': '기타'}

def exclusion_details(item, profile, verdict=None):
    verdict = verdict or assess(item, profile)
    details = []
    for reason in verdict['excluded']:
        code = ('deadline' if '마감' in reason else 'audience' if '참가 구분' in reason else
                'gpu' if 'VRAM' in reason else 'paid_api' if '유료 API' in reason else
                'offline' if '오프라인' in reason else 'keyword' if '제외 키워드' in reason else
                'status' if '제출 비활성' in reason else 'other')
        detail = reason
        if code == 'gpu':
            detail += '\n' + verdict['gpu']
        elif code == 'deadline':
            field = 'newEntrantDeadline' if '신규 참가' in reason else 'deadline'
            detail += '\n' + display_date(item.get(field))
        details.append({'code': code, 'label': EXCLUSION_LABELS[code], 'detail': detail})
    if verdict['score'] < profile['min_score']:
        details.append({'code': 'score', 'label': EXCLUSION_LABELS['score'],
                        'detail': f"탐색 점수 {verdict['score']}점 < 설정한 최소 {profile['min_score']}점"})
    return details

def notification_window_open(profile, at=None):
    if profile['notify_schedule'] == 'always':
        return True
    current = (at or now()).astimezone(KST).strftime('%H:%M')
    start, end = profile['notify_start'], profile['notify_end']
    return start <= current < end if start < end else current >= start or current < end

class Blob(ctypes.Structure):
    _fields_ = [('size', ctypes.c_uint32), ('data', ctypes.POINTER(ctypes.c_ubyte))]

def protect(raw, decrypt=False):
    if os.name != 'nt':
        raise RuntimeError('이 버전의 인증 저장은 Windows에서 지원됩니다.')
    buffer = ctypes.create_string_buffer(raw)
    incoming = Blob(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    outgoing = Blob()
    dll = ctypes.windll.crypt32
    fn = dll.CryptUnprotectData if decrypt else dll.CryptProtectData
    if not fn(ctypes.byref(incoming), None, None, None, None, 1, ctypes.byref(outgoing)):
        raise RuntimeError('Windows 계정 암호화에 실패했습니다. 이 PC에서 다시 연결하세요.')
    try:
        return ctypes.string_at(outgoing.data, outgoing.size)
    finally:
        ctypes.windll.kernel32.LocalFree(ctypes.cast(outgoing.data, ctypes.c_void_p))

class Store:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.db = self.folder / 'scout.sqlite3'
        with self.connect() as con:
            con.executescript('''
            CREATE TABLE IF NOT EXISTS items(ref TEXT PRIMARY KEY, body TEXT NOT NULL,
              hash TEXT NOT NULL, first_seen TEXT, last_seen TEXT, starred INTEGER DEFAULT 0,
              hidden INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, created TEXT, kind TEXT,
              ref TEXT, message TEXT);
            CREATE TABLE IF NOT EXISTS reminders(key TEXT PRIMARY KEY);
            ''')
            columns = {r['name'] for r in con.execute('PRAGMA table_info(events)')}
            for name, definition in [('delivery', "TEXT NOT NULL DEFAULT 'legacy'"), ('context', "TEXT NOT NULL DEFAULT '{}' ")]:
                if name not in columns:
                    con.execute(f'ALTER TABLE events ADD COLUMN {name} {definition}')

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.db, timeout=15)
        con.row_factory = sqlite3.Row
        try:
            with con:
                yield con
        finally:
            con.close()

    def get(self, key, default=None):
        with self.connect() as con:
            row = con.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, key, value):
        with self.connect() as con:
            con.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', (key, json.dumps(value, ensure_ascii=False)))

    def profile(self):
        try:
            return validate_profile(self.get('profile', {}))
        except (ValueError, TypeError, RecursionError):
            # Keep the damaged record intact; recover the UI with safe defaults.
            return copy.deepcopy(DEFAULT)

    def save_credentials(self, credentials):
        value = validate_credentials(credentials)
        self.set('credentials', base64.b64encode(protect(json.dumps(value).encode())).decode())

    def credentials(self):
        try:
            value = self.get('credentials')
            if not value:
                return None
            return validate_credentials(json.loads(protect(base64.b64decode(value, validate=True), True)))
        except (ValueError, TypeError, RecursionError):
            raise RuntimeError('저장된 인증 정보를 확인할 수 없습니다. 이 PC에서 다시 연결하세요.') from None

    def clear_credentials(self):
        with self.connect() as con:
            con.execute('PRAGMA secure_delete=ON')
            con.execute("DELETE FROM meta WHERE key='credentials'")

    def rows(self):
        with self.connect() as con:
            return [dict(r) for r in con.execute('SELECT * FROM items')]

    def flag(self, ref, column, value):
        if column not in ('starred', 'hidden'):
            raise ValueError(column)
        with self.connect() as con:
            con.execute(f'UPDATE items SET {column}=? WHERE ref=?', (int(value), ref))

    def sync(self, items, profile, at=None):
        at = at or now()
        stamp = at.isoformat()
        first = not self.get('initialized', False)
        notices = []
        with self.connect() as con:
            for item in items:
                ref = slug(item)
                old = con.execute('SELECT * FROM items WHERE ref=?', (ref,)).fetchone()
                digest = fingerprint(item)
                con.execute('''INSERT INTO items(ref,body,hash,first_seen,last_seen) VALUES(?,?,?,?,?)
                  ON CONFLICT(ref) DO UPDATE SET body=excluded.body,hash=excluded.hash,last_seen=excluded.last_seen''',
                            (ref, json.dumps(item, ensure_ascii=False), digest, stamp, stamp))
                verdict = assess(item, profile, at)
                eligible = not verdict['excluded'] and verdict['score'] >= profile['min_score']
                kind = None
                if not first and old is None and eligible and allow_new_recommendation(item, profile):
                    kind = '새 추천'
                elif old and old['hash'] != digest and old['starred'] and not old['hidden']:
                    kind = '정보 변경'
                if kind and not (old and old['hidden']):
                    msg = item.get('title', ref)
                    notices.append((kind, msg, ref))
                    con.execute("INSERT INTO events(created,kind,ref,message,delivery) VALUES(?,?,?,?,'pending')", (stamp, kind, ref, msg))
            # Interest reminders also run over cached records and recover after sleep.
            for row in con.execute('SELECT * FROM items WHERE starred=1 AND hidden=0').fetchall():
                item = json.loads(row['body'])
                for field, label in [('newEntrantDeadline', '참가'), ('mergerDeadline', '팀 구성'), ('deadline', '제출')]:
                    end = date(item.get(field))
                    if not end or end <= at:
                        continue
                    hours = (end - at).total_seconds() / 3600
                    bucket = 1 if hours <= 24 else 3 if hours <= 72 else 7 if hours <= 168 else None
                    if bucket is None:
                        continue
                    key = f"{row['ref']}|{field}|{end.isoformat()}|{bucket}"
                    if con.execute('INSERT OR IGNORE INTO reminders VALUES(?)', (key,)).rowcount:
                        msg = f"{item.get('title', row['ref'])} · {label} 마감 {display_date(end.isoformat())}"
                        notices.append(('마감 임박', msg, row['ref']))
                        con.execute("INSERT INTO events(created,kind,ref,message,delivery,context) VALUES(?,?,?,?,'pending',?)", (stamp, '마감 임박', row['ref'], msg, json.dumps({'field': field, 'deadline': end.isoformat()})))
        self.set('initialized', True)
        return first, notices

    def notification_batch(self, profile, at=None):
        at = at or now()
        ready = []
        with self.connect() as con:
            for event in con.execute("SELECT * FROM events WHERE delivery='pending' ORDER BY id").fetchall():
                skip = not profile['notify'] or event['kind'] not in profile['notify_kinds']
                row = con.execute('SELECT * FROM items WHERE ref=?', (event['ref'],)).fetchone()
                skip = skip or row is None or bool(row['hidden'])
                if row:
                    item = json.loads(row['body'])
                    if event['kind'] == '새 추천':
                        skip = skip or not allow_new_recommendation(item, profile) or bool(exclusion_details(item, profile, assess(item, profile, at)))
                    elif event['kind'] in ('마감 임박', '정보 변경'):
                        skip = skip or not row['starred']
                    if event['kind'] == '마감 임박':
                        context = json.loads(event['context'])
                        end = date(context.get('deadline'))
                        skip = skip or not end or end <= at or date(item.get(context.get('field', ''))) != end
                if skip:
                    con.execute("UPDATE events SET delivery='skipped' WHERE id=?", (event['id'],))
                elif notification_window_open(profile, at):
                    ready.append(dict(event))
        return ready

    def mark_notified(self, ids):
        with self.connect() as con:
            con.executemany("UPDATE events SET delivery='sent' WHERE id=? AND delivery='pending'", [(i,) for i in ids])

class Kaggle:
    BASE = 'https://api.kaggle.com/v1/competitions.CompetitionApiService/'
    MAX_RESPONSE_BYTES = 8 * 1024 * 1024

    def __init__(self, credentials):
        if not credentials:
            raise RuntimeError('최초 연결에서 Kaggle 인증을 설정하세요.')
        try:
            credentials = validate_credentials(credentials)
        except ValueError:
            raise RuntimeError('Kaggle 인증 형식이 올바르지 않습니다.') from None
        self.session = requests.Session()
        self.session.trust_env = False  # Do not load ambient .netrc credentials or proxy settings.
        self.session.headers['User-Agent'] = 'KaggleScout/1.0 personal-local-monitor'
        if credentials.get('token'):
            self.session.headers['Authorization'] = 'Bearer ' + credentials['token']
        else:
            self.session.auth = (credentials['username'], credentials['key'])

    def call(self, method, body):
        if method not in ('ListCompetitions', 'ListCompetitionPages'):
            raise RuntimeError('허용되지 않은 Kaggle 조회 요청입니다.')
        try:
            with self.session.post(self.BASE + method, json=body, timeout=(10, 35),
                                   allow_redirects=False, verify=True, stream=True) as response:
                if response.status_code in (401, 403):
                    raise RuntimeError('Kaggle 인증 또는 접근 권한을 확인하세요. 설정에서 다시 연결할 수 있습니다.')
                if response.status_code == 429:
                    raise RuntimeError('Kaggle 요청 제한입니다. 다음 확인 주기에 다시 시도합니다.')
                if 300 <= response.status_code < 400:
                    raise RuntimeError('Kaggle API 주소 변경 응답을 차단했습니다.')
                response.raise_for_status()
                raw = bytearray()
                started = time.monotonic()
                for chunk in response.iter_content(65536):
                    raw.extend(chunk)
                    if len(raw) > self.MAX_RESPONSE_BYTES or time.monotonic() - started > 60:
                        raise RuntimeError('Kaggle 응답 한도를 초과했습니다. 기존 기록을 유지합니다.')
                data = json.loads(raw)
            if not isinstance(data, dict) or data.get('error'):
                raise RuntimeError('Kaggle 응답 형식 또는 API 오류입니다.')
            return data
        except requests.RequestException:
            raise RuntimeError('Kaggle 연결에 실패했습니다. 인터넷 상태를 확인하세요.') from None
        except (ValueError, RecursionError):
            raise RuntimeError('Kaggle 응답 형식이 올바르지 않습니다.') from None

    def collect(self):
        # Token pagination, with a bounded safety cap. No partial success is committed.
        items, seen_tokens, seen_refs = [], set(), set()
        token = ''
        for _ in range(100):
            body = {'pageSize': 100, 'sortBy': 'COMPETITION_SORT_BY_RECENTLY_CREATED',
                    'group': 'COMPETITION_LIST_TAB_GENERAL'}
            if token:
                body['pageToken'] = token
            data = self.call('ListCompetitions', body)
            if 'competitions' not in data:
                # Empty repeated fields may be omitted by protobuf JSON.
                if data == {}:
                    return items
                raise RuntimeError('대회 목록 응답을 해석할 수 없습니다. 기존 기록을 유지합니다.')
            batch = data['competitions']
            if not isinstance(batch, list):
                raise RuntimeError('대회 목록 형식이 올바르지 않습니다.')
            for item in batch:
                if not isinstance(item, dict):
                    raise RuntimeError('대회 항목 형식이 올바르지 않습니다.')
                ref = slug(item)
                if ref not in seen_refs:
                    items.append(item)
                    seen_refs.add(ref)
            token = data.get('nextPageToken', '')
            if not token:
                return items
            if token in seen_tokens:
                raise RuntimeError('Kaggle 페이지 순환 오류입니다. 기존 기록을 유지합니다.')
            seen_tokens.add(token)
        raise RuntimeError('조회 페이지 한도를 초과했습니다. 기존 기록을 유지합니다.')

    def pages(self, ref):
        ref = slug({'ref': ref})
        data = self.call('ListCompetitionPages', {'competitionName': ref})
        pages = data.get('pages', [])
        if not isinstance(pages, list) or not all(isinstance(p, dict) for p in pages):
            raise RuntimeError('대회 규칙 응답 형식이 올바르지 않습니다.')
        return pages
