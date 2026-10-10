"""Build the Windows single-file player with PyInstaller.

Runs on a Windows machine (e.g. GitHub Actions windows-latest):

  1. Takes the song from media/song.mp3, or extracts the exact bytes the
     author embedded in the upstream v1.0.0 release package (verified
     against its bundle manifest SHA-256).
  2. Builds world-execute-mv.exe with PyInstaller (--onefile, console).
  3. Smoke-tests the exe in --snapshot mode (needs no audio device).
  4. Packs world-execute-mv-windows.zip + SHA256SUMS.txt.
"""
import hashlib
import json
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'
UPSTREAM_PYZ = ('https://github.com/yym8224961/world.execute-me-ascii'
                '/releases/download/v1.0.0/world-execute-mv.pyz')
RESOURCES = ('player.py', 'scenes.py', 'console_win.py', 'audio_engine.py',
             'config.json', 'lyrics.json', 'spectrum.json')


def ensure_song():
    media = ROOT / 'media'
    media.mkdir(exist_ok=True)
    song = media / 'song.mp3'
    if song.is_file():
        return
    print('media/song.mp3 not found, extracting from upstream v1.0.0 package...')
    DIST.mkdir(exist_ok=True)
    tmp = DIST / 'upstream.pyz'
    urllib.request.urlretrieve(UPSTREAM_PYZ, tmp)
    with zipfile.ZipFile(tmp) as bundle:
        manifest = json.loads(bundle.read('bundle-manifest.json'))
        data = bundle.read('media/song.mp3')
        want = manifest['files']['media/song.mp3']
        assert hashlib.sha256(data).hexdigest() == want, 'song.mp3 checksum mismatch'
        song.write_bytes(data)
    print('song.mp3 extracted and verified: %d bytes' % song.stat().st_size)


def build_exe():
    for name in RESOURCES:
        assert (ROOT / name).is_file(), 'missing resource: ' + name
    sep = ';'  # PyInstaller --add-data separator on Windows
    cmd = [sys.executable, '-m', 'PyInstaller',
           '--noconfirm', '--clean', '--onefile',
           '--name', 'world-execute-mv',
           '--console',
           '--add-data', f'media/song.mp3{sep}media',
           '--add-data', f'config.json{sep}.',
           '--add-data', f'lyrics.json{sep}.',
           '--add-data', f'spectrum.json{sep}.',
           '--collect-all', 'just_playback',
           '--collect-all', 'cffi',
           '--hidden-import', '_cffi_backend',
           '--hidden-import', 'audio_engine',
           '--hidden-import', 'console_win',
           'player.py']
    subprocess.run(cmd, cwd=ROOT, check=True)
    exe = DIST / 'world-execute-mv.exe'
    assert exe.is_file(), 'PyInstaller did not produce the exe'
    return exe


def smoke_test(exe):
    # --snapshot renders one frame and exits; needs no audio device,
    # but proves resources (song/lyrics/spectrum/config) are bundled
    # and the player code runs inside the frozen exe.
    proc = subprocess.run([str(exe), '--snapshot', '10', '--plain',
                           '--width', '120', '--height', '40'],
                          capture_output=True, timeout=180)
    out = proc.stdout.decode('utf-8', errors='replace')
    assert proc.returncode == 0, 'snapshot smoke test failed: ' + proc.stderr.decode('utf-8', errors='replace')[:500]
    assert 'WORLD.EXECUTE(ME);' in out, 'snapshot output looks wrong'
    assert len(out.splitlines()) >= 40, 'snapshot output too short'
    print('snapshot smoke test OK (%d lines)' % len(out.splitlines()))


def package(exe):
    pkg = DIST / 'world-execute-mv'
    if pkg.exists():
        shutil.rmtree(pkg)
    pkg.mkdir(parents=True)
    shutil.copy2(exe, pkg / 'world-execute-mv.exe')
    shutil.copy2(ROOT / '运行Windows版.bat', pkg / '运行Windows版.bat')
    shutil.copy2(ROOT / 'Windows说明.txt', pkg / 'Windows说明.txt')
    (pkg / 'SHA256SUMS.txt').write_text(''.join(
        '%s  %s\n' % (hashlib.sha256(p.read_bytes()).hexdigest(), p.name)
        for p in sorted(pkg.iterdir())), encoding='utf-8')
    archive = DIST / 'world-execute-mv-windows.zip'
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(pkg.rglob('*')):
            if p.is_file():
                zf.write(p, 'world-execute-mv/' + p.relative_to(pkg).as_posix())
    print('built: %s (%d bytes)' % (archive, archive.stat().st_size))


def main():
    ensure_song()
    exe = build_exe()
    smoke_test(exe)
    package(exe)


if __name__ == '__main__':
    main()
