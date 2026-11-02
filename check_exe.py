"""Bounded self-test: fail on crash, missing report, or hung executable."""
import json
import os
import subprocess
import sys
from pathlib import Path


if __name__ == '__main__':
    report = Path('.build/checks/exe-selftest.json').resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    report.unlink(missing_ok=True)
    exe = Path('dist/QQPassManager.exe').resolve()
    process = subprocess.Popen([str(exe),'--self-test','--report',str(report)])
    try:
        code = process.wait(timeout=45)
    except subprocess.TimeoutExpired:
        if os.name == 'nt':
            subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],check=False,capture_output=True)
        else:
            process.kill()
        print('EXE self-test timed out; this build has NOT passed.', file=sys.stderr)
        raise SystemExit(1)
    if code != 0 or not report.is_file():
        print(f'EXE self-test failed (exit={code}, report={report.is_file()}).',file=sys.stderr)
        raise SystemExit(1)
    result = json.loads(report.read_text(encoding='utf-8'))
    if result.get('ok') is not True:
        print('EXE self-test report indicates failure.',file=sys.stderr)
        raise SystemExit(1)
    print(f"EXE self-test: PASS ({len(result['checks'])} groups of checks)")
