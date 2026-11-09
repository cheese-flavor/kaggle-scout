"""One readable, escaped competition detail document for the native Qt panel."""
import html
from core import display_date, plain


DOCUMENT_STYLE = '''
body {font-family:Pretendard;font-size:17px;color:#24394f;}
h2 {font-size:22px;font-weight:700;color:#14243c;margin-top:0;margin-bottom:8px;}
h3 {font-size:18px;font-weight:600;color:#172d43;margin-top:24px;margin-bottom:9px;}
p {font-size:17px;line-height:145%;margin-top:7px;margin-bottom:12px;}
li {font-size:17px;margin-bottom:7px;}
td {font-size:17px;vertical-align:top;}
'''


def text(value, missing='확인 필요'):
    value = missing if value is None or value == '' else str(value)
    return html.escape(value).replace('\n', '<br>')


def fields(rows):
    body = ''.join('<tr><td width="30%"><span style="font-size:14px;color:#627086">' + text(key) + '</span></td>'
                   '<td>' + text(value) + '</td></tr>' for key, value in rows)
    return '<table width="100%" cellspacing="0" cellpadding="5">' + body + '</table>'


def detail_document(item, verdict, exclusions, last_seen, countdown, deadline_colors, topic_ink, long_practice=False):
    body = '<h2>' + text(item.get('title')) + '</h2>'
    deadline_label = '장기 운영 일정 · API상 마감' if long_practice else '최종 제출 마감'
    if countdown and not long_practice:
        deadline_label += ' · ' + countdown
    body += '<table width="100%" cellspacing="0" cellpadding="8" bgcolor="' + deadline_colors['surface'] + '"><tr><td>'
    body += '<span style="font-size:14px;color:' + deadline_colors['ink'] + '">' + text(deadline_label) + '</span><br>'
    body += '<b style="font-size:18px;color:' + deadline_colors['ink'] + '">' + text(display_date(item.get('deadline'))) + '</b>'
    body += '</td></tr></table>'
    eligibility = verdict['eligibility'].removeprefix('참가 대상: ')
    closed = next((reason for reason in verdict['excluded']
                   if reason in ('최종 제출 마감', '신규 참가 마감', '제출 비활성')), None)
    body += fields([('참가 상태' if closed else '참가 대상', closed or eligibility)])
    body += '<p style="color:' + topic_ink + ';font-size:14px;font-weight:600">' + text(' · '.join(verdict['topics']), '분야 확인 필요') + '</p>'
    body += '<p>' + text(plain(item.get('description'))) + '</p>'
    if verdict['education']:
        body += '<h3>교육용 분류</h3><p>' + text(verdict['education_reason']) + '</p>'
    body += '<h3>대회 일정</h3>' + fields([
        ('시작', display_date(item.get('enabledDate'))),
        ('참가 마감', display_date(item.get('newEntrantDeadline'))),
        ('팀 구성 마감', display_date(item.get('mergerDeadline'))),
    ])
    submission = 'Kaggle Notebook 코드 제출' if item.get('isKernelsSubmissionsOnly') else '코드 전용 제한 미표시 · 원문 확인'
    body += '<h3>참가·제출 정보</h3>' + fields([
        ('평가 지표', item.get('evaluationMetric')),
        ('제출 방식', submission), ('최대 팀 인원', item.get('maxTeamSize')),
        ('보상', item.get('reward')), ('참여 팀', item.get('teamCount')),
    ])
    environment = [('GPU', verdict['gpu']), ('API', verdict['api'])]
    if closed:
        environment.insert(0, ('참가 대상', eligibility))
    body += '<h3>참가 조건·내 환경</h3>' + fields(environment)
    body += '<h3>추천 이유</h3><ul>' + ''.join('<li>' + text(reason) + '</li>' for reason in verdict['reasons']) + '</ul>'
    if exclusions:
        body += '<h3 style="color:#ad3646">현재 제외 이유</h3>'
        body += '<ul>' + ''.join('<li>' + text(entry['detail']) + '</li>' for entry in exclusions) + '</ul>'
    if item.get('pages'):
        body += '<h3>추가 설명·규칙</h3><p>' + text(plain(item['pages'])) + '</p>'
    body += '<h3>확인 기록</h3><p style="font-size:14px;color:#627086">' + text(display_date(last_seen)) + '<br>미확인 조건은 Kaggle 원문 확인</p>'
    return body
