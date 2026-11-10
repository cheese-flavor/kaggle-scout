# Third-party software in the Windows distribution

Kaggle Scout's own code is distributed under the MIT license in [LICENSE](LICENSE).

**This distribution uses Qt Base, Qt SVG, PySide6 Essentials and Shiboken6 6.11.3 under the GNU LGPL version 3.** The Windows package contains the LGPLv3 and GPLv3 texts and upstream attributions under `licenses/Qt-6.11.3/`. The same texts are available in the [source repository](https://github.com/cheese-flavor/kaggle-scout/tree/v0.10.3/licenses/Qt-6.11.3). Copyright belongs to The Qt Company Ltd. and the contributors listed in the upstream sources and attributions.

The Qt and PySide6 libraries are shipped as separate files. A recipient can replace the libraries with ABI-compatible modified versions under `_internal/PySide6/` and `_internal/shiboken6/`, or rebuild the application from [the release's application source](https://github.com/cheese-flavor/kaggle-scout/tree/v0.10.3) using `build.ps1` and the corresponding library versions. The distribution terms permit debugging such modifications, including reverse engineering for that purpose. The libraries are unmodified upstream binaries from the PySide6 Essentials and Shiboken6 wheels.

## Corresponding source

The [v0.10.3 release](https://github.com/cheese-flavor/kaggle-scout/releases/tag/v0.10.3) provides these unmodified corresponding source archives alongside the Windows ZIP, at no charge. The upstream links are also available.

| Component | Upstream source | SHA-256 |
|---|---|---|
| Qt Base 6.11.3 | [qtbase-everywhere-src-6.11.3.tar.xz](https://download.qt.io/archive/qt/6.11/6.11.3/submodules/qtbase-everywhere-src-6.11.3.tar.xz) | `46de0710b594945a5d446ae44354daa386141c6903c53781b2ca547bc62f8f8f` |
| Qt SVG 6.11.3 | [qtsvg-everywhere-src-6.11.3.tar.xz](https://download.qt.io/archive/qt/6.11/6.11.3/submodules/qtsvg-everywhere-src-6.11.3.tar.xz) | `9bdf6fa4b5a2d91c3eaa2edd12263fdff0ae19d0ac25d3c99946cd4189a07123` |
| PySide6 and Shiboken6 6.11.3 | [pyside-setup-everywhere-src-6.11.3.tar.xz](https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.11.3-src/pyside-setup-everywhere-src-6.11.3.tar.xz) | `050819cb05e14d6689f42b56e4fa9c8ff63be2bb339e0c094c45b990b7cabde1` |

The package also carries CPython and Python dependency notices under `licenses/`, and the Pretendard (SIL OFL) and Lucide (ISC) notices alongside their assets. PyInstaller's [bootloader exception](https://pyinstaller.org/en/stable/license.html) applies to the executable packaging.
