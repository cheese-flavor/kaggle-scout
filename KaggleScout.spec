# PyInstaller collects all plugins for a Qt module by default. The desktop
# app uses the Windows platform, native style, and its local SVG/ICO assets.
from pathlib import PurePosixPath

analysis = Analysis(['app.py'], datas=[('assets', 'assets')],
                    module_collection_mode={'PySide6': 'py', 'shiboken6': 'py'})
qt_dlls = {'qt6core.dll', 'qt6gui.dll', 'qt6widgets.dll', 'qt6svg.dll'}
qt_bindings = {'qtcore.pyd', 'qtgui.pyd', 'qtwidgets.pyd', 'qtsvg.pyd'}
qt_plugins = {'qwindows.dll', 'qmodernwindowsstyle.dll', 'qico.dll', 'qsvg.dll', 'qsvgicon.dll'}


def used_binary(entry):
    target = PurePosixPath(entry[0].replace('\\', '/').lower())
    if target.parts[0] != 'pyside6':
        return True
    if 'plugins' in target.parts:
        return target.name in qt_plugins
    if target.name.startswith('qt6') and target.suffix == '.dll':
        return target.name in qt_dlls
    if target.name.startswith('qt') and target.suffix == '.pyd':
        return target.name in qt_bindings
    return target.name != 'opengl32sw.dll'


pyz = PYZ(analysis.pure)
exe = EXE(pyz, analysis.scripts, [], exclude_binaries=True, name='KaggleScout',
          console=False, upx=False, version='version_info.txt', icon='assets/scout.ico')
bundle = COLLECT(exe, [entry for entry in analysis.binaries if used_binary(entry)],
                 analysis.datas, upx=False, name='KaggleScout')
