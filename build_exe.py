"""Build entry point; also supports Python virtualenvs based on Windows Conda."""
import os
import sys
from pathlib import Path

import PyInstaller.__main__


if __name__ == '__main__':
    # Conda DLLs live here rather than beside python.exe. Restrict this PATH
    # change to this build process so PyInstaller can resolve actual dependencies.
    conda_bin = Path(sys.base_prefix) / 'Library' / 'bin'
    if conda_bin.is_dir():
        os.environ['PATH'] = str(conda_bin) + os.pathsep + os.environ.get('PATH', '')
    PyInstaller.__main__.run([
        '--noconfirm','--clean','--onefile','--windowed','--name','QQPassManager',
        '--distpath','dist','--workpath','.build/pyinstaller','--specpath','.build','app.py',
    ])
