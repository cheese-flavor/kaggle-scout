"""Local, versioned visual assets and tokens for the selected light app design."""
from pathlib import Path
import sys
from functools import lru_cache
from PySide6.QtCore import Qt, QByteArray
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer

ASSETS = Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / 'assets'

@lru_cache(maxsize=128)
def icon(name, color='#68758b', size=22):
    source = (ASSETS/'icons'/(name+'.svg')).read_text(encoding='utf8')
    result = QIcon()
    for mode, tint in [(QIcon.Mode.Normal, color), (QIcon.Mode.Disabled, '#acb8c6')]:
        pixmap = QPixmap(size*2, size*2)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        QSvgRenderer(QByteArray(source.replace('currentColor', tint).encode())).render(painter)
        painter.end()
        pixmap.setDevicePixelRatio(2)
        result.addPixmap(pixmap, mode)
    return result

def asset(name):
    return str(ASSETS/'icons'/(name+'.svg')).replace('\\','/')

STYLE = '''
* { font-family: "Pretendard", "Malgun Gothic"; font-size:16px; font-weight:400; color:#16283f; }
QMainWindow,QDialog { background:#f7f9fd; }
QWidget#sidebar {background:#ffffff; border-right:1px solid #e9edf4;}
QLabel {background:transparent; border:0;}
QLabel#muted {color:#627086; font-size:16px;}
QLabel#eyebrow {color:#0386af; font-size:12px; font-weight:600;}
QLabel#heading {font-size:36px; font-weight:700; color:#12223b;}
QLabel#title {font-size:24px; font-weight:600;}
QLabel#brand {font-size:15px; font-weight:700;}
QLabel#chip {background:#e6f8ff; color:#027ca4; border-radius:12px; padding:5px 10px; font-size:12px; font-weight:600;}
QLabel#profilePill {font-size:16px;background:#ffffff; border:1px solid #e1e7ef; border-radius:19px; padding:10px 16px; font-weight:600;}
QFrame#card {background:#ffffff; border:1px solid #e3e9f1; border-radius:20px;}
QFrame#hero {background:#eaf9ff; border:1px solid #bfeafa; border-radius:20px;}
QFrame#competitionCard {background:transparent; border:1px solid transparent; border-bottom:1px solid #e6ebf3; border-radius:0px;}
QFrame#competitionCard:hover {background:#f0f7fc; border-radius:20px;}
QFrame#competitionCard[selected="true"] {background:#edfaff; border:1px solid #15b8f3; border-radius:20px;}
QFrame#competitionCard:focus {border:2px solid #178ab4; border-radius:20px;}
QPushButton {background:#ffffff; border:1px solid #e0e6ef; border-radius:14px; padding:10px 15px; font-weight:500;}
QPushButton:hover {background:#eff8fd; border-color:#9edcf2;}
QPushButton:pressed {background:#def2fc;}
QPushButton:focus {border:2px solid #1687b1;}
QPushButton:disabled {background:#f0f3f7; border-color:#e6ebf2; color:#a0adbc;}
QPushButton#primary {background:#08b7ed; border-color:#08b7ed; color:#072c43; font-weight:600; border-radius:18px; padding:14px 18px;}
QPushButton#primary:hover {background:#34c5f5;}
QPushButton#primary:disabled {background:#edf1f6; border-color:#e5eaf1; color:#a0adbc;}
QPushButton#chipButton {border-radius:19px; padding:10px 18px; background:#ffffff;}
QPushButton#chipButton:checked {background:#0ab7ee; border-color:#0ab7ee; color:#07324b; font-weight:600;}
QPushButton#iconButton {border-radius:12px; padding:6px;}
QToolButton#nav {border:0; background:transparent; border-radius:20px; color:#5e6e84; padding:14px 6px; font-size:14px; font-weight:500;}
QToolButton#nav:hover {background:#f0f8fc;}
QToolButton#nav:checked {background:#e1f7ff; color:#0083ae; font-weight:700;}
QLineEdit,QComboBox,QSpinBox,QTimeEdit {background:#ffffff; border:1px solid #dfe5ee; border-radius:12px; padding:10px 12px; min-height:18px; selection-background-color:#c7efff;}
QLineEdit#search {border-radius:24px; padding:14px 12px; font-size:16px;}
QLineEdit:focus,QComboBox:focus,QSpinBox:focus,QTimeEdit:focus {border-color:#14b2eb;}
QComboBox::drop-down {border:0; width:26px;}
QComboBox::down-arrow {image:url("DOWN"); width:14px; height:14px;}
QComboBox QAbstractItemView {background:white; border:1px solid #e0e7ef; selection-background-color:#e6f7ff; color:#203146; padding:6px;}
QSpinBox::up-button {subcontrol-origin:border; subcontrol-position:top right; width:25px; border:0;}
QSpinBox::down-button {subcontrol-origin:border; subcontrol-position:bottom right; width:25px; border:0;}
QSpinBox::up-arrow {image:url("UP"); width:12px; height:12px;}
QSpinBox::down-arrow {image:url("DOWN"); width:12px; height:12px;}
QCheckBox {spacing:10px; padding:6px 2px;}
QCheckBox::indicator {width:19px; height:19px; background:#ffffff; border:1px solid #bdcbd9; border-radius:6px;}
QCheckBox::indicator:checked {background:#20beff; border-color:#20beff; image:url("CHECK");}
QCheckBox:disabled {color:#a1adbc;}
QTimeEdit:disabled,QComboBox:disabled {color:#9ba9b9;background:#f2f5f9;border-color:#e5eaf1;}
QCheckBox#choice {border:1px solid #e1e7ef; border-radius:16px; padding:12px; background:#ffffff;}
QCheckBox#choice:checked {border-color:#a4dff4; background:#e9f9ff; color:#03799f;}
QScrollArea {border:0; background:transparent;}
QScrollArea > QWidget > QWidget {background:transparent;}
QTextBrowser {background:transparent; border:0; padding:0;}
QScrollBar:vertical {background:transparent; width:8px; margin:3px;}
QScrollBar::handle:vertical {background:#d5deea; min-height:28px; border-radius:3px;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;}
QSlider::groove:horizontal {height:7px; background:#e3eaf3; border-radius:3px;}
QSlider::sub-page:horizontal {background:#20beff; border-radius:3px;}
QSlider::handle:horizontal {background:white; border:2px solid #0ab4ec; width:18px; margin:-7px 0; border-radius:10px;}
QSlider::handle:horizontal:focus {border:3px solid #17354e;}
QWidget#settingsFooter {background:white; border-top:1px solid #e4eaf2;}
QTabWidget::pane {border:0; background:transparent;}
QTabBar::tab {background:transparent; border:0; color:#6b7890; padding:12px 18px; margin:3px; border-radius:16px;}
QTabBar::tab:selected {background:#e0f7ff; color:#0080aa; font-weight:600;}
QListWidget {background:white; border:1px solid #e5eaf2; border-radius:15px; padding:8px; outline:0;}
QListWidget::item {padding:12px; border-radius:10px;}
QListWidget::item:selected {background:#e6f8ff; color:#12627e;}
QMenu {background:#ffffff; border:1px solid #e3eaf2; border-radius:14px; padding:10px;}
'''.replace('DOWN', asset('chevron-down')).replace('UP', asset('chevron-up')).replace('CHECK', asset('check'))
