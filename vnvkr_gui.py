"""Small local Output generator. No game/MO2 installation writes."""
from datetime import datetime
import os
from pathlib import Path
import queue
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import vnvkr
from vnvkr_output import build_output


def program_folder():
    return Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent


class App:
    def __init__(self, window):
        self.window = window
        self.folder = program_folder()
        self.events = queue.Queue()
        self.output = None
        window.title(f'Viva New Vegas 한국어 패쳐 v{vnvkr.VERSION}')
        window.minsize(660, 240)
        frame = ttk.Frame(window, padding=22)
        frame.pack(fill='both', expand=True)
        frame.columnconfigure(0, weight=1)
        ttk.Label(frame, text='비바 뉴 베가스 MO2 폴더').grid(row=0, column=0, columnspan=2, sticky='w')
        default = 'C:/Modlists/VNV' if Path('C:/Modlists/VNV/ModOrganizer.ini').is_file() else ''
        self.mo2 = tk.StringVar(value=default)
        ttk.Entry(frame, textvariable=self.mo2).grid(row=1, column=0, sticky='ew', pady=(6, 16))
        self.browse = ttk.Button(frame, text='찾아보기', command=self.choose)
        self.browse.grid(row=1, column=1, padx=(8, 0), pady=(6, 16))
        self.generate = ttk.Button(frame, text='Output 생성', command=self.start)
        self.generate.grid(row=2, column=0, sticky='w')
        self.open_button = ttk.Button(frame, text='Output 폴더 열기', command=self.open_output, state='disabled')
        self.open_button.grid(row=2, column=1)
        self.status = tk.StringVar(value='Output 안의 mods 폴더를 선택한 MO2 폴더로 복사하면 됩니다.')
        ttk.Label(frame, textvariable=self.status, wraplength=600, justify='left').grid(
            row=3, column=0, columnspan=2, sticky='w', pady=(18, 0))
        window.after(150, self.poll)

    def choose(self):
        folder = filedialog.askdirectory(title='ModOrganizer.ini가 있는 VNV 폴더 선택')
        if folder:
            self.mo2.set(folder)

    def start(self):
        root = Path(self.mo2.get().strip())
        if not (root / 'ModOrganizer.ini').is_file():
            messagebox.showerror('폴더 확인', 'ModOrganizer.ini가 있는 VNV MO2 폴더를 선택해주세요.')
            return
        catalog = self.folder / 'TranslationData'
        if not (catalog / 'catalog.json').is_file():
            catalog = self.folder / 'bundles/records-release-20261003'
            if not (catalog / 'catalog.json').is_file():
                messagebox.showerror('번역 데이터 확인', '검증된 TranslationData 폴더가 필요합니다. 패쳐와 함께 제공된 파일을 확인해주세요.')
                return
        target = self.folder / 'Output'
        if target.exists() or target.with_name(target.name + '.report.json').exists():
            target = self.folder / ('Output-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        self.generate.configure(state='disabled')
        self.browse.configure(state='disabled')
        self.open_button.configure(state='disabled')
        self.status.set('선택한 프로필의 원본을 읽고 Output을 생성하고 있습니다.')

        def run():
            try:
                report = build_output(vnvkr.Installation(root), catalog, target)
                self.events.put(('done', target, report))
            except Exception as error:
                self.events.put(('error', str(error)))
        threading.Thread(target=run, daemon=True).start()

    def poll(self):
        try:
            event = self.events.get_nowait()
        except queue.Empty:
            pass
        else:
            self.generate.configure(state='normal')
            self.browse.configure(state='normal')
            if event[0] == 'error':
                self.status.set('Output 생성에 실패했습니다. 원본 설치는 변경하지 않았습니다.')
                messagebox.showerror('생성 실패', event[1])
            else:
                _, self.output, report = event
                unmatched = sum(row.get('unmatched', 0) for row in report['files'])
                fonts = report.get('fonts', {})
                activation = (f'\nMO2에서 "{fonts["mod"]}" 모드를 체크하고 tNVSE보다 아래에 배치해주세요.'
                              if fonts.get('requires_activation') else '')
                extra = set(report.get('assets', {}).get('mods_requiring_activation', []))
                runtime = report.get('runtime_mods', {})
                extra.update(runtime.get('mods_requiring_activation', []))
                if fonts.get('requires_activation'):
                    extra.discard(fonts['mod'])
                if extra:
                    activation += '\nMO2에서 다음 번역 모드도 체크해주세요: ' + ', '.join(sorted(extra))
                plugins = runtime.get('plugins_requiring_activation', [])
                if plugins:
                    activation += '\nMO2 플러그인 목록에서 다음 ESP도 체크해주세요: ' + ', '.join(plugins)
                self.status.set(f"{len(report['files'])}개 파일 생성 완료 · 미대응 항목 {unmatched}개 · 제외 파일 {len(report['skipped'])}개\n"
                                f"{self.output}\nOutput 안의 mods 폴더를 선택한 MO2 폴더로 복사해주세요.{activation}")
                self.open_button.configure(state='normal')
        self.window.after(150, self.poll)

    def open_output(self):
        if self.output:
            os.startfile(self.output)


def packaged_self_test(mo2_root):
    folder = program_folder()
    catalog = folder / 'TranslationData'
    if not (catalog / 'catalog.json').is_file():
        raise FileNotFoundError('TranslationData/catalog.json')
    metadata = vnvkr.read_json(catalog / 'catalog.json')
    native = [entry for entry in metadata['files'] if entry.get('kind') == 'plugin-records']
    verified = [entry for entry in native if entry.get('verified_delta')]
    if len(verified) != len(native) or metadata.get('verified_delta_files') != len(verified):
        raise RuntimeError('Packaged release is missing one or more verified fast deltas')
    for entry in verified:
        spec = entry['verified_delta']
        payload = vnvkr.contained(catalog, spec['payload'])
        if not payload.is_file() or vnvkr.sha256(payload) != spec['payload_sha256']:
            raise RuntimeError(f'Packaged verified delta is missing/corrupt: {entry["path"]}')
    for required in ('Backend/xdelta3.exe', 'Backend/node.exe', 'Backend/node-1252.exe',
                     'Backend/yesman_text.cjs', 'Backend/node_modules/xeditlib/XEditLib.dll'):
        if not (folder / required).is_file():
            raise FileNotFoundError(required)
    with tempfile.TemporaryDirectory(prefix='vnvkr-packaged-selftest-') as tmp:
        output = Path(tmp) / 'Output'
        report = build_output(vnvkr.Installation(Path(mo2_root)), catalog, output)
        fast = sum(row.get('status') == 'exact_source_verified_delta' for row in report['files'])
        if fast < 1 or not output.is_dir():
            raise RuntimeError(f'Packaged fast path did not complete: {fast}')
    return 0


if __name__ == '__main__':
    if len(sys.argv) >= 3 and sys.argv[1] == '--self-test':
        raise SystemExit(packaged_self_test(sys.argv[2]))
    window = tk.Tk()
    App(window)
    window.mainloop()
