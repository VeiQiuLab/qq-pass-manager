"""Build in this isolated checkout; no dependency installation or system changes."""
from pathlib import Path
import os, subprocess, sys
ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT)
os.environ.setdefault('PYTHONDONTWRITEBYTECODE','1')
os.environ.setdefault('PYINSTALLER_CONFIG_DIR',str(ROOT/'.build/pyinstaller-cache'))
def run(args, timeout=240):
 subprocess.run(args,check=True,timeout=timeout)
if sys.platform!='win32': raise SystemExit('Windows build required')
sys.path.insert(0,str(ROOT))
run([sys.executable,'-B','-m','unittest','discover','-s','tests','-v'])
run([sys.executable,'-B','-c',"from smoke import run; run('.build/checks/source-selftest.json')"])
run([sys.executable,'-B','build_exe.py'])
run([sys.executable,'-B','check_exe.py'])
print('BUILD_PASS: QQPassManager.exe')
