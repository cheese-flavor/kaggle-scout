import copy
import html
import json
import os
from pathlib import Path
import sys
from datetime import timedelta
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QLockFile, QUrl
from PySide6.QtGui import QIcon, QFont, QFontDatabase, QDesktopServices, QAction
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QFrame, QLabel,
    QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout, QStackedWidget, QScrollArea,
    QLineEdit, QComboBox, QSpinBox, QCheckBox, QTextBrowser, QMessageBox, QDialog,
    QFileDialog, QSystemTrayIcon, QMenu, QSplitter, QSlider, QListWidget, QListWidgetItem)
from core import Store, Kaggle, DEFAULT, TOPICS, AUDIENCES, validate_profile, read_json_file, validate_credentials, assess, now, date, display_date, plain, slug
from installation import data_directory, migrate_database
from core import exclusion_details, EXCLUSION_LABELS

ROOT = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
ASSETS = Path(getattr(sys, '_MEIPASS', ROOT)) / 'assets'
STYLE = '''
* { font-family: "Pretendard", "Malgun Gothic"; font-size: 14px; font-weight: 400; color: #23364b; }
QMainWindow, QDialog { background: #f5f8fc; }
QWidget#sidebar { background: #ffffff; border-right: 1px solid #e3ebf3; }
QFrame#card { background: #ffffff; border: 1px solid #e2eaf2; border-radius: 14px; }
QFrame#hero { background: #e9f8ff; border: 1px solid #c5edff; border-radius: 16px; }
QLabel { background: transparent; border: none; }
QLabel#muted { color: #586c82; font-size: 14px; }
QLabel#eyebrow { color: #087da4; font-size: 12px; font-weight: 600; }
QLabel#heading { font-size: 25px; font-weight: 600; color: #152b42; }
QLabel#title { font-size: 17px; font-weight: 600; }
QPushButton { background: white; border: 1px solid #dbe5ee; border-radius: 8px; padding: 10px 16px; font-weight: 500; }
QPushButton:hover { background: #eef8fd; border-color: #9edff9; }
QPushButton:pressed { background: #d3f0fc; }
QPushButton:disabled { color: #9daab6; background: #edf2f7; }
QPushButton#primary { background: #20beff; color: #10374b; border-color: #20beff; }
QPushButton#primary:hover { background: #60d0ff; }
QPushButton#primary:disabled { background: #edf2f7; color: #91a0af; border-color: #dbe5ee; }
QPushButton#nav { text-align: left; border: none; background: transparent; padding: 13px 16px; color: #63758a; }
QPushButton#nav:checked { background: #e8f8ff; color: #027eab; }
QLineEdit, QComboBox, QSpinBox { background: #ffffff; border: 1px solid #d9e4ee; border-radius: 8px; padding: 10px; min-height: 18px; }
QLineEdit:focus, QSpinBox:focus { border: 1px solid #20beff; }
QCheckBox { spacing: 10px; padding: 5px; }
QCheckBox::indicator { width: 17px; height: 17px; }
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QTextBrowser { background: #ffffff; border: none; padding: 12px; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 3px; }
QScrollBar::handle:vertical { background: #c8d8e5; min-height: 30px; border-radius: 3px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QSlider::groove:horizontal { height: 6px; background: #dfe9f2; border-radius: 3px; }
QSlider::sub-page:horizontal { background: #20beff; border-radius: 3px; }
QSlider::handle:horizontal { background: #ffffff; border: 2px solid #159cd2; width: 16px; margin: -7px 0; border-radius: 9px; }
QSlider::handle:horizontal:focus { border: 3px solid #102c43; }
QWidget#settingsFooter { background: #ffffff; border-top: 1px solid #dfe9f2; }
'''

def label(text, kind=None, wrap=False):
    w = QLabel()
    w.setTextFormat(Qt.TextFormat.PlainText)
    w.setText(str(text))
    if kind:
        w.setObjectName(kind)
    w.setWordWrap(wrap)
    return w

def button(text, fn, primary=False):
    b = QPushButton(text)
    if primary:
        b.setObjectName('primary')
    b.clicked.connect(fn)
    return b

def card(hero=False):
    w = QFrame()
    w.setObjectName('hero' if hero else 'card')
    box = QVBoxLayout(w)
    box.setContentsMargins(22, 20, 22, 20)
    box.setSpacing(12)
    return w, box

def clear(layout):
    while layout.count():
        entry = layout.takeAt(0)
        if entry.widget():
            entry.widget().deleteLater()
        elif entry.layout():
            clear(entry.layout())

class SafeTextBrowser(QTextBrowser):
    def __init__(self):
        super().__init__()
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)

    def loadResource(self, resource_type, name):
        # Display only escaped text supplied by the app; never load local/remote resources.
        return None

class SliderInput(QWidget):
    """A slider for quick changes, plus exact input that preserves out-of-range values."""
    valueChanged = Signal(int)

    def __init__(self, name, minimum, maximum, value, suffix='', slider_max=None,
                 stops=None, presets=(), low_label='', high_label=''):
        super().__init__()
        self.stops = list(stops) if stops else None
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(6)
        row = QHBoxLayout()
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, len(self.stops) - 1) if self.stops else self.slider.setRange(minimum, slider_max or maximum)
        self.slider.setAccessibleName(name + ' 슬라이더')
        self.slider.setToolTip('방향키로 조절하거나 오른쪽에 정확한 값을 입력하세요.')
        self.spinbox = QSpinBox()
        self.spinbox.setRange(minimum, maximum)
        self.spinbox.setSuffix(suffix)
        self.spinbox.setAccessibleName(name + ' 정확한 값')
        self.spinbox.setFixedWidth(118)
        self.spinbox.setKeyboardTracking(False)
        row.addWidget(self.slider, 1)
        row.addWidget(self.spinbox)
        box.addLayout(row)
        if low_label or high_label:
            legend = QHBoxLayout()
            legend.addWidget(label(low_label, 'muted'))
            legend.addStretch()
            legend.addWidget(label(high_label, 'muted'))
            box.addLayout(legend)
        if presets:
            chips = QHBoxLayout()
            for number, text in presets:
                b = button(text, lambda checked=False, n=number: self.setValue(n))
                b.setAccessibleName(name + ' ' + text)
                chips.addWidget(b)
            chips.addStretch()
            box.addLayout(chips)
        self.slider.valueChanged.connect(self.from_slider)
        self.spinbox.valueChanged.connect(self.from_number)
        self.setValue(value)

    def value(self):
        return self.spinbox.value()

    def setValue(self, value):
        self.spinbox.setValue(value)
        self.from_number(self.spinbox.value(), emit=False)

    def from_slider(self, value):
        self.spinbox.setValue(self.stops[value] if self.stops else value)

    def from_number(self, value, emit=True):
        self.slider.blockSignals(True)
        position = min(range(len(self.stops)), key=lambda i: abs(self.stops[i] - value)) if self.stops else min(value, self.slider.maximum())
        self.slider.setValue(position)
        self.slider.blockSignals(False)
        if emit:
            self.valueChanged.emit(value)

class ExclusionDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle('대회가 제외된 이유')
        self.resize(720, 560)
        box = QVBoxLayout(self)
        box.setContentsMargins(24, 24, 24, 24)
        box.addWidget(label('제외 이유 확인', 'heading'))
        box.addWidget(label('저장된 조건 기준이며 숨긴 대회는 제외합니다. 한 대회에 여러 이유가 있을 수 있습니다.', 'muted', True))
        self.entries = []
        profile = window.store.profile()
        counts = {}
        for row in window.store.rows():
            if row['hidden']:
                continue
            item = json.loads(row['body'])
            details = exclusion_details(item, profile)
            if details:
                self.entries.append((row['ref'], item, details))
                for code in {d['code'] for d in details}:
                    counts[code] = counts.get(code, 0) + 1
        self.reason = QComboBox()
        self.reason.addItem(f'전체 제외 대회 ({len(self.entries)}개)', '')
        for code, text in EXCLUSION_LABELS.items():
            if code in counts:
                self.reason.addItem(f'{text} ({counts[code]}개)', code)
        box.addWidget(self.reason)
        self.items = QListWidget()
        self.items.setWordWrap(True)
        box.addWidget(self.items, 1)
        self.explanation = label('', 'muted', True)
        box.addWidget(self.explanation)
        actions = QHBoxLayout()
        actions.addWidget(button('설정 조정', self.adjust))
        self.view_button = button('목록에서 보기', self.view, True)
        actions.addWidget(self.view_button)
        actions.addWidget(button('닫기', self.accept))
        box.addLayout(actions)
        self.reason.currentIndexChanged.connect(self.fill)
        self.items.currentItemChanged.connect(self.describe)
        self.fill()

    def fill(self, *_):
        self.items.clear()
        for ref, item, details in self.entries:
            if self.reason.currentData() and not any(d['code'] == self.reason.currentData() for d in details):
                continue
            entry = QListWidgetItem(str(item.get('title', ref)) + '\n' + ' · '.join(dict.fromkeys(d['label'] for d in details)))
            entry.setData(Qt.ItemDataRole.UserRole, (ref, item, details))
            self.items.addItem(entry)
        if self.items.count():
            self.items.setCurrentRow(0)
        else:
            self.explanation.setText('현재 조건으로 제외된 대회가 없습니다.')
        self.view_button.setEnabled(self.items.count() > 0)

    def describe(self, current, previous=None):
        if current:
            _, _, details = current.data(Qt.ItemDataRole.UserRole)
            self.explanation.setText('\n\n'.join(d['detail'] for d in details))

    def adjust(self):
        self.accept()
        self.window.navigate(3)

    def view(self):
        current = self.items.currentItem()
        if current:
            ref, item, _ = current.data(Qt.ItemDataRole.UserRole)
            self.accept()
            self.window.navigate(0)
            self.window.clear_search_filters()
            self.window.show_excluded.setChecked(True)
            self.window.search.setText(str(item.get('title', ref)))
            self.window.select(ref)

class Job(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self.fn = fn

    def run(self):
        try:
            self.done.emit(self.fn())
        except Exception as e:
            # Never surface raw HTTP bodies, headers, or credentials.
            text = str(e) if isinstance(e, RuntimeError) else '처리 중 오류가 발생했습니다. 연결과 저장 폴더를 확인하세요.'
            self.failed.emit(text)
        finally:
            self.fn = None

class Connect(QDialog):
    def __init__(self, store, parent):
        super().__init__(parent)
        self.store, self.job = store, None
        self.setWindowTitle('Kaggle Scout · 계정 연결')
        self.setMinimumWidth(580)
        box = QVBoxLayout(self)
        box.setContentsMargins(32, 32, 32, 32)
        box.setSpacing(16)
        box.addWidget(label('01  CONNECT YOUR KAGGLE', 'eyebrow'))
        box.addWidget(label('나의 다음 도전을 연결하세요', 'heading'))
        box.addWidget(label('Kaggle 개인 API 토큰으로 대회를 확인합니다.\nAI 모델 API가 아니며, 유료 AI 서비스를 호출하지 않습니다.', 'muted', True))
        panel, fields = card()
        fields.addWidget(label('Kaggle 개인 API 토큰', 'title'))
        self.token = QLineEdit()
        self.token.setMaxLength(8192)
        self.token.setPlaceholderText('Kaggle 설정에서 생성한 API token')
        self.token.setEchoMode(QLineEdit.EchoMode.Password)
        fields.addWidget(self.token)
        fields.addWidget(button('Kaggle API 설정 열기 ↗', lambda: QDesktopServices.openUrl(QUrl('https://www.kaggle.com/settings/api'))))
        fields.addWidget(button('기존 kaggle.json 파일로 연결', self.import_legacy))
        box.addWidget(panel)
        box.addWidget(label('인증 정보는 Windows 현재 계정으로 암호화하여 이 앱의 data 폴더에 저장합니다.\n다른 PC에서는 다시 연결합니다. 비밀번호나 토큰을 채팅에 보낼 필요가 없습니다.', 'muted', True))
        self.status = label('연결을 확인한 다음 프로필 설정으로 이동합니다.', 'muted', True)
        box.addWidget(self.status)
        self.submit = button('연결 확인하고 시작하기 →', self.connect_token, True)
        box.addWidget(self.submit)
        self.credentials = None
        self.finished.connect(lambda _: self.token.clear())

    def import_legacy(self):
        path, _ = QFileDialog.getOpenFileName(self, 'kaggle.json 선택', '', 'JSON (*.json)')
        if not path:
            return
        try:
            value = validate_credentials(read_json_file(path))
            self.verify(value)
        except (ValueError, OSError, RecursionError):
            self.status.setText('username과 key가 들어 있는 Kaggle 인증 JSON을 선택하세요.')

    def connect_token(self):
        value = self.token.text().strip()
        if not value:
            self.status.setText('개인 API 토큰을 입력하거나 kaggle.json을 선택하세요.')
            return
        self.verify({'token': value})

    def verify(self, credentials):
        if self.job and self.job.isRunning():
            return
        self.submit.setEnabled(False)
        self.status.setText('Kaggle 연결 확인 중…')
        self.job = Job(lambda: Kaggle(credentials).call('ListCompetitions', {'pageSize': 1}), self)
        def success(_):
            try:
                self.store.save_credentials(credentials)
                self.credentials = credentials
                self.token.clear()
                self.accept()
            except RuntimeError as e:
                fail(str(e))
        def fail(text):
            self.status.setText(text)
            self.submit.setEnabled(True)
        self.job.done.connect(success)
        self.job.failed.connect(fail)
        self.job.start()

    def reject(self):
        if self.job and self.job.isRunning():
            self.status.setText('연결 확인이 끝나면 창을 닫을 수 있습니다.')
            return
        super().reject()

class Window(QMainWindow):
    def __init__(self, store, preview=False):
        super().__init__()
        self.store, self.preview = store, preview
        self.credentials = None
        self.job = None
        self.mode = 0
        self.page_index = 0
        self.current_page_refs = []
        self.selected = None
        self.next_due = now()
        self.quitting = False
        self.await_profile = False
        self.setWindowTitle('Kaggle Scout' + (' · 디자인 미리보기 / 가상 데이터' if preview else ''))
        self.setMinimumSize(960, 680)
        self.resize(1140, 780)
        self.setWindowIcon(QIcon(str(ASSETS / 'scout.ico')))
        shell = QWidget()
        self.setCentralWidget(shell)
        root = QHBoxLayout(shell)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        sidebar = QWidget()
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(180)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(16, 24, 16, 20)
        side.setSpacing(10)
        mark = QLabel()
        mark.setPixmap(QIcon(str(ASSETS / 'scout.ico')).pixmap(38, 38))
        side.addWidget(mark)
        side.addWidget(label('Kaggle Scout', 'title'))
        side.addSpacing(16)
        self.nav = []
        for i, text in enumerate(['◈   대회 탐색', '☆   관심 대회', '◷   알림 기록', '⚙   나의 설정']):
            b = button(text, lambda checked=False, index=i: self.navigate(index))
            b.setObjectName('nav')
            b.setCheckable(True)
            self.nav.append(b)
            side.addWidget(b)
        side.addStretch()
        self.profile_summary = label('', 'muted', True)
        side.addWidget(self.profile_summary)
        root.addWidget(sidebar)
        self.pages = QStackedWidget()
        root.addWidget(self.pages, 1)
        self.build_discovery()
        self.build_events()
        self.build_settings()
        self.setup_tray()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(15000)
        self.navigate(0)
        if not preview:
            QTimer.singleShot(350, self.startup)

    def setup_tray(self):
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        self.tray.setToolTip('Kaggle Scout · 대회 모니터')
        menu = QMenu()
        menu.addAction('Kaggle Scout 열기', self.show_app)
        menu.addAction('지금 확인', self.refresh)
        menu.addSeparator()
        menu.addAction('완전히 종료', self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.show_app() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray.messageClicked.connect(self.show_app)
        if QSystemTrayIcon.isSystemTrayAvailable() and not self.preview:
            self.tray.show()

    def show_app(self):
        if hasattr(self, 'notice_ref') and self.notice_ref:
            ref = self.notice_ref
            self.navigate(0)
            self.select(ref)
            self.notice_ref = None
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        if not self.quitting and self.tray.isVisible():
            self.hide()
            event.ignore()
            if not self.store.get('tray_explained'):
                self.tray.showMessage('Kaggle Scout', '트레이에서 계속 확인합니다. 트레이 메뉴에서 완전히 종료할 수 있습니다.')
                self.store.set('tray_explained', True)
        elif self.job and self.job.isRunning():
            event.ignore()
            self.status.setText('현재 요청을 마친 뒤 종료할 수 있습니다.')
            self.quitting = False
        else:
            self.timer.stop()
            self.settings_preview_timer.stop()
            event.accept()

    def quit_app(self):
        self.quitting = True
        if self.close():
            self.tray.hide()
            QApplication.quit()

    def startup(self):
        try:
            self.credentials = self.store.credentials()
        except RuntimeError:
            self.credentials = None
        if not self.credentials:
            self.connect_account(first=True)
        else:
            self.refresh()

    def connect_account(self, first=False):
        dlg = Connect(self.store, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.credentials = dlg.credentials
            self.connection_label.setText('Kaggle 연결됨 · Windows 암호화 저장')
            if first:
                self.await_profile = True
                self.navigate(3)
                self.status.setText('기본 프로필을 확인하고 저장하면 첫 수집을 시작합니다.')
                self.settings_status.setText('프로필을 확인한 뒤 저장하면 첫 수집을 시작합니다.')
            else:
                self.refresh()
        elif not self.credentials:
            self.status.setText('연결 대기 · 나의 설정에서 Kaggle을 연결하세요.')
        dlg.deleteLater()

    def navigate(self, index):
        self.mode = index
        self.page_index = 0
        for i, b in enumerate(self.nav):
            b.setChecked(i == index)
        self.pages.setCurrentIndex(0 if index <= 1 else index - 1)
        if index <= 1:
            self.heading.setText('관심 대회' if index == 1 else '대회 탐색')
            self.render()
        elif index == 2:
            self.render_events()

    def build_discovery(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(22, 22, 22, 16)
        layout.setSpacing(12)
        top = QHBoxLayout()
        titlebox = QVBoxLayout()
        self.heading = label('대회 탐색', 'heading')
        titlebox.addWidget(self.heading)
        top.addLayout(titlebox)
        top.addStretch()
        self.refresh_button = button('↻  지금 확인', self.refresh, True)
        top.addWidget(self.refresh_button)
        layout.addLayout(top)
        self.hero_text = label('', 'muted', True)
        layout.addWidget(self.hero_text)
        self.stats = label('', 'muted')
        layout.addWidget(self.stats)
        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.setPlaceholderText('대회명, 주제, 설명 검색…')
        self.search.textChanged.connect(self.reset_page)
        filters.addWidget(self.search, 1)
        self.topic = QComboBox()
        self.topic.addItems(['모든 분야'] + list(TOPICS))
        self.topic.currentTextChanged.connect(self.reset_page)
        filters.addWidget(self.topic)
        self.sort = QComboBox()
        self.sort.addItems(['추천 순', '마감 임박 순', '최근 발견 순'])
        self.sort.currentTextChanged.connect(self.reset_page)
        filters.addWidget(self.sort)
        layout.addLayout(filters)
        switches = QHBoxLayout()
        self.show_excluded = QCheckBox('제외·마감 대회 표시')
        self.show_hidden = QCheckBox('숨긴 대회 표시')
        self.show_excluded.toggled.connect(self.reset_page)
        self.show_hidden.toggled.connect(self.reset_page)
        switches.addWidget(self.show_excluded)
        switches.addWidget(self.show_hidden)
        switches.addStretch()
        self.exclusion_button = button('제외 이유', self.show_exclusion_dialog)
        switches.addWidget(self.exclusion_button)
        layout.addLayout(switches)
        split = QSplitter(Qt.Orientation.Horizontal)
        scroll = QScrollArea()
        self.list_scroll = scroll
        scroll.setWidgetResizable(True)
        contents = QWidget()
        self.cards = QVBoxLayout(contents)
        self.cards.setContentsMargins(0, 0, 8, 0)
        self.cards.setSpacing(12)
        scroll.setWidget(contents)
        split.addWidget(scroll)
        detail, d = card()
        detail.setMinimumWidth(290)
        d.setContentsMargins(16, 16, 16, 16)
        d.addWidget(label('대회 정보', 'title'))
        self.detail = SafeTextBrowser()
        self.detail.document().setDefaultStyleSheet('body {font-family: Pretendard; font-size:14px; color:#23364b;} h2 {font-size:21px; font-weight:600; margin-bottom:16px;} h3 {font-size:16px; font-weight:600; margin-top:22px;} p {line-height:145%; margin-bottom:12px;}')
        self.detail.setMinimumHeight(140)
        self.detail.setOpenExternalLinks(False)
        d.addWidget(self.detail, 1)
        actions = QHBoxLayout()
        self.star_button = button('☆ 관심', self.star)
        self.hide_button = button('숨기기', self.hide_item)
        actions.addWidget(self.star_button)
        actions.addWidget(self.hide_button)
        d.addLayout(actions)
        self.rules_button = button('참가 규칙 확인', self.load_pages)
        self.original_button = button('Kaggle 원문 열기 ↗', self.open_selected, True)
        d.addWidget(self.rules_button)
        d.addWidget(self.original_button)
        split.addWidget(detail)
        split.setSizes([600, 370])
        layout.addWidget(split, 1)
        paging = QHBoxLayout()
        self.page_label = label('1 / 1 페이지', 'muted')
        paging.addWidget(self.page_label)
        paging.addStretch()
        self.display_size = QComboBox()
        for size in (5, 10, 20, 50):
            self.display_size.addItem(f'페이지당 {size}개', size)
        self.display_size.setCurrentIndex(self.display_size.findData(self.store.profile()['page_size']))
        self.display_size.currentIndexChanged.connect(self.change_page_size)
        paging.addWidget(self.display_size)
        self.previous_page = button('← 이전', lambda: self.move_page(-1))
        self.next_page = button('다음 →', lambda: self.move_page(1))
        paging.addWidget(self.previous_page)
        paging.addWidget(self.next_page)
        layout.addLayout(paging)
        self.status = label('Kaggle 연결 대기', 'muted', True)
        layout.addWidget(self.status)
        self.pages.addWidget(page)

    def reset_page(self, *_):
        self.page_index = 0
        self.render()

    def move_page(self, delta):
        self.page_index += delta
        self.render()
        self.list_scroll.verticalScrollBar().setValue(0)

    def change_page_size(self, *_):
        size = self.display_size.currentData()
        profile = self.store.profile()
        profile['page_size'] = size
        self.store.set('profile', profile)
        if hasattr(self, 'page_size_input'):
            self.page_size_input.setCurrentIndex(self.page_size_input.findData(size))
        self.reset_page()

    def clear_search_filters(self):
        for w in (self.search, self.topic, self.sort, self.show_excluded, self.show_hidden):
            w.blockSignals(True)
        self.search.clear()
        self.topic.setCurrentIndex(0)
        self.sort.setCurrentIndex(0)
        self.show_excluded.setChecked(False)
        self.show_hidden.setChecked(False)
        for w in (self.search, self.topic, self.sort, self.show_excluded, self.show_hidden):
            w.blockSignals(False)
        self.reset_page()

    def render(self, *_):
        if not hasattr(self, 'cards'):
            return
        profile = self.store.profile()
        self.profile_summary.setText(f"{profile['name']}\n{profile['gpu']} · {profile['vram']}GB")
        self.hero_text.setText(f"관심 분야 {len(profile['topics'])}개 · {profile['interval']}분마다 확인")
        rows = self.store.rows()
        excluded_count = sum(bool(exclusion_details(json.loads(r['body']), profile)) for r in rows if not r['hidden'])
        self.exclusion_button.setText(f'제외 이유 ({excluded_count})')
        results = []
        query = self.search.text().lower().strip()
        for row in rows:
            item = json.loads(row['body'])
            verdict = assess(item, profile)
            details = exclusion_details(item, profile, verdict)
            row['exclusions'] = details
            row['item'], row['verdict'] = item, verdict
            if self.mode == 1 and not row['starred']:
                continue
            if row['hidden'] and not self.show_hidden.isChecked():
                continue
            if details and not self.show_excluded.isChecked():
                continue
            if query and query not in plain(json.dumps(item, ensure_ascii=False)).lower():
                continue
            if self.topic.currentIndex() and self.topic.currentText() not in verdict['topics']:
                continue
            results.append(row)
        if self.sort.currentIndex() == 1:
            results.sort(key=lambda r: date(r['item'].get('deadline')) or now() + timedelta(days=99999))
        elif self.sort.currentIndex() == 2:
            results.sort(key=lambda r: r['first_seen'], reverse=True)
        else:
            results.sort(key=lambda r: (-r['verdict']['score'], r['item'].get('deadline', '9999')))
        self.stats.setText(f"표시 {len(results)}개    /    저장된 대회 {len(rows)}개    /    관심 {sum(r['starred'] for r in rows)}개" + ('    ·    가상 데이터 미리보기' if self.preview else ''))
        size = profile['page_size']
        count = len(results)
        page_count = max(1, (count + size - 1) // size)
        self.page_index = max(0, min(self.page_index, page_count - 1))
        start = self.page_index * size
        results = results[start:start + size]
        self.current_page_refs = [r['ref'] for r in results]
        self.page_label.setText(f'{self.page_index + 1} / {page_count} 페이지  ·  {start + 1 if count else 0}–{start + len(results)} / {count}개')
        self.previous_page.setEnabled(self.page_index > 0)
        self.next_page.setEnabled(self.page_index + 1 < page_count)
        clear(self.cards)
        if not results:
            panel, p = card()
            if rows and (query or self.topic.currentIndex()):
                title, text, action, fn = '검색 결과가 없습니다', '검색어나 분야를 바꿔보세요.', '검색 조건 초기화', self.clear_search_filters
            elif self.mode == 1 and not any(r['starred'] for r in rows):
                title, text, action, fn = '관심 대회를 담아보세요', '대회 상세에서 관심 버튼을 누르면 여기에 모입니다.', '대회 탐색', lambda: self.navigate(0)
            elif rows:
                title, text, action, fn = '현재 조건에 맞는 대회가 없습니다', '참가 대상이나 추천 점수 조건을 조정해보세요.', '추천 조건 조정', lambda: self.navigate(3)
            elif self.credentials:
                title, text, action, fn = '대회를 확인해보세요', '지금 확인을 누르면 최신 목록을 가져옵니다.', '지금 확인', self.refresh
            else:
                title, text, action, fn = 'Kaggle을 연결해 주세요', '계정을 연결하면 관심 분야에 맞는 대회를 모아드립니다.', '계정 연결', self.connect_account
            self.empty_title = title
            p.addWidget(label(title, 'title'))
            p.addWidget(label(text, 'muted', True))
            p.addWidget(button(action, fn))
            self.cards.addWidget(panel)
        for row in results:
            item, v = row['item'], row['verdict']
            panel, p = card()
            panel.setMinimumHeight(190)
            p.setContentsMargins(18, 16, 18, 16)
            p.setSpacing(8)
            p.addWidget(label(('★  ' if row['starred'] else '') + item.get('title', row['ref']), 'title', True))
            p.addWidget(label('  ·  '.join(v['topics']) or '분야 미분류', 'eyebrow', True))
            desc = plain(item.get('description', ''))
            p.addWidget(label(desc[:110] + ('…' if len(desc) > 110 else ''), 'muted', True))
            p.addWidget(label('제출 마감  ' + display_date(item.get('deadline')), 'muted'))
            line = QHBoxLayout()
            line.addWidget(label(item.get('reward') or '보상 미정', 'muted'))
            line.addStretch()
            line.addWidget(button('자세히 →', lambda checked=False, ref=row['ref']: self.select(ref)))
            p.addLayout(line)
            if row['exclusions']:
                p.addWidget(label('제외: ' + ' · '.join(dict.fromkeys(d['label'] for d in row['exclusions'])), 'muted', True))
            self.cards.addWidget(panel)
        self.cards.addStretch()
        visible = {r['ref'] for r in results}
        if self.selected not in visible:
            self.selected = results[0]['ref'] if results else None
        self.select(self.selected)

    def selected_row(self):
        return next((r for r in self.store.rows() if r['ref'] == self.selected), None)

    def show_exclusion_dialog(self):
        dialog = ExclusionDialog(self)
        dialog.exec()
        dialog.deleteLater()

    def select(self, ref):
        self.selected = ref
        row = self.selected_row()
        for b in (self.star_button, self.hide_button, self.rules_button, self.original_button):
            b.setEnabled(row is not None)
        if not row:
            self.star_button.setText('☆ 관심')
            self.hide_button.setText('숨기기')
            self.detail.setHtml('<h2>대회 상세 정보</h2><p>대회를 선택하면 일정과 추천 이유를 확인할 수 있습니다.</p>')
            return
        self.star_button.setText('★ 관심 해제' if row['starred'] else '☆ 관심')
        self.hide_button.setText('숨김 해제' if row['hidden'] else '숨기기')
        item = json.loads(row['body'])
        v = assess(item, self.store.profile())
        esc = lambda x: html.escape(str(x or '확인 필요'))
        pairs = [('시작', display_date(item.get('enabledDate'))),
                 ('신규 참가 마감', display_date(item.get('newEntrantDeadline'))),
                 ('팀 구성 마감', display_date(item.get('mergerDeadline'))),
                 ('최종 제출 마감', display_date(item.get('deadline'))),
                 ('평가 지표', item.get('evaluationMetric')),
                 ('제출 방식', 'Kaggle Notebook 코드 제출' if item.get('isKernelsSubmissionsOnly') else '목록 API에 코드 전용 제한 없음 · 규칙 확인'),
                 ('최대 팀 인원', item.get('maxTeamSize')), ('보상', item.get('reward')),
                 ('참여 팀', item.get('teamCount')), ('마지막 확인', display_date(row['last_seen']))]
        body = '<h2>' + esc(item.get('title')) + '</h2><p>' + esc(plain(item.get('description'))) + '</p>'
        body += '<h3>일정과 주요 정보</h3>' + ''.join(f'<p><b>{k}</b><br>{esc(value)}</p>' for k, value in pairs)
        body += '<h3>추천 이유</h3><p>' + '<br>'.join(esc(x) for x in v['reasons']) + '</p>'
        body += '<h3>내 환경에서 확인할 사항</h3><p>' + '<br><br>'.join(esc(v[k]) for k in ('eligibility', 'gpu', 'api')) + '</p>'
        details = exclusion_details(item, self.store.profile(), v)
        if details:
            body += '<h3>현재 제외 이유</h3><p>' + '<br><br>'.join(esc(d['detail']).replace('\n', '<br>') for d in details) + '</p>'
        if item.get('pages'):
            body += '<h3>추가 조회한 원문</h3><p>' + esc(plain(item['pages'])).replace('\n', '<br>') + '</p>'
        body += '<p style="color:#6c7d90">설명·규칙이 변경될 수 있습니다. 확정되지 않은 조건은 확인 필요로 표시합니다.</p>'
        self.detail.setHtml(body)

    def star(self):
        row = self.selected_row()
        if row:
            self.store.flag(row['ref'], 'starred', not row['starred'])
            self.render()

    def hide_item(self):
        row = self.selected_row()
        if row:
            self.store.flag(row['ref'], 'hidden', not row['hidden'])
            self.render()

    def open_selected(self):
        if self.selected:
            ref = slug({'ref': self.selected})
            QDesktopServices.openUrl(QUrl('https://www.kaggle.com/competitions/' + ref))

    def busy(self):
        return self.job and self.job.isRunning()

    def refresh(self):
        if self.preview:
            self.status.setText('디자인 미리보기: 네트워크 수집은 실행하지 않습니다.')
            return
        if self.busy():
            return
        if not self.credentials:
            self.connect_account()
            return
        self.refresh_button.setEnabled(False)
        self.status.setText('Kaggle 대회 목록을 확인하고 있습니다…')
        profile = copy.deepcopy(self.store.profile())
        def task():
            items = Kaggle(self.credentials).collect()
            # Preserve previously fetched rules when the list API omits them.
            previous = {r['ref']: json.loads(r['body']) for r in self.store.rows()}
            for item in items:
                old = previous.get(slug(item), {})
                if old.get('pages'):
                    item['pages'] = old['pages']
            first, notices = self.store.sync(items, profile)
            self.store.set('last_success', now().isoformat())
            self.store.set('last_error', '')
            return len(items), first, notices
        self.job = Job(task, self)
        self.job.done.connect(self.refreshed)
        self.job.failed.connect(self.failed)
        self.job.start()

    def refreshed(self, result):
        count, first, notices = result
        self.refresh_button.setEnabled(True)
        self.next_due = now() + timedelta(minutes=self.store.profile()['interval'])
        self.status.setText(f"최근 확인 {display_date(self.store.get('last_success'))} · {count}개")
        self.status.setToolTip('다음 확인: ' + display_date(self.next_due.isoformat()))
        self.render()
        if first:
            self.notify('첫 수집 완료', f'{count}개 대회를 확인했습니다. 추천 목록에서 관심 대회를 선택하세요.')
        elif notices:
            kind, title, ref = notices[0]
            self.notice_ref = ref
            row = next((r for r in self.store.rows() if r['ref'] == ref), None)
            extra = ''
            if row:
                item = json.loads(row['body'])
                verdict = assess(item, self.store.profile())
                extra = '\n제출 ' + display_date(item.get('deadline')) + '\n' + ' / '.join(verdict['reasons'][:2])
            self.notify(f'{kind} · {len(notices)}건', title + extra + ('\n전체 정보는 알림 기록에서 확인하세요.' if len(notices) > 1 else ''))

    def failed(self, text):
        self.refresh_button.setEnabled(True)
        self.next_due = now() + timedelta(minutes=self.store.profile()['interval'])
        self.store.set('last_error', text)
        self.status.setText(text + ' · 마지막 성공: ' + display_date(self.store.get('last_success')))

    def notify(self, title, text):
        if self.store.profile()['notify'] and self.tray.isVisible():
            self.tray.showMessage('Kaggle Scout · ' + title, text[:240], QSystemTrayIcon.MessageIcon.Information, 10000)

    def tick(self):
        if self.credentials and not self.await_profile and not self.preview and now() >= self.next_due:
            self.refresh()

    def load_pages(self):
        if not self.selected or self.busy() or self.preview:
            return
        if not self.credentials:
            self.connect_account()
            return
        ref = self.selected
        self.status.setText('설명·규칙을 추가 조회합니다. 대회 권한에 따라 제공되지 않을 수 있습니다…')
        self.job = Job(lambda: Kaggle(self.credentials).pages(ref), self)
        def done(pages):
            rows = self.store.rows()
            row = next((r for r in rows if r['ref'] == ref), None)
            if row:
                item = json.loads(row['body'])
                item['pages'] = '\n\n'.join(str(p.get('name', '')) + '\n' + str(p.get('content', '')) for p in pages)
                self.store.sync([item], self.store.profile())
            self.status.setText('추가 조회 완료' if pages else '추가 설명을 제공받지 못했습니다. Kaggle 원문에서 확인하세요.')
            self.render()
        self.job.done.connect(done)
        self.job.failed.connect(self.failed)
        self.job.start()

    def build_events(self):
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(32, 32, 32, 32)
        box.addWidget(label('알림 기록', 'heading'))
        box.addWidget(label('새 추천 · 관심 대회 정보 변경 · 마감 7일 / 3일 / 1일 전', 'muted'))
        self.events = SafeTextBrowser()
        self.events.document().setDefaultStyleSheet('body {font-family:Pretendard; font-size:14px;} h3 {font-size:17px; font-weight:600;}')
        box.addWidget(self.events)
        self.pages.addWidget(page)

    def render_events(self):
        with self.store.connect() as con:
            rows = con.execute('SELECT * FROM events ORDER BY id DESC LIMIT 300').fetchall()
        self.events.setHtml(''.join('<h3>' + html.escape(r['kind']) + '</h3><p>' + html.escape(r['message']) + '</p><p style="color:#6c7d90">' + display_date(r['created']) + '</p><hr>' for r in rows) or '<h3>아직 알림이 없습니다.</h3><p>첫 수집은 목록으로 보여주고, 이후 새 추천과 관심 대회 변경 사항을 기록합니다.</p>')

    def build_settings(self):
        scroll = QScrollArea()
        self.settings_scroll = scroll
        scroll.setWidgetResizable(True)
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(32, 28, 32, 28)
        box.setSpacing(18)
        box.addWidget(label('나의 설정', 'heading'))
        connection, c = card()
        c.addWidget(label('Kaggle 계정', 'title'))
        self.connection_label = label('저장된 연결 있음' if self.store.get('credentials') else '아직 연결되지 않았습니다.', 'muted')
        c.addWidget(self.connection_label)
        c.addWidget(button('계정 연결 / 다시 연결', self.connect_account))
        c.addWidget(button('연결 해제', self.disconnect_account))
        box.addWidget(connection)
        interests, i = card()
        i.addWidget(label('관심 분야', 'title'))
        grid = QGridLayout()
        p = self.store.profile()
        self.topic_checks = {}
        for n, name in enumerate(TOPICS):
            chk = QCheckBox(name)
            chk.setChecked(name in p['topics'])
            self.topic_checks[name] = chk
            grid.addWidget(chk, n // 2, n % 2)
        i.addLayout(grid)
        box.addWidget(interests)
        participation, pa = card()
        pa.addWidget(label('참가 대상', 'title'))
        self.audience_checks = {}
        audience_grid = QGridLayout()
        for n, (key, text) in enumerate(AUDIENCES.items()):
            chk = QCheckBox(text)
            chk.setChecked(key in p['audiences'])
            self.audience_checks[key] = chk
            audience_grid.addWidget(chk, n // 2, n % 2)
        pa.addLayout(audience_grid)
        self.unknown_audience = QCheckBox('참가 조건이 공개되지 않은 대회도 포함')
        self.unknown_audience.setChecked(p['include_unknown_audience'])
        pa.addWidget(self.unknown_audience)
        pa.addWidget(label('대회 설명의 명시적 문구로 구분하며, 최종 참가 자격은 원문에서 확인합니다.', 'muted', True))
        box.addWidget(participation)
        hardware, h = card()
        h.addWidget(label('사용 가능한 환경', 'title'))
        fields = QGridLayout()
        self.name_input = QLineEdit(p['name'])
        self.name_input.setMaxLength(100)
        self.skills_input = QLineEdit(p['skills'])
        self.skills_input.setMaxLength(250)
        self.gpu_input = QLineEdit(p['gpu'])
        self.gpu_input.setMaxLength(120)
        self.vram_input = SliderInput('GPU VRAM', 0, 512, p['vram'], ' GB', slider_max=64,
                                     presets=[(8, '8GB'), (16, '16GB'), (24, '24GB'), (32, '32GB')],
                                     low_label='GPU 없음', high_label='64GB · 더 큰 용량은 직접 입력')
        for n, (name, widget) in enumerate([('프로필 이름', self.name_input), ('보유 기술', self.skills_input), ('GPU 이름 (없으면 없음)', self.gpu_input), ('GPU VRAM', self.vram_input)]):
            fields.addWidget(label(name, 'muted'), n, 0)
            fields.addWidget(widget, n, 1)
        h.addLayout(fields)
        self.paid = QCheckBox('유료 API를 사용하는 대회도 허용')
        self.paid.setChecked(p['paid_api'])
        h.addWidget(self.paid)
        h.addWidget(label('자원 요구량이 공개되지 않은 대회는 상세 화면에 확인 필요로 표시합니다.', 'muted', True))
        box.addWidget(hardware)
        filters, f = card()
        f.addWidget(label('제외 조건과 알림', 'title'))
        self.offline = QCheckBox('오프라인 참석 필수 문구가 감지된 대회 제외')
        self.offline.setChecked(p['exclude_offline'])
        self.notifications = QCheckBox('PC 알림 받기 (관심 대회 마감 알림 포함)')
        self.notifications.setChecked(p['notify'])
        self.autostart = QCheckBox('Windows 로그인 시 트레이로 자동 시작')
        self.autostart.setChecked(self.autostart_enabled())
        for chk in [self.offline, self.notifications, self.autostart]:
            f.addWidget(chk)
        self.keywords = QLineEdit(', '.join(p['exclude_keywords']))
        self.keywords.setPlaceholderText('추가 제외 키워드, 쉼표로 구분')
        f.addWidget(self.keywords)
        f.addWidget(label('확인 주기', 'muted'))
        self.interval = SliderInput('확인 주기', 15, 1440, p['interval'], ' 분',
                                    stops=[15, 30, 60, 120, 180, 360, 720, 1440],
                                    low_label='15분', high_label='하루',
                                    presets=[(30, '30분'), (60, '1시간'), (180, '3시간'), (360, '6시간')])
        f.addWidget(self.interval)
        f.addWidget(label('추천 범위', 'muted'))
        self.threshold = SliderInput('최소 탐색 점수', 0, 100, p['min_score'], ' 점',
                                     low_label='폭넓게 보기', high_label='관심 분야 중심')
        f.addWidget(self.threshold)
        page_row = QHBoxLayout()
        page_row.addWidget(label('페이지당 표시 개수', 'muted'))
        self.page_size_input = QComboBox()
        for size in (5, 10, 20, 50):
            self.page_size_input.addItem(f'{size}개', size)
        self.page_size_input.setCurrentIndex(self.page_size_input.findData(p['page_size']))
        page_row.addWidget(self.page_size_input)
        page_row.addStretch()
        f.addLayout(page_row)
        f.addWidget(label('PC와 앱이 실행 중일 때 확인합니다.', 'muted'))
        box.addWidget(filters)
        scroll.setWidget(page)
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(scroll, 1)
        footer = QWidget()
        footer.setObjectName('settingsFooter')
        bottom = QHBoxLayout(footer)
        bottom.setContentsMargins(22, 12, 22, 12)
        self.settings_status = label('저장된 설정입니다.', 'muted', True)
        bottom.addWidget(self.settings_status, 1)
        bottom.addWidget(button('내보내기', self.export_profile))
        bottom.addWidget(button('가져오기', self.import_profile))
        bottom.addWidget(button('설정 저장', self.save_settings, True))
        outer.addWidget(footer)
        self.pages.addWidget(container)
        self.settings_preview_timer = QTimer(self)
        self.settings_preview_timer.setSingleShot(True)
        self.settings_preview_timer.timeout.connect(self.preview_settings)
        for edit in (self.name_input, self.skills_input, self.gpu_input, self.keywords):
            edit.textChanged.connect(self.queue_settings_preview)
        for control in (self.vram_input, self.interval, self.threshold):
            control.valueChanged.connect(self.queue_settings_preview)
        for check in [*self.topic_checks.values(), *self.audience_checks.values(), self.unknown_audience,
                      self.paid, self.offline, self.notifications, self.autostart]:
            check.toggled.connect(self.queue_settings_preview)
        self.page_size_input.currentIndexChanged.connect(self.queue_settings_preview)

    def queue_settings_preview(self, *_):
        self.settings_preview_timer.start(150)

    def preview_settings(self):
        try:
            p = self.read_form()
        except ValueError:
            self.settings_status.setText('입력값을 확인해 주세요.')
            return
        rows = [r for r in self.store.rows() if not r['hidden']]
        candidates = sum(not (v := assess(json.loads(r['body']), p))['excluded'] and v['score'] >= p['min_score'] for r in rows)
        changed = p != self.store.profile() or self.autostart.isChecked() != self.autostart_enabled()
        self.settings_status.setText(('저장 전' if changed else '저장됨') + (f' · 현재 목록에서 추천 후보 {candidates}개' if rows else ' · 수집 후 추천 후보를 확인할 수 있습니다.'))

    def read_form(self):
        p = self.store.profile()
        p.update(name=self.name_input.text().strip() or '나의 프로필',
                 skills=self.skills_input.text().strip(), gpu=self.gpu_input.text().strip() or '없음',
                 vram=self.vram_input.value(), paid_api=self.paid.isChecked(),
                 topics=[k for k, c in self.topic_checks.items() if c.isChecked()],
                 audiences=[k for k, chk in self.audience_checks.items() if chk.isChecked()],
                 include_unknown_audience=self.unknown_audience.isChecked(),
                 exclude_students=not any(self.audience_checks[k].isChecked() for k in ('university', 'youth', 'student')),
                 exclude_offline=self.offline.isChecked(),
                 notify=self.notifications.isChecked(), interval=self.interval.value(),
                 min_score=self.threshold.value(),
                 page_size=self.page_size_input.currentData(),
                 exclude_keywords=[k.strip() for k in self.keywords.text().split(',') if k.strip()])
        return validate_profile(p)

    def disconnect_account(self):
        if self.busy():
            self.connection_label.setText('현재 조회가 끝난 뒤 연결을 해제할 수 있습니다.')
            return
        answer = QMessageBox.question(self, 'Kaggle 연결 해제', '이 PC에 저장한 인증 정보를 삭제할까요?\n관심 대회와 수집 기록은 유지됩니다.', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.store.clear_credentials()
        self.credentials = None
        self.connection_label.setText('연결이 해제되었습니다.')
        self.status.setText('Kaggle 연결 대기')

    def autostart_enabled(self):
        if os.name != 'nt':
            return False
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
                winreg.QueryValueEx(key, 'KaggleScout')
            return True
        except OSError:
            return False

    def save_settings(self):
        try:
            p = self.read_form()
        except ValueError:
            self.settings_status.setText('입력값을 확인하세요. 제외 키워드는 50개 이하, 각 80자 이하입니다.')
            return
        start_first_collection = self.await_profile and self.credentials is not None
        self.settings_preview_timer.stop()
        self.store.set('profile', p)
        self.display_size.blockSignals(True)
        self.display_size.setCurrentIndex(self.display_size.findData(p['page_size']))
        self.display_size.blockSignals(False)
        self.await_profile = False
        self.next_due = now() + timedelta(minutes=p['interval'])
        if os.name == 'nt' and not self.preview:
            import winreg
            try:
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
                    if self.autostart.isChecked():
                        command = f'"{sys.executable}" --background' if getattr(sys, 'frozen', False) else f'"{sys.executable}" "{Path(__file__)}" --background'
                        winreg.SetValueEx(key, 'KaggleScout', 0, winreg.REG_SZ, command)
                    else:
                        try:
                            winreg.DeleteValue(key, 'KaggleScout')
                        except FileNotFoundError:
                            pass
            except OSError:
                self.settings_status.setText('프로필은 저장했지만 자동 시작 등록에 실패했습니다.')
                return
        self.settings_status.setText('설정을 저장했습니다. 추천 목록에 적용되었습니다.')
        self.render()
        if start_first_collection:
            self.navigate(0)
            self.refresh()

    def export_profile(self):
        path, _ = QFileDialog.getSaveFileName(self, '개인 프로필 내보내기', 'scout-profile.json', 'JSON (*.json)')
        if path:
            try:
                Path(path).write_text(json.dumps(self.read_form(), indent=2, ensure_ascii=False), encoding='utf8')
                self.settings_status.setText('프로필을 내보냈습니다. 인증 정보는 포함되지 않습니다.')
            except (OSError, ValueError):
                self.settings_status.setText('프로필 파일을 저장하지 못했습니다.')

    def import_profile(self):
        path, _ = QFileDialog.getOpenFileName(self, '개인 프로필 가져오기', '', 'JSON (*.json)')
        if not path:
            return
        try:
            p = validate_profile(read_json_file(path))
            self.name_input.setText(p['name'])
            self.skills_input.setText(p['skills'])
            self.gpu_input.setText(p['gpu'])
            self.vram_input.setValue(p['vram'])
            self.paid.setChecked(p['paid_api'])
            for key, chk in self.audience_checks.items():
                chk.setChecked(key in p['audiences'])
            self.unknown_audience.setChecked(p['include_unknown_audience'])
            self.offline.setChecked(p['exclude_offline'])
            self.notifications.setChecked(p['notify'])
            self.interval.setValue(p['interval'])
            self.threshold.setValue(p['min_score'])
            self.page_size_input.setCurrentIndex(self.page_size_input.findData(p['page_size']))
            self.keywords.setText(', '.join(p['exclude_keywords']))
            for name, chk in self.topic_checks.items():
                chk.setChecked(name in p['topics'])
            self.settings_status.setText('프로필을 불러왔습니다. 설정 저장을 눌러 적용하세요.')
        except (ValueError, OSError, TypeError, RecursionError):
            self.settings_status.setText('지원하는 프로필 JSON 파일이 아닙니다.')

def main():
    if '--migrate-from' in sys.argv:
        try:
            index = sys.argv.index('--migrate-from')
            source = Path(sys.argv[index + 1])
            migrate_database(source, data_directory(ROOT, frozen=True))
            return 0
        except Exception:
            return 1
    app = QApplication(sys.argv)
    app.setApplicationName('Kaggle Scout')
    app.setOrganizationName('PersonalTools')
    for font in ASSETS.glob('Pretendard-*.otf'):
        QFontDatabase.addApplicationFont(str(font))
    font = QFont('Pretendard', 11)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)
    app.setStyleSheet(STYLE)
    preview = '--preview' in sys.argv
    folder = data_directory(ROOT, frozen=getattr(sys, 'frozen', False),
                            portable='--portable' in sys.argv, preview=preview)
    folder.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(folder / 'app.lock'))
    lock.setStaleLockTime(30000)
    if not lock.tryLock(100):
        QMessageBox.information(None, 'Kaggle Scout', '이미 실행 중입니다. 작업 표시줄의 트레이 아이콘을 확인하세요.')
        return 0
    store = Store(folder)
    window = Window(store, preview)
    if '--background' not in sys.argv or not store.get('credentials') or not window.tray.isVisible():
        window.show()
    app.setQuitOnLastWindowClosed(False)
    if '--smoke' in sys.argv:
        def smoke():
            (ROOT / 'work').mkdir(exist_ok=True)
            window.grab().save(str(ROOT / 'work' / 'app-smoke.png'))
            window.quitting = True
            window.close()
            app.quit()
        QTimer.singleShot(1500, smoke)
    return app.exec()

if __name__ == '__main__':
    sys.exit(main())
