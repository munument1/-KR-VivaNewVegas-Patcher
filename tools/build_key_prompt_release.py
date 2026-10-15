"""Build an installer from verified resources while preserving its worker."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
from tools.prepare_key_prompt_release import prepare, verify


def build(base, expected_sha256, project, work, output):
    if hashlib.sha256(base.read_bytes()).hexdigest() != expected_sha256:
        raise ValueError('Base release checksum mismatch')
    if work.exists():
        raise FileExistsError(work)
    work.mkdir(parents=True)
    output.mkdir(parents=True, exist_ok=True)
    is_ns = project == 'ns'
    name = 'NuclearSunsetKoreanPatcher' if is_ns else 'VNVKoreanPatcher'
    worker = 'NSKRXEditWorker.exe' if is_ns else 'VNVKRXEditWorker.exe'
    source = 'nskr_gui.py' if is_ns else 'vnvkr_gui.py'
    version = __import__('nskr' if is_ns else 'vnvkr').VERSION
    base_exe = base
    if is_ns:
        with zipfile.ZipFile(base) as archive:
            if archive.testzip():
                raise ValueError('Corrupt base ZIP')
            base_exe = work / (name + '-base.exe')
            base_exe.write_bytes(archive.read(name + '.exe'))
    root = work / 'resources'
    prepare(base_exe, root)
    args = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onefile', '--windowed',
            '--name', name, '--distpath', str(work/'dist'), '--workpath', str(work/'build'),
            '--specpath', str(work/'spec'), '--add-data', f'{root.resolve()}/TranslationData;TranslationData',
            '--add-binary', f'{root.resolve()}/{worker};.',
            '--add-binary', f'{root.resolve()}/Backend/XEditLib.dll;Backend']
    for asset in ['FalloutNV.Hardcoded.dat', 'icudtl.dat', 'LICENSE']:
        args += ['--add-data', f'{root.resolve()}/Backend/{asset};Backend']
    subprocess.run(args + [source], check=True)
    exe = work / 'dist' / (name + '.exe')
    verify(base_exe, exe)
    # Windowed installers must finish successfully, not just start a process.
    subprocess.run([str(exe.resolve()), '--package-check'], check=True, timeout=120,
                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    assets = []
    if is_ns:
        path = output / f'NuclearSunset-Korean-Patcher-v{version}.zip'
        with zipfile.ZipFile(base) as original, zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as dest:
            for entry in original.namelist():
                dest.writestr(entry, exe.read_bytes() if entry == name+'.exe' else original.read(entry))
        assets.append(path)
        path = output / f'NuclearSunset-TranslationData-v{version}.zip'
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as dest:
            for p in sorted((root/'TranslationData').rglob('*')):
                if p.is_file():
                    dest.write(p, 'TranslationData/'+p.relative_to(root/'TranslationData').as_posix())
        assets.append(path)
        for p in assets:
            with zipfile.ZipFile(p) as archive:
                if archive.testzip():
                    raise ValueError('Corrupt output ZIP')
    else:
        path = output / f'VNVKoreanPatcher-v{version}.exe'
        shutil.copyfile(exe, path)
        assets.append(path)
    (output/'SHA256SUMS.txt').write_text(''.join(
        f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in assets), encoding='ascii')
    print('PASS: built and verified release', version)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--base', type=Path, required=True)
    p.add_argument('--sha256', required=True)
    p.add_argument('--project', choices=['vnv', 'ns'], required=True)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    build(args.base, args.sha256, args.project, args.work, args.output)
