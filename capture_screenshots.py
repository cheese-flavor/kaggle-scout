"""Capture real Qt windows with synthetic fixtures, never the user's database."""
import argparse
from pathlib import Path
import re
import tempfile
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtTest import QTest
from app import Window, ASSETS, STYLE
from core import Store, DEFAULT


def capture(version):
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Expected a semantic version')
    root = Path(__file__).resolve().parent
    suffix = 'v' + version.replace('.', '')
    app = QApplication.instance() or QApplication([])
    for font in ASSETS.glob('Pretendard-*.otf'):
        QFontDatabase.addApplicationFont(str(font))
    app.setFont(QFont('Pretendard', 11))
    app.setStyleSheet(STYLE)
    values = [
        ('데이터 예측 챌린지', 'Python과 SQL로 시작하는 데이터 분석', 'Playground', 'Tabular regression'),
        ('언어 모델 추론 챌린지', 'LLM을 활용한 자연어 추론 문제 해결', 'Research', 'NLP language model'),
        ('시계열 예측 챌린지', '시계열 데이터로 예측하는 미래 수요', 'Featured', 'time series forecast'),
        ('기초 분류 실습', '처음부터 학습하고 제출까지 연습하는 예시 대회', 'Getting Started', 'Tabular classification'),
        ('주택 가격 예측 입문', '회귀 모델과 특성 공학을 연습하는 예시 대회', 'Getting Started', 'Tabular regression'),
    ]
    items = [{'ref': f'fixture-{i}', 'title': t, 'description': d, 'category': cat, 'tags': tags,
              'deadline': '2099-12-31T14:59:00Z' if i >= 3 else '2026-11-30T14:59:00Z',
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

        def shot(name):
            QTest.qWait(180)
            path = root / 'docs' / f'{name}-{suffix}.png'
            if not window.grab().save(str(path)):
                raise RuntimeError('Screenshot save failed')
            outputs.append(path)

        try:
            shot('dashboard')
            window.collection_tabs.setCurrentIndex(1)
            shot('education')
            window.resize(960, 680)
            shot('education-small')
            window.navigate(3)
            window.resize(1180, 820)
            window.settings_tabs.setCurrentIndex(2)
            shot('collection-settings')
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
