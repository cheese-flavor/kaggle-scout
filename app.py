import copy
import json
import os
from pathlib import Path
import sys
from datetime import timedelta
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QLockFile, QUrl, QTime, QSize, QSignalBlocker
from PySide6.QtGui import QIcon, QDesktopServices, QAction, QKeyEvent, QTextOption
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QFrame, QLabel,
    QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout, QStackedWidget, QScrollArea,
    QLineEdit, QComboBox, QSpinBox, QCheckBox, QTextBrowser, QMessageBox, QDialog,
    QFileDialog, QSystemTrayIcon, QMenu, QSplitter, QSlider, QListWidget, QListWidgetItem, QTimeEdit, QToolButton, QTabWidget, QTabBar, QWidgetAction, QSizePolicy)
from core import Store, Kaggle, DEFAULT, TOPICS, AUDIENCES, validate_profile, read_json_file, validate_credentials, assess, now, date, display_date, plain, slug
from installation import data_directory, migrate_database
from core import exclusion_details, EXCLUSION_LABELS, NOTIFY_KINDS, KST, trash_cutoff

ROOT = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
ASSETS = Path(getattr(sys, '_MEIPASS', ROOT)) / 'assets'
from ui_theme import STYLE, apply_theme, icon, TONES, TOPIC_TONES, NAV_TONES, set_tone
from detail_view import DOCUMENT_STYLE, detail_document
from notification_view import HISTORY_STYLE, history_document

def label(text, kind=None, wrap=False):
    w = QLabel()
    w.setTextFormat(Qt.TextFormat.PlainText)
    w.setText(str(text))
    if kind:
        w.setObjectName(kind)
    w.setWordWrap(wrap)
    return w

def button(text, fn, primary=False, icon_name=None, tone=None):
    mappings = {'Kaggle API 설정 열기 ↗': ('Kaggle API 설정 열기', 'arrow-up-right'), '연결 확인하고 시작하기 →': ('연결하고 시작하기', 'arrow-right'), '↻  지금 확인': ('최신 대회 확인', 'refresh-cw'), '← 이전': ('이전', 'chevron-left'),
                '다음 →': ('다음', 'chevron-right'), '☆ 관심': ('관심 등록', 'bookmark'),
                'Kaggle 원문 열기 ↗': ('대회 살펴보기', 'arrow-right'), '참가 규칙 확인': ('참가 조건 확인', 'layers'),
                '숨기기': ('숨기기', 'eye-off'), '설정 저장': ('설정 저장', 'check'),
                '내보내기': ('내보내기', 'download'), '가져오기': ('가져오기', 'upload'),
                '연결 해제': ('연결 해제', 'log-out'), '계정 연결 / 다시 연결': ('계정 연결', 'shield-check')}
    text, automatic_icon = mappings.get(text, (text, None))
    b = QPushButton(text)
    selected_icon = icon_name or automatic_icon
    if tone is None:
        if selected_icon == 'rotate-ccw':
            tone = 'teal'
        elif selected_icon == 'bookmark-check' or (selected_icon == 'bookmark' and text):
            tone = 'violet'
        elif selected_icon == 'trash' and text in ('', '삭제'):
            tone = 'danger'
    if tone:
        b.setProperty('tone', tone)
    if selected_icon:
        tint = ('#ffffff' if primary else TONES[tone]['ink']) if tone else ('#07324b' if primary else '#637087')
        b.setIcon(icon(selected_icon, tint))
        b.setIconSize(QSize(19, 19))
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

class NounHeading(QLabel):
    """Preserve the functional title while eliding an unusually long display name."""
    def __init__(self):
        super().__init__()
        self.prefix, self.suffix = '', ''
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setObjectName('heading')
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def set_title(self, prefix, suffix=''):
        self.prefix, self.suffix = prefix, suffix
        self.setToolTip(prefix + suffix)
        self.setAccessibleName(prefix + suffix)
        self.update_text()

    def update_text(self):
        available = max(0, self.width() - self.fontMetrics().horizontalAdvance(self.suffix))
        visible = self.fontMetrics().elidedText(self.prefix, Qt.TextElideMode.ElideRight, available)
        self.setText(visible + self.suffix)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_text()


class CompetitionCard(QFrame):
    clicked = Signal()

    def __init__(self, title):
        super().__init__()
        self.setObjectName('competitionCard')
        self.setProperty('selected', False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName('대회 상세 보기: ' + title)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
            event.accept()
        else:
            super().keyPressEvent(event)

def topic_visual(topics):
    order = ['LLM / 생성형 AI', 'NLP', '시계열', '이미지 / 영상', '음성', 'AI 서비스 / 웹 개발', '정형 데이터 / SQL']
    primary = next((name for name in order if name in topics), None)
    tone, glyph = TOPIC_TONES[primary or '정형 데이터 / SQL']
    colors = TONES[tone]
    return primary or '분야 확인', glyph, colors['ink'], colors['surface']


def deadline_tone(value, long_practice=False):
    end = date(value)
    if not end or end <= now():
        return 'slate'
    if long_practice:
        return 'teal'
    days = (end.astimezone(KST).date() - now().astimezone(KST).date()).days
    return 'danger' if days <= 3 else 'amber' if days <= 7 else 'slate'

def icon_tile(name, color, background):
    tile = QLabel()
    tile.setPixmap(icon(name, color, 22).pixmap(22, 22))
    tile.setFixedSize(38, 38)
    tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
    tile.setStyleSheet(f'background:{background}; border-radius:12px;')
    return tile

def deadline_badge(value):
    end = date(value)
    if not end:
        return ''
    if end <= now():
        return '마감'
    days = (end.astimezone(KST).date() - now().astimezone(KST).date()).days
    return '오늘 마감' if days == 0 else f'D-{days}'

class SafeTextBrowser(QTextBrowser):
    def __init__(self):
        super().__init__()
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)

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
        self.setWindowTitle('제외 이유')
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
        self.explanation = SafeTextBrowser()
        self.explanation.setMinimumHeight(90)
        self.explanation.setMaximumHeight(150)
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
            self.explanation.setPlainText('현재 조건으로 제외된 대회가 없습니다.')
        self.view_button.setEnabled(self.items.count() > 0)

    def describe(self, current, previous=None):
        if current:
            _, _, details = current.data(Qt.ItemDataRole.UserRole)
            self.explanation.setPlainText('\n\n'.join(d['detail'] for d in details))

    def adjust(self):
        self.accept()
        self.window.navigate(3)

    def view(self):
        current = self.items.currentItem()
        if current:
            ref, _, _ = current.data(Qt.ItemDataRole.UserRole)
            self.accept()
            self.window.open_competition(ref)

def recovery_label(row):
    until = date(row.get('trash_until'))
    return (until.astimezone(KST) - timedelta(seconds=1)).strftime('%Y.%m.%d %H:%M까지 (KST)') if until else '종료일 미확인 · 일정 확인 전까지 보관'


class TrashDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle('삭제 보관함')
        self.resize(740, 590)
        box = QVBoxLayout(self)
        box.setContentsMargins(24, 24, 24, 24)
        box.setSpacing(14)
        box.addWidget(label('삭제 보관함', 'heading'))
        box.addWidget(label('종료일 전날 23:59까지 복구 가능 · 한국 시간 기준', 'muted', True))
        self.search = QLineEdit()
        self.search.setPlaceholderText('삭제된 대회 검색')
        box.addWidget(self.search)
        self.items = QListWidget()
        self.items.setWordWrap(True)
        box.addWidget(self.items, 1)
        self.explanation = SafeTextBrowser()
        self.explanation.setMaximumHeight(130)
        box.addWidget(self.explanation)
        self.result_label = label('', 'muted', True)
        box.addWidget(self.result_label)
        actions = QHBoxLayout()
        actions.addStretch()
        self.restore_button = button('복구', self.restore_selected, True, icon_name='rotate-ccw')
        actions.addWidget(self.restore_button)
        actions.addWidget(button('닫기', self.accept))
        box.addLayout(actions)
        self.search.textChanged.connect(self.fill)
        self.items.currentItemChanged.connect(self.describe)
        self.fill()

    def fill(self, *_):
        self.items.clear()
        query = self.search.text().strip().lower()
        rows = self.window.store.trash_rows()
        for row in rows:
            item = json.loads(row['body'])
            title = str(item.get('title', row['ref']))
            if query and query not in (title + ' ' + plain(item.get('description'))).lower():
                continue
            entry = QListWidgetItem(title + '\n복구 기한: ' + recovery_label(row))
            entry.setData(Qt.ItemDataRole.UserRole, row)
            self.items.addItem(entry)
        self.restore_button.setEnabled(self.items.count() > 0)
        if self.items.count():
            self.items.setCurrentRow(0)
        else:
            self.explanation.setPlainText('검색 결과가 없습니다.' if rows and query else '삭제된 대회가 없습니다.')

    def describe(self, current, previous=None):
        if current:
            row = current.data(Qt.ItemDataRole.UserRole)
            item = json.loads(row['body'])
            self.explanation.setPlainText(plain(item.get('description')) + '\n\n최종 제출 마감: ' + display_date(item.get('deadline')) + '\n복구 기한: ' + recovery_label(row))

    def restore_selected(self):
        current = self.items.currentItem()
        if not current:
            return
        row = current.data(Qt.ItemDataRole.UserRole)
        restored = self.window.store.restore(row['ref'])
        self.fill()
        self.window.render()
        self.result_label.setText('복구 완료 · 기존 관심 등록 유지' if restored else '복구 기한 경과 · 보관 기록 정리')


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
        box.addWidget(label('Kaggle 계정 연결', 'heading'))
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
        self.list_filters = {}
        self.page_index = 0
        self.current_page_refs = []
        self.selected = None
        self.notice_ref = None
        self.next_due = now()
        self.quitting = False
        self.await_profile = False
        self.setWindowTitle('Kaggle Scout' + (' · 디자인 미리보기 / 가상 데이터' if preview else ''))
        self.setMinimumSize(960, 680)
        self.resize(1180, 820)
        self.setWindowIcon(QIcon(str(ASSETS / 'scout.ico')))
        shell = QWidget()
        self.setCentralWidget(shell)
        root = QHBoxLayout(shell)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        sidebar = QWidget()
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(118)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(16, 30, 16, 20)
        side.setSpacing(14)
        mark = QLabel()
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setPixmap(QIcon(str(ASSETS / 'scout.ico')).pixmap(42, 42))
        side.addWidget(mark)
        brand = label('Kaggle\nScout', 'brand')
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side.addWidget(brand)
        side.addSpacing(18)
        self.nav = []
        self.nav_icons = ['trophy', 'bookmark', 'bell', 'settings-2']
        for i, text in enumerate(['대회', '관심', '알림', '설정']):
            b = QToolButton()
            b.setText(text)
            b.setIcon(icon(self.nav_icons[i], size=25))
            b.setIconSize(QSize(25, 25))
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            b.setFixedSize(84, 80)
            b.setObjectName('nav')
            b.setProperty('tone', NAV_TONES[i])
            b.setCheckable(True)
            b.setAccessibleName(text)
            b.clicked.connect(lambda checked=False, index=i: self.navigate(index))
            self.nav.append(b)
            side.addWidget(b)
        side.addStretch()
        self.profile_summary = label('', 'muted')
        self.profile_summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        menu = QMenu(self)
        menu.setObjectName('trayMenu')
        menu.addAction('앱 열기', self.show_app)
        menu.addAction('종료', self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.show_app() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray.messageClicked.connect(self.open_notice)
        if QSystemTrayIcon.isSystemTrayAvailable() and not self.preview:
            self.tray.show()

    def show_app(self):
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()

    def open_notice(self):
        ref = self.notice_ref
        self.notice_ref = None
        if not ref or not self.open_competition(ref):
            self.navigate(2)
        self.show_app()

    def open_competition(self, ref):
        row = next((row for row in self.store.rows() if row['ref'] == ref), None)
        if row is None:
            return False
        profile = self.store.profile()
        item = json.loads(row['body'])
        verdict = assess(item, profile)
        self.navigate(0)
        self.apply_list_filters(sort=self.sort.currentIndex(),
                                group=int(profile['separate_education'] and verdict['education']),
                                include_excluded=bool(exclusion_details(item, profile, verdict)),
                                include_hidden=bool(row['hidden']))
        self.render(reveal_ref=ref)
        frame = self.card_frames.get(ref)
        if frame is None:
            return False
        self.list_scroll.ensureWidgetVisible(frame)
        return True

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
        self.render()
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
        if self.mode != index:
            if self.mode <= 1:
                self.list_filters[self.mode] = dict(
                    search=self.search.text(), topic=self.topic.currentIndex(),
                    sort=self.sort.currentIndex(), group=self.collection_tabs.currentIndex(),
                    include_excluded=self.show_excluded.isChecked(), include_hidden=self.show_hidden.isChecked())
            if index <= 1:
                self.apply_list_filters(**self.list_filters.get(index, {'group': self.collection_tabs.currentIndex()}))
        self.mode = index
        self.page_index = 0
        for i, b in enumerate(self.nav):
            b.setChecked(i == index)
            b.setIcon(icon(self.nav_icons[i], TONES[NAV_TONES[i]]['ink'] if i == index else '#627087', 25))
        self.pages.setCurrentIndex(0 if index <= 1 else index - 1)
        if index <= 1:
            self.render()
        elif index == 2:
            self.render_events()

    def build_discovery(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 24, 16)
        layout.setSpacing(12)
        top = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(5)
        self.heading = NounHeading()
        self.heading.set_title('대회 탐색')
        titles.addWidget(self.heading)
        self.hero_text = label('', 'muted', True)
        titles.addWidget(self.hero_text)
        top.addLayout(titles, 1)
        self.profile_pill = label('', 'profilePill')
        top.addWidget(self.profile_pill, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(top)
        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setObjectName('search')
        self.search.setClearButtonEnabled(True)
        self.search.addAction(icon('search'), QLineEdit.ActionPosition.LeadingPosition)
        self.search.setPlaceholderText('대회명, 주제, 설명으로 검색하기')
        self.search.textChanged.connect(self.reset_page)
        search_row.addWidget(self.search, 1)
        self.refresh_button = button('↻  지금 확인', self.refresh)
        search_row.addWidget(self.refresh_button)
        layout.addLayout(search_row)
        self.collection_tabs = QTabBar()
        self.collection_tabs.setDrawBase(False)
        self.collection_tabs.setObjectName('collectionTabs')
        self.collection_tabs.addTab('일반 대회')
        self.collection_tabs.addTab('교육용')
        self.collection_tabs.setAccessibleName('일반 대회와 교육용 구분')
        self.collection_tabs.currentChanged.connect(self.reset_page)
        group_row = QHBoxLayout()
        group_row.addWidget(self.collection_tabs, 0, Qt.AlignmentFlag.AlignLeft)
        self.topic = QComboBox()
        self.topic.addItems(['모든 분야'] + list(TOPICS) + ['LLM · NLP'])
        self.topic.setAccessibleName('대회 분야')
        self.topic.currentTextChanged.connect(self.reset_page)
        group_row.addWidget(self.topic)
        group_row.addStretch()
        self.filter_button = button('필터', lambda: None, icon_name='sliders-horizontal')
        menu = QMenu(self.filter_button)
        filter_panel = QWidget()
        filters = QVBoxLayout(filter_panel)
        filters.setContentsMargins(14, 12, 14, 12)
        filters.addWidget(label('정렬·표시', 'title'))
        self.sort = QComboBox()
        self.sort.addItems(['추천 순', '마감 임박 순', '최근 발견 순'])
        self.sort.currentTextChanged.connect(self.reset_page)
        filters.addWidget(self.sort)
        self.show_excluded = QCheckBox('제외·마감 대회 포함')
        self.show_hidden = QCheckBox('숨긴 대회도 보기')
        self.show_excluded.toggled.connect(self.reset_page)
        self.show_hidden.toggled.connect(self.reset_page)
        filters.addWidget(self.show_excluded)
        filters.addWidget(self.show_hidden)
        self.exclusion_button = button('제외 이유', self.show_exclusion_dialog, icon_name='eye-off')
        filters.addWidget(self.exclusion_button)
        action = QWidgetAction(menu)
        action.setDefaultWidget(filter_panel)
        menu.addAction(action)
        self.filter_button.setMenu(menu)
        group_row.addWidget(self.filter_button)
        self.trash_button = button('삭제 보관함', self.show_trash_dialog, icon_name='trash', tone='slate')
        group_row.addWidget(self.trash_button)
        layout.addLayout(group_row)
        split = QSplitter(Qt.Orientation.Horizontal)
        scroll = QScrollArea()
        self.list_scroll = scroll
        scroll.setWidgetResizable(True)
        contents = QWidget()
        self.cards = QVBoxLayout(contents)
        self.cards.setContentsMargins(0, 0, 8, 0)
        self.cards.setSpacing(16)
        scroll.setWidget(contents)
        split.addWidget(scroll)
        detail, d = card()
        self.detail_layout = d
        detail.setMinimumWidth(290)
        self.detail = SafeTextBrowser()
        self.detail.document().setDocumentMargin(4)
        self.detail.document().setDefaultStyleSheet(DOCUMENT_STYLE)
        self.detail.setMinimumHeight(0)
        d.addWidget(self.detail, 1)
        links = QHBoxLayout()
        self.original_button = button('Kaggle 원문 열기 ↗', self.open_selected, True)
        links.addWidget(self.original_button, 1)
        actions = QHBoxLayout()
        self.star_button = button('☆ 관심', self.star)
        self.rules_button = button('참가 조건', self.load_pages, icon_name='layers')
        links.addWidget(self.rules_button)
        d.addLayout(links)
        self.hide_button = button('숨기기', self.hide_item)
        self.hide_button.setParent(detail)
        self.hide_button.hide()
        self.delete_button = button('삭제', lambda: self.delete_competition(self.selected), icon_name='trash')
        actions.addWidget(self.star_button)
        actions.addWidget(self.delete_button)
        self.more_button = button('더보기', lambda: None, icon_name='sliders-horizontal')
        self.more_button.setObjectName('iconButton')
        self.more_button.setAccessibleName('더보기')
        self.more_button.setToolTip('더보기')
        more_menu = QMenu(self.more_button)
        self.more_rules_action = more_menu.addAction(icon('layers'), '참가 조건 확인', self.load_pages)
        self.more_hide_action = more_menu.addAction(icon('eye-off'), '숨김 해제', self.hide_item)
        self.more_button.setMenu(more_menu)
        actions.addWidget(self.more_button)
        d.addLayout(actions)
        split.addWidget(detail)
        split.setSizes([600, 420])
        layout.addWidget(split, 1)
        paging = QHBoxLayout()
        self.page_label = label('1 / 1 페이지', 'muted')
        paging.addWidget(self.page_label)
        paging.addStretch()
        self.display_size = QComboBox()
        for size in (5, 10, 20, 50):
            self.display_size.addItem(f'{size}개씩 보기', size)
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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'more_rules_action'):
            self.update_detail_actions()

    def update_detail_actions(self):
        if hasattr(self, 'more_rules_action'):
            compact = self.height() < 760
            self.detail_layout.setContentsMargins(18, 14 if compact else 18, 18, 12 if compact else 16)
            self.detail_layout.setSpacing(8 if compact else 12)
            self.star_button.setVisible(True)
            self.delete_button.setVisible(True)
            for button in (self.star_button, self.delete_button):
                button.setStyleSheet('padding:10px;' if compact else '')
            self.rules_button.setVisible(not compact)
            self.more_rules_action.setVisible(compact)
            row = self.selected_row()
            legacy_hidden = bool(row and row['hidden'])
            self.more_hide_action.setVisible(legacy_hidden)
            self.more_button.setVisible(compact or legacy_hidden)
            self.more_button.setText('')
            self.more_button.setFixedWidth(44)

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

    def apply_list_filters(self, *, search='', topic=0, sort=0, group=0,
                           include_excluded=False, include_hidden=False):
        widgets = (self.search, self.topic, self.sort, self.collection_tabs, self.show_excluded, self.show_hidden)
        blockers = [QSignalBlocker(widget) for widget in widgets]
        self.search.setText(search)
        self.topic.setCurrentIndex(topic)
        self.sort.setCurrentIndex(sort)
        self.collection_tabs.setCurrentIndex(group)
        self.show_excluded.setChecked(include_excluded)
        self.show_hidden.setChecked(include_hidden)
        for blocker in blockers:
            blocker.unblock()

    def clear_search_filters(self):
        self.apply_list_filters(group=self.collection_tabs.currentIndex())
        self.reset_page()

    def render(self, *_, reveal_ref=None):
        if not hasattr(self, 'cards'):
            return
        profile = self.store.profile()
        if self.mode <= 1:
            owner = ' '.join(profile['name'].split())
            if owner == DEFAULT['name']:
                owner = ''
            if not owner:
                owner = ' '.join((self.credentials or {}).get('username', '').split())
            if self.mode == 1 and owner:
                self.heading.set_title(owner, '의 관심 대회')
            else:
                self.heading.set_title('관심 대회' if self.mode == 1 else '대회 탐색')
        self.profile_summary.setText(self.profile_summary.fontMetrics().elidedText(profile['name'], Qt.TextElideMode.ElideRight, 80))
        self.profile_summary.setToolTip(profile['name'])
        self.profile_summary.setAccessibleName(profile['name'])
        self.profile_pill.setText(f"{profile['gpu']} · {profile['vram']}GB")
        separate = profile['separate_education']
        self.collection_tabs.setVisible(separate)
        self.show_excluded.setVisible(self.mode != 1)
        active_filters = []
        if self.sort.currentIndex():
            active_filters.append(self.sort.currentText())
        if self.mode == 0 and self.show_excluded.isChecked():
            active_filters.append('제외·마감 포함')
        if self.show_hidden.isChecked():
            active_filters.append('숨긴 대회 포함')
        self.filter_button.setText(f'필터 ({len(active_filters)})' if active_filters else '필터')
        self.filter_button.setToolTip(' · '.join(active_filters) or '정렬·표시 설정')
        education_view = separate and self.collection_tabs.currentIndex() == 1
        set_tone(self.collection_tabs, 'teal' if education_view else 'blue')
        intro = '관심 등록 대회 목록' if self.mode == 1 else ('입문·연습 대회 목록' if education_view else '참가 조건 적용 · 관심 분야에 따라 추천 점수 반영')
        self.hero_text.setText(('예시 데이터 화면 · ' if self.preview else '') + intro)
        self.hero_text.setToolTip(f"관심 분야 {len(profile['topics'])}개 · {profile['interval']}분마다 확인")
        deleted = self.store.trash_rows()
        self.trash_button.setText(f'삭제 보관함 ({len(deleted)})')
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
            if details and self.mode != 1 and not self.show_excluded.isChecked():
                continue
            search_text = ' '.join([str(item.get('title', '')), plain(item.get('description')), *verdict['topics']])
            if query and query not in search_text.lower():
                continue
            if self.topic.currentText() == 'LLM · NLP':
                if not {'NLP', 'LLM / 생성형 AI'}.intersection(verdict['topics']):
                    continue
            elif self.topic.currentIndex() and self.topic.currentText() not in verdict['topics']:
                continue
            results.append(row)
        education_count = sum(r['verdict']['education'] for r in results)
        self.collection_tabs.setTabText(0, f'일반 대회 ({len(results) - education_count})')
        self.collection_tabs.setTabText(1, f'교육용 ({education_count})')
        if separate:
            results = [r for r in results if r['verdict']['education'] == education_view]
        order = self.sort.currentIndex()
        if order == 2:
            results.sort(key=lambda r: r['first_seen'], reverse=True)
        else:
            def deadline_order(row):
                end = date(row['item'].get('deadline'))
                score = -row['verdict']['score'] if order == 0 else 0
                return end is None, score, end, row['ref']
            results.sort(key=deadline_order)
        size = profile['page_size']
        if reveal_ref:
            for index, row in enumerate(results):
                if row['ref'] == reveal_ref:
                    self.page_index = index // size
                    self.selected = reveal_ref
                    break
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
            if self.mode == 1 and not any(r['starred'] for r in rows):
                title, text, action, fn = '관심 대회 없음', '상세에서 관심 등록한 대회가 여기에 표시됩니다.', '대회 탐색', lambda: self.navigate(0)
            elif rows and (query or self.topic.currentIndex()):
                title, text, action, fn = '검색 결과 없음', '검색어나 분야를 변경할 수 있습니다.', '검색 조건 초기화', self.clear_search_filters
            elif separate and education_view and rows:
                title, text, action, fn = '교육용 대회 없음', '교육용 분류와 검색·제외 조건을 설정에서 조절할 수 있습니다.', '일반 대회 보기', lambda: self.collection_tabs.setCurrentIndex(0)
            elif separate and education_count and rows:
                title, text, action, fn = '일반 대회 없음', '현재 조건에 맞는 입문·연습 대회는 교육용 보기에 있습니다.', '교육용 보기', lambda: self.collection_tabs.setCurrentIndex(1)
            elif self.mode == 1:
                title, text, action, fn = '표시할 관심 대회 없음', '필터에서 숨긴 관심 대회도 확인할 수 있습니다.', '숨긴 대회 보기', lambda: self.show_hidden.setChecked(True)
            elif rows:
                title, text, action, fn = '추천 대회 없음', '참가 대상이나 추천 점수 조건을 조정할 수 있습니다.', '추천 조건 조정', lambda: self.navigate(3)
            elif self.credentials:
                title, text, action, fn = '대회 목록 미수집', '최신 대회 목록을 가져올 수 있습니다.', '지금 확인', self.refresh
            else:
                title, text, action, fn = 'Kaggle 계정 연결', '계정 연결 후 대회 목록을 수집합니다.', '계정 연결', self.connect_account
            self.empty_title = title
            p.addWidget(label(title, 'title'))
            p.addWidget(label(text, 'muted', True))
            p.addWidget(button(action, fn))
            self.cards.addWidget(panel)
        self.card_frames = {}
        for row in results:
            item, v = row['item'], row['verdict']
            title = str(item.get('title', row['ref']))
            panel = CompetitionCard(title)
            panel.setProperty('context', 'bookmark' if self.mode == 1 else 'education' if education_view else 'general')
            self.card_frames[row['ref']] = panel
            panel.clicked.connect(lambda ref=row['ref']: self.select(ref))
            panel.setMinimumHeight(112)
            p = QHBoxLayout(panel)
            p.setContentsMargins(16, 13, 16, 13)
            p.setSpacing(14)
            primary_topic, topic_icon, color, background = topic_visual(v['topics'])
            p.addWidget(icon_tile(topic_icon, color, background), 0, Qt.AlignmentFlag.AlignVCenter)
            body = QVBoxLayout()
            body.setSpacing(8)
            top = QHBoxLayout()
            name = label(title, 'listTitle', True)
            top.addWidget(name, 1)
            if v['education']:
                badge = label('교육용', 'chip')
                badge.setProperty('tone', 'teal')
                badge.setToolTip(v['education_reason'])
                top.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
            body.addLayout(top)
            meta = QHBoxLayout()
            meta.setSpacing(9)
            tag = label(primary_topic, 'chip')
            tag.setStyleSheet(f'background:{background};color:{color};border-radius:11px;padding:5px 9px;font-size:14px;')
            meta.addWidget(tag)
            calendar = QHBoxLayout()
            calendar.setSpacing(5)
            cal = QLabel()
            cal.setPixmap(icon('calendar-days', size=18).pixmap(18, 18))
            calendar.addWidget(cal)
            end = date(item.get('deadline'))
            calendar.addWidget(label(end.astimezone(KST).strftime('%Y.%m.%d') if end else '마감 확인', 'cardDate'))
            meta.addLayout(calendar)
            if end:
                long_practice = v['education'] and end > now() + timedelta(days=365)
                deadline = label('장기 운영' if long_practice else deadline_badge(item.get('deadline')), 'deadline')
                deadline.setProperty('tone', deadline_tone(item.get('deadline'), long_practice))
                meta.addWidget(deadline)
            meta.addStretch()
            body.addLayout(meta)
            if row['exclusions']:
                status = '상태' if self.mode == 1 else '제외'
                reasons = ' · '.join(dict.fromkeys(d['label'] for d in row['exclusions']))
                body.addWidget(label(f'{status} · {reasons}', 'muted', True))
            p.addLayout(body, 1)
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

    def show_trash_dialog(self):
        dialog = TrashDialog(self)
        dialog.exec()
        dialog.deleteLater()
        self.render()

    def delete_competition(self, ref):
        row = next((r for r in self.store.rows() if r['ref'] == ref), None)
        if not row:
            return
        until = trash_cutoff(json.loads(row['body']))
        if until and until <= now():
            answer = QMessageBox.question(self, '복구 기한 경과', '종료일에 도달한 대회는 삭제 후 복구할 수 없습니다. 삭제하시겠습니까?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
        if self.store.trash(ref):
            self.render()
            remaining = next((r for r in self.store.trash_rows() if r['ref'] == ref), None)
            self.status.setText('삭제 보관함 이동 · ' + recovery_label(remaining) if remaining else '삭제 완료 · 복구 기한 경과')

    def select(self, ref):
        if ref not in self.current_page_refs:
            ref = None
        self.selected = ref
        for key, frame in getattr(self, 'card_frames', {}).items():
            frame.setProperty('selected', key == ref)
            frame.style().unpolish(frame)
            frame.style().polish(frame)
            frame.update()
        row = self.selected_row()
        self.update_detail_actions()
        for b in (self.star_button, self.hide_button, self.delete_button, self.rules_button, self.original_button, self.more_button):
            b.setEnabled(row is not None)
        if not row:
            self.star_button.setText('관심 등록')
            self.hide_button.setText('숨기기')
            self.show_detail_document(None, '<h2>대회 상세 정보</h2><p>대회를 선택하면 일정과 추천 이유를 확인할 수 있습니다.</p>')
            return
        self.star_button.setText('관심 해제' if row['starred'] else '관심 등록')
        self.star_button.setIcon(icon('bookmark-check' if row['starred'] else 'bookmark', TONES['violet']['ink']))
        self.hide_button.setText('숨김 해제' if row['hidden'] else '숨기기')
        item = json.loads(row['body'])
        v = assess(item, self.store.profile())
        end = date(item.get('deadline'))
        long_practice = bool(v['education'] and end and end > now() + timedelta(days=365))
        _, _, topic_ink, _ = topic_visual(v['topics'])
        details = exclusion_details(item, self.store.profile(), v)
        body = detail_document(item, v, details, row['last_seen'], deadline_badge(item.get('deadline')),
                               TONES[deadline_tone(item.get('deadline'), long_practice)], topic_ink, long_practice)
        self.show_detail_document(ref, body)

    def show_detail_document(self, ref, body):
        previous_ref = getattr(self, '_detail_ref', None)
        if previous_ref == ref and getattr(self, '_detail_html', None) == body:
            return
        position = self.detail.verticalScrollBar().value() if previous_ref == ref else 0
        self._detail_ref, self._detail_html = ref, body
        self.detail.setHtml(body)
        self.detail.verticalScrollBar().setValue(position)

    def toggle_bookmark(self, ref):
        row = next((r for r in self.store.rows() if r['ref'] == ref), None)
        if row:
            self.store.flag(ref, 'starred', not row['starred'])
            self.render()

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
            previous = {r['ref']: json.loads(r['body']) for r in self.store.rows(include_deleted=True)}
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
        self.flush_notifications()

    def failed(self, text):
        self.refresh_button.setEnabled(True)
        self.next_due = now() + timedelta(minutes=self.store.profile()['interval'])
        self.store.set('last_error', text)
        self.status.setText(text + ' · 마지막 성공: ' + display_date(self.store.get('last_success')))

    def notify(self, title, text):
        if self.store.profile()['notify'] and self.tray.isVisible():
            self.tray.showMessage('Kaggle Scout · ' + title, text[:240], QSystemTrayIcon.MessageIcon.Information, 10000)
            return True
        return False

    def flush_notifications(self):
        if self.preview or not self.tray.isVisible():
            return
        batch = self.store.notification_batch(self.store.profile())
        if not batch:
            return
        counts = {kind: sum(e['kind'] == kind for e in batch) for kind in NOTIFY_KINDS}
        title = ' · '.join(f'{NOTIFY_KINDS[k]} {n}건' for k, n in counts.items() if n)
        text = batch[0]['message']
        if len(batch) > 1:
            text += f'\n외 {len(batch)-1}건 · 전체 내용은 알림 기록에서 확인하세요.'
        if self.notify(title, text):
            self.notice_ref = batch[0]['ref'] if len(batch) == 1 else None
            self.store.mark_notified([e['id'] for e in batch])

    def tick(self):
        if self.store.cleanup_trash():
            self.render()
        self.flush_notifications()
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
        box.setContentsMargins(28, 24, 24, 20)
        box.addWidget(label('알림 기록', 'heading'))
        box.addWidget(label('새 대회 · 관심 대회 변경·마감', 'muted'))
        self.events = SafeTextBrowser()
        self.events.document().setDocumentMargin(16)
        self.events.document().setDefaultStyleSheet(HISTORY_STYLE)
        self.events.anchorClicked.connect(self.open_history_link)
        box.addWidget(self.events)
        self.pages.addWidget(page)

    def open_history_link(self, url):
        if url.scheme() == 'scout':
            self.open_competition(url.path())

    def render_events(self):
        with self.store.connect() as con:
            rows = con.execute('SELECT * FROM events ORDER BY id DESC LIMIT 300').fetchall()
        titles = {r['ref']: json.loads(r['body']).get('title') or r['ref'] for r in self.store.rows()}
        self.events.setHtml(history_document(rows, titles))

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
        grid.setSpacing(10)
        p = self.store.profile()
        self.topic_checks = {}
        for n, name in enumerate(TOPICS):
            chk = QCheckBox(name)
            chk.setObjectName('choice')
            chk.setProperty('tone', TOPIC_TONES[name][0])
            chk.setChecked(name in p['topics'])
            self.topic_checks[name] = chk
            grid.addWidget(chk, n // 2, n % 2)
        i.addLayout(grid)
        box.addWidget(interests)
        participation, pa = card()
        pa.addWidget(label('참가 대상', 'title'))
        self.audience_checks = {}
        audience_grid = QGridLayout()
        audience_grid.setSpacing(10)
        for n, (key, text) in enumerate(AUDIENCES.items()):
            chk = QCheckBox(text)
            chk.setObjectName('choice')
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
        h.addWidget(label('사용 환경', 'title'))
        fields = QGridLayout()
        fields.setHorizontalSpacing(16)
        fields.setVerticalSpacing(10)
        self.name_input = QLineEdit('' if p['name'] == DEFAULT['name'] else p['name'])
        self.name_input.setPlaceholderText('이름 또는 Kaggle 아이디 (선택)')
        self.name_input.setToolTip('관심 화면 제목에 표시됩니다. 미입력 시 저장된 Kaggle 아이디를 사용하며, 아이디가 없으면 관심 대회로 표시합니다.')
        self.name_input.setMaxLength(100)
        self.skills_input = QLineEdit(p['skills'])
        self.skills_input.setMaxLength(250)
        self.gpu_input = QLineEdit(p['gpu'])
        self.gpu_input.setMaxLength(120)
        self.vram_input = SliderInput('GPU VRAM', 0, 512, p['vram'], ' GB', slider_max=64,
                                     presets=[(8, '8GB'), (16, '16GB'), (24, '24GB'), (32, '32GB')],
                                     low_label='GPU 없음', high_label='64GB · 더 큰 용량은 직접 입력')
        for n, (name, widget) in enumerate([('이름 / 표시명', self.name_input), ('보유 기술', self.skills_input), ('GPU 이름 (없으면 없음)', self.gpu_input), ('GPU VRAM', self.vram_input)]):
            fields.addWidget(label(name, 'muted'), n, 0)
            fields.addWidget(widget, n, 1)
        h.addLayout(fields)
        self.paid = QCheckBox('유료 API를 사용하는 대회도 허용')
        self.paid.setChecked(p['paid_api'])
        h.addWidget(self.paid)
        h.addWidget(label('자원 요구량이 공개되지 않은 대회는 상세 화면에 확인 필요로 표시합니다.', 'muted', True))
        box.addWidget(hardware)
        filters, f = card()
        f.addWidget(label('수집·필터 설정', 'title'))
        self.offline = QCheckBox('오프라인 참석 필수 문구가 감지된 대회 제외')
        self.offline.setChecked(p['exclude_offline'])
        self.notifications = QCheckBox('PC 알림 받기')
        self.notifications.setChecked(p['notify'])
        self.autostart = QCheckBox('Windows 로그인 시 트레이로 자동 시작')
        self.autostart.setChecked(self.autostart_enabled())
        for chk in [self.offline, self.autostart]:
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
        education_card, ec = card()
        ec.addWidget(label('교육용 대회', 'title'))
        self.separate_education = QCheckBox('일반 대회와 교육용을 나눠 보기')
        self.education_playground = QCheckBox('Playground 대회도 교육용으로 분류')
        self.notify_education = QCheckBox('교육용 새 대회도 알림 받기')
        for key, chk in [('separate_education', self.separate_education), ('education_playground', self.education_playground), ('notify_education', self.notify_education)]:
            chk.setChecked(p[key])
            ec.addWidget(chk)
        ec.addWidget(label('Getting Started 등 입문 카테고리를 기준으로 분류합니다.', 'muted', True))
        ec.addWidget(label('관심 등록한 교육용 대회의 변경·마감은 알림 설정을 따릅니다.', 'muted', True))
        box.addWidget(education_card)
        notification_card, nc = card()
        nc.addWidget(label('알림 설정', 'title'))
        nc.addWidget(self.notifications)
        nc.addSpacing(4)
        nc.addWidget(label('알림 종류', 'sectionTitle'))
        self.notify_kind_checks = {}
        notification_help = {
            '새 추천': '관심 등록과 관계없이 내 추천 조건에 맞는 새 대회 발견. 교육용 신규 알림은 수집·보기 설정에서 별도 선택합니다.',
            '정보 변경': '관심 등록한 대회의 주요 설명·일정·보상 등 변경.',
            '마감 임박': '관심 대회의 참가·팀 구성·제출 마감이 7·3·1일 이내로 진입.',
        }
        for kind, text in NOTIFY_KINDS.items():
            chk = QCheckBox('새 추천 대회' if kind == '새 추천' else text)
            chk.setProperty('tone', {'새 추천': 'blue', '정보 변경': 'violet', '마감 임박': 'amber'}[kind])
            chk.setToolTip(notification_help[kind])
            chk.setChecked(kind in p['notify_kinds'])
            self.notify_kind_checks[kind] = chk
            nc.addWidget(chk)
        nc.addWidget(label('새 대회는 추천 조건, 변경·마감은 관심 등록 기준으로 기록합니다.', 'muted', True))
        nc.addSpacing(8)
        nc.addWidget(label('수신 시간', 'sectionTitle'))
        schedule_row = QHBoxLayout()
        schedule_row.setSpacing(10)
        self.notify_schedule = QComboBox()
        self.notify_schedule.addItem('언제든 받기', 'always')
        self.notify_schedule.addItem('지정 시간에만 받기', 'window')
        self.notify_schedule.setCurrentIndex(self.notify_schedule.findData(p['notify_schedule']))
        schedule_row.addWidget(self.notify_schedule)
        self.notify_start = QTimeEdit(QTime.fromString(p['notify_start'], 'HH:mm'))
        self.notify_end = QTimeEdit(QTime.fromString(p['notify_end'], 'HH:mm'))
        for widget, name in [(self.notify_start, '알림 시작 시간'), (self.notify_end, '알림 종료 시간')]:
            widget.setDisplayFormat('HH:mm')
            widget.setMinimumWidth(92)
            widget.setAccessibleName(name + ' KST')
        schedule_row.addWidget(self.notify_start)
        schedule_row.addWidget(label('~'))
        schedule_row.addWidget(self.notify_end)
        schedule_row.addWidget(label('KST', 'muted'))
        schedule_row.addStretch()
        nc.addLayout(schedule_row)
        notes = QVBoxLayout()
        notes.setSpacing(7)
        notes.addWidget(label('지정 시간 밖의 알림은 보관했다가 다음 수신 시간에 묶어 표시합니다.', 'muted', True))
        notes.addWidget(label('앱이 실행 중일 때만 표시합니다. 꺼둔 종류는 기록에 남습니다.', 'muted', True))
        nc.addLayout(notes)
        box.addWidget(notification_card)
        scroll.setWidget(page)
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.setContentsMargins(20, 18, 20, 0)
        outer.addWidget(label('나의 설정', 'heading'))
        self.settings_tabs = QTabWidget()
        self.settings_tabs.tabBar().setObjectName('settingsTabs')
        self.settings_tabs.tabBar().setProperty('tone', 'blue')
        self.settings_tab_scrolls = []
        groups = [('프로필·환경', [connection, hardware]), ('관심·참가', [interests, participation]),
                  ('수집·보기', [education_card, filters]), ('알림', [notification_card])]
        for title, panels in groups:
            tab_scroll = QScrollArea()
            tab_scroll.setWidgetResizable(True)
            tab_page = QWidget()
            tab_box = QVBoxLayout(tab_page)
            tab_box.setContentsMargins(2, 14, 8, 16)
            tab_box.setSpacing(20)
            for panel in panels:
                box.removeWidget(panel)
                tab_box.addWidget(panel)
            tab_box.addStretch()
            tab_scroll.setWidget(tab_page)
            self.settings_tabs.addTab(tab_scroll, title)
            self.settings_tab_scrolls.append(tab_scroll)
        self.settings_scroll = self.settings_tab_scrolls[0]
        self.settings_tabs.currentChanged.connect(self.settings_section_changed)
        outer.addWidget(self.settings_tabs, 1)
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
                      self.paid, self.offline, self.notifications, self.autostart,
                      self.separate_education, self.education_playground, self.notify_education]:
            check.toggled.connect(self.queue_settings_preview)
        self.page_size_input.currentIndexChanged.connect(self.queue_settings_preview)
        self.notify_schedule.currentIndexChanged.connect(self.update_notification_controls)
        self.notifications.toggled.connect(self.update_notification_controls)
        for chk in self.notify_kind_checks.values():
            chk.toggled.connect(self.queue_settings_preview)
        self.notify_start.timeChanged.connect(self.queue_settings_preview)
        self.notify_end.timeChanged.connect(self.queue_settings_preview)
        self.update_notification_controls()

    def settings_section_changed(self, index):
        self.settings_scroll = self.settings_tab_scrolls[index]
        set_tone(self.settings_tabs.tabBar(), ('blue', 'violet', 'teal', 'amber')[index])
        self.queue_settings_preview()

    def update_notification_controls(self, *_):
        enabled = self.notifications.isChecked()
        self.notify_schedule.setEnabled(enabled)
        for chk in self.notify_kind_checks.values():
            chk.setEnabled(enabled)
        window = enabled and self.notify_schedule.currentData() == 'window'
        self.notify_start.setEnabled(window)
        self.notify_end.setEnabled(window)
        self.queue_settings_preview()

    def queue_settings_preview(self, *_):
        self.settings_preview_timer.start(150)

    def preview_settings(self):
        try:
            p = self.read_form()
        except ValueError:
            self.settings_status.setText('입력값을 확인해 주세요.')
            return
        changed = p != self.store.profile() or (not self.preview and self.autostart.isChecked() != self.autostart_enabled())
        state = '저장 전' if changed else '저장됨'
        if self.settings_tabs.currentIndex() == 3:
            schedule = 'PC 알림 끔'
            if p['notify']:
                schedule = 'PC 알림 항상 표시'
                if p['notify_schedule'] == 'window':
                    start, end = p['notify_start'], p['notify_end']
                    day = '다음 날 ' if end < start else ''
                    schedule = f'PC 알림 {start}~{day}{end} KST'
            self.settings_status.setText(f'{state} · {schedule}')
            return
        rows = [r for r in self.store.rows() if not r['hidden']]
        verdicts = [assess(json.loads(r['body']), p) for r in rows]
        candidates = sum(not v['excluded'] and v['score'] >= p['min_score'] for v in verdicts)
        education_count = sum(v['education'] and not v['excluded'] and v['score'] >= p['min_score'] for v in verdicts)
        self.settings_status.setText(state + (f' · 현재 목록에서 추천 후보 {candidates}개' if rows else ' · 수집 후 추천 후보를 확인할 수 있습니다.'))
        if rows and p['separate_education']:
            self.settings_status.setText(self.settings_status.text() + f' (일반 {candidates - education_count} · 교육 {education_count})')

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
                 separate_education=self.separate_education.isChecked(),
                 education_playground=self.education_playground.isChecked(),
                 notify_education=self.notify_education.isChecked(),
                 notify=self.notifications.isChecked(), interval=self.interval.value(),
                 notify_kinds=[k for k, chk in self.notify_kind_checks.items() if chk.isChecked()],
                 notify_schedule=self.notify_schedule.currentData(),
                 notify_start=self.notify_start.time().toString('HH:mm'),
                 notify_end=self.notify_end.time().toString('HH:mm'),
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
        self.render()

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
            self.settings_status.setText('입력값을 확인하세요. 알림 시작/종료는 달라야 하며 제외 키워드는 50개 이하, 각 80자 이하입니다.')
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
        if self.settings_tabs.currentIndex() == 3:
            self.preview_settings()
        else:
            self.settings_status.setText('설정을 저장했습니다. 추천 목록에 적용되었습니다.')
        self.render()
        self.flush_notifications()
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
            self.separate_education.setChecked(p['separate_education'])
            self.education_playground.setChecked(p['education_playground'])
            self.notify_education.setChecked(p['notify_education'])
            self.notifications.setChecked(p['notify'])
            for key, chk in self.notify_kind_checks.items():
                chk.setChecked(key in p['notify_kinds'])
            self.notify_schedule.setCurrentIndex(self.notify_schedule.findData(p['notify_schedule']))
            self.notify_start.setTime(QTime.fromString(p['notify_start'], 'HH:mm'))
            self.notify_end.setTime(QTime.fromString(p['notify_end'], 'HH:mm'))
            self.update_notification_controls()
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
    apply_theme(app)
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
