"""Set UTF-8 ACP on a LOCAL Node copy using Microsoft's manifest tool.

Never edits the installed Node or Windows locale. Needed because XEditLib
uses the process ANSI code page for inline, nonlocalized FNV plugin text.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

parser = argparse.ArgumentParser()
parser.add_argument('--node', type=Path, default=Path('C:/Program Files/nodejs/node.exe'))
parser.add_argument('--mt', type=Path, default=Path('C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64/mt.exe'))
parser.add_argument('--output', type=Path, default=Path('.tools/yesman-node-utf8'))
parser.add_argument('--codepage', choices=['UTF-8', 'en-US'], default='UTF-8')
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
source_hash = hashlib.sha256(args.node.read_bytes()).hexdigest()
copied = (args.output / 'node.exe').resolve()
if copied == args.node.resolve():
    raise ValueError('Never alter the installed Node runtime')
shutil.copyfile(args.node, copied)
original = (args.output / 'original.manifest').resolve()
modified = (args.output / 'utf8.manifest').resolve()
subprocess.run([str(args.mt), f'-inputresource:{copied};#1', f'-out:{original}'], check=True)
tree = ET.parse(original)
application = ET.SubElement(tree.getroot(), '{urn:schemas-microsoft-com:asm.v3}application')
settings = ET.SubElement(application, '{urn:schemas-microsoft-com:asm.v3}windowsSettings')
ET.SubElement(settings, '{http://schemas.microsoft.com/SMI/2019/WindowsSettings}activeCodePage').text = args.codepage
tree.write(modified, encoding='utf-8', xml_declaration=True)
subprocess.run([str(args.mt), '-manifest', str(modified), f'-outputresource:{copied};#1'], check=True)
assert hashlib.sha256(args.node.read_bytes()).hexdigest() == source_hash
report = {'source': str(args.node.resolve()), 'source_sha256': source_hash,
          'local_copy': str(copied), 'local_copy_sha256': hashlib.sha256(copied.read_bytes()).hexdigest(),
          'codepage': args.codepage + ' process manifest', 'system_locale_modified': False,
          'reference': 'https://learn.microsoft.com/en-us/windows/apps/design/globalizing/use-utf8-code-page'}
(args.output / 'runtime.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False))
