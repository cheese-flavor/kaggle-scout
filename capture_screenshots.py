"""Capture real Qt windows with synthetic fixtures, never the user's database."""
import argparse
from pathlib import Path
import re
import tempfile
from datetime import timedelta
from PySide6.QtCore import QTime
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from app import Window, TrashDialog
from ui_theme import apply_theme
from core import Store, DEFAULT, now


def capture(version, output_dir=None):
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Expected a semantic version')
    root = Path(__file__).resolve().parent
    output_dir = Path(output_dir) if output_dir else root / 'docs'
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = 'v' + version.replace('.', '')
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    values = [
        ('데이터 예측 챌린지', 'Python과 SQL로 시작하는 데이터 분석', 'Playground', 'Tabular regression'),
        ('언어 모델 추론 챌린지', 'LLM을 활용한 자연어 추론 문제 해결', 'Research', 'NLP language model'),
        ('시계열 예측 챌린지', '시계열 데이터로 예측하는 미래 수요', 'Featured', 'time series forecast'),
        ('기초 분류 실습', '처음부터 학습하고 제출까지 연습하는 예시 대회', 'Getting Started', 'Tabular classification'),
        ('주택 가격 예측 입문', '회귀 모델과 특성 공학을 연습하는 예시 대회', 'Getting Started', 'Tabular regression'),
    ]
    items = [{'ref': f'fixture-{i}', 'title': t, 'description': d, 'category': cat, 'tags': tags,
              'deadline': '2099-12-31T14:59:00Z' if i >= 3 else (now().replace(hour=14, minute=59, second=0, microsecond=0) + timedelta(days=24)).isoformat(),
              'enabledDate': (now() - timedelta(days=6)).isoformat() if i < 3 else None,
              'newEntrantDeadline': (now() + timedelta(days=21)).isoformat() if i < 3 else None,
              'mergerDeadline': (now() + timedelta(days=22)).isoformat() if i < 3 else None,
              'teamCount': 128,
              'reward': '가상 예시', 'evaluationMetric': '예시 지표', 'maxTeamSize': 5}
             for i, (t, d, cat, tags) in enumerate(values)]
    (root / 'work').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root / 'work') as temp:
        store = Store(temp)
        store.sync(items, DEFAULT)
        window = Window(store, preview=True)
        window.resize(1180, 820)
        window.show()
        outputs = []

        def shot(name, target=None):
            QTest.qWait(180)
            path = output_dir / f'{name}-{suffix}.png'
            if not (target or window).grab().save(str(path)):
                raise RuntimeError('Screenshot save failed')
            outputs.append(path)

        try:
            shot('dashboard')
            document = window.detail.document()
            schedule = document.find('대회 일정').block()
            schedule_top = document.documentLayout().blockBoundingRect(schedule).top()
            window.detail.verticalScrollBar().setValue(max(0, round(schedule_top) - 8))
            shot('detail-information')
            window.detail.verticalScrollBar().setValue(0)
            window.collection_tabs.setCurrentIndex(1)
            shot('education')
            window.resize(960, 680)
            shot('education-small')
            window.resize(1180, 820)
            window.collection_tabs.setCurrentIndex(0)
            window.name_input.setText('민수')
            window.save_settings()
            store.flag('fixture-0', 'starred', True)
            window.navigate(1)
            shot('bookmarks')
            window.delete_competition('fixture-2')
            dialog = TrashDialog(window)
            try:
                dialog.show()
                shot('trash', dialog)
            finally:
                dialog.close()
            profile = store.profile()
            updated = {**items[0], 'deadline': (now() + timedelta(days=5)).isoformat(), 'reward': '가상 예시 · 참가 증명서'}
            store.sync([updated, {**items[1], 'ref': 'fixture-new', 'title': '새 언어 모델 챌린지'}], profile)
            batch = store.notification_batch(profile)
            store.mark_notified([event['id'] for event in batch if event['kind'] != '마감 임박'])
            window.navigate(2)
            shot('notification-history')
            window.navigate(3)
            window.resize(1180, 820)
            window.settings_tabs.setCurrentIndex(2)
            shot('collection-settings')
            window.settings_tabs.setCurrentIndex(0)
            window.settings_scroll.verticalScrollBar().setValue(max(0, window.name_input.parentWidget().y() - 8))
            shot('profile-settings')
            window.settings_tabs.setCurrentIndex(3)
            window.notify_schedule.setCurrentIndex(1)
            window.notify_start.setTime(QTime(22, 0))
            window.notify_end.setTime(QTime(8, 0))
            shot('notifications')
            menu = window.tray.contextMenu()
            menu.popup(window.pos())
            try:
                shot('tray-menu', menu)
            finally:
                menu.close()
            # Independent synthetic records expose the calendar urgency colors.
            with store.connect() as con:
                con.execute('DELETE FROM items')
            examples = [
                ('영상 객체 탐지', '이미지·영상 모델 평가용 예시 대회', 'image vision', 2),
                ('주간 데이터 분석', '정형 데이터 예측용 예시 대회', 'tabular regression', 6),
                ('음성 분류 실험', '음성 인식 모델 비교용 예시 대회', 'audio speech', 14),
                ('수요 시계열 예측', '시계열 예측용 예시 대회', 'time series forecast', 30),
            ]
            store.sync([{'ref': f'color-example-{i}', 'title': t, 'description': d, 'tags': tags,
                         'category': 'Featured', 'deadline': (now() + timedelta(days=days)).isoformat()}
                        for i, (t, d, tags, days) in enumerate(examples)], store.profile())
            window.navigate(0)
            window.resize(1180, 1058)
            window.sort.setCurrentIndex(1)
            window.render()
            window.status.setText('예시 데이터 · 마감·분야 색상')
            shot('deadline-colors')
        finally:
            window.quitting = True
            window.close()
            app.processEvents()
    return outputs


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', required=True)
    args = parser.parse_args()
    for path in capture(args.version):
        print(path)
