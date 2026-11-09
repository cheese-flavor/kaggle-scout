"""Competition-grouped alert records for the native Qt text browser."""
import json

from core import CHANGE_FIELDS, NOTIFY_KINDS, REMINDER_FIELDS, display_date
from detail_view import text
from ui_theme import TONES


HISTORY_STYLE = """
body {font-family:Pretendard;font-size:16px;color:#24394f;}
h2 {font-size:20px;color:#14243c;margin-top:12px;margin-bottom:4px;}
p {margin-top:4px;margin-bottom:9px;}
a {color:#195ea0;}
"""

STATES = {'pending': 'PC 알림 대기', 'sent': 'PC 알림 표시 요청됨',
          'skipped': 'PC 알림 생략', 'legacy': '이전 기록'}
KIND_TONES = {'새 추천': 'blue', '정보 변경': 'violet', '마감 임박': 'amber'}


def event_context(row):
    try:
        context = json.loads(row['context'])
    except (ValueError, TypeError):
        return {}
    return context if isinstance(context, dict) else {}


def change_value(field, value):
    if field in REMINDER_FIELDS and value:
        return text(display_date(value))
    if isinstance(value, bool):
        return '예' if value else '아니요'
    return text(value, '미기재')


def history_document(rows, titles):
    groups = {}
    for row in rows:
        groups.setdefault(row['ref'], []).append(row)
    if not groups:
        return ('<h2>알림 기록 없음</h2>'
                '<p>첫 수집 이후의 새 추천과 관심 대회의 정보 변경·마감이 여기에 표시됩니다.</p>')
    chunks = []
    for ref, events in groups.items():
        title = titles.get(ref) or next((row['message'] for row in events if row['kind'] != '마감 임박'), ref)
        heading = text(title)
        if ref in titles:
            heading = f'<a href="scout:{text(ref)}">{heading}</a>'
        chunks.append(f'<h2>{heading}</h2><p style="font-size:14px;color:#627086">{len(events)}건</p>')
        for row in events:
            kind = row['kind']
            ink = TONES[KIND_TONES.get(kind, 'slate')]['ink']
            stamp = text(display_date(row['created']))
            state = STATES.get(row['delivery'], '기록됨')
            chunks.append(f'<p style="font-size:14px"><b style="color:{ink}">{text(NOTIFY_KINDS.get(kind, kind))}</b>'
                          f' <span style="color:#627086">· {stamp} · {state}</span></p>')
            context = event_context(row)
            if kind == '정보 변경':
                changes = context.get('changes')
                details = []
                for change in changes if isinstance(changes, list) else []:
                    field = change.get('field') if isinstance(change, dict) else None
                    if not isinstance(field, str) or field not in CHANGE_FIELDS:
                        continue
                    before = change_value(field, change.get('before'))
                    after = change_value(field, change.get('after'))
                    details.append(f'<p><b>{CHANGE_FIELDS[field]}</b><br>'
                                   f'<span style="color:#627086">이전</span> {before}<br>'
                                   f'<span style="color:#627086">변경</span> {after}</p>')
                chunks.extend(details or ['<p>변경 항목 미저장</p>'])
            elif kind == '마감 임박':
                field = context.get('field')
                label = REMINDER_FIELDS.get(field) if isinstance(field, str) else None
                deadline = context.get('deadline')
                summary = f'{label} 마감 · {display_date(deadline)}' if label and deadline else row['message']
                chunks.append(f'<p>{text(summary)}</p>')
        chunks.append('<hr>')
    return ''.join(chunks)
