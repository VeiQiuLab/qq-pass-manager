"""Package only curated source/docs plus the rebuilt executable; exclude runtime data."""
from pathlib import Path
import hashlib, os, zipfile
ROOT=Path(__file__).resolve().parents[1]
SLUG=ROOT.name
allowed={'.py','.pyw','.mjs','.md','.txt','.json','.html','.command','.bat','.yml'}
excluded={'.git','.build','build','dist','release','__pycache__','.venv-build','.pytest_cache'}
files=[]
for p in ROOT.rglob('*'):
 rel=p.relative_to(ROOT)
 if not p.is_file() or any(x in excluded for x in rel.parts): continue
 if 'third_party_licenses' in rel.parts or p.suffix in allowed or p.name in ('LICENSE','.gitignore','.gitattributes'):
  files.append(p)
if SLUG!='video-bitrate-calculator-macos':
 exe=ROOT/'dist'/'QQPassManager.exe'
 if not exe.is_file(): raise SystemExit('Build the executable first')
 files.append(exe)
out=ROOT/'release';out.mkdir(exist_ok=True)
name=SLUG+'-archive-2026-11-02.zip'
hashes=[]
with zipfile.ZipFile(out/name,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for p in sorted(files):
  rel=p.relative_to(ROOT).as_posix()
  if p.suffix=='.exe': rel=p.name
  b=p.read_bytes();hashes.append(hashlib.sha256(b).hexdigest()+'  '+rel)
  info=zipfile.ZipInfo(SLUG+'/'+rel)
  info.create_system=3;info.external_attr=(0o100755 if p.suffix=='.command' else 0o100644)<<16
  info.compress_type=zipfile.ZIP_DEFLATED
  z.writestr(info,b)
 z.writestr(SLUG+'/SHA256SUMS.txt','\n'.join(hashes)+'\n')
with zipfile.ZipFile(out/name) as z: assert z.testzip() is None
(out/'SHA256SUMS.txt').write_text(hashlib.sha256((out/name).read_bytes()).hexdigest()+'  '+name+'\n',encoding='utf-8')
print('PACKAGE_PASS: '+name)
