"""Download font research candidates into staging; never install or bundle them."""
from pathlib import Path
import hashlib
import html
import json
import re
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1] / 'staging/font-source-candidates'


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'VNV-KR-font-research/1.0'})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def main():
    from fontTools.ttLib import TTFont
    ROOT.mkdir(parents=True, exist_ok=True)
    author_page = fetch('https://cactus.tistory.com/193').decode('utf-8')
    dung_url = next(html.unescape(u) for u in re.findall(r'href="([^"]+)"', author_page)
                    if 'DungGeunMo%20TTF.zip' in u)
    sources = [
        ('NanumSquare', 'https://hangeul.naver.com/hangeul_static/webfont/zips/nanum-square.zip',
         'https://hangeul.naver.com/fonts/search?f=nanum', 'official', 'license required'),
        ('DungGeunMo', dung_url, 'https://cactus.tistory.com/193', 'author', 'public domain per author'),
        ('TmonMonsori', 'https://raw.githubusercontent.com/withstep/TmonMonsori/master/TmonMonsoriBlack.ttf',
         'https://github.com/withstep/TmonMonsori', 'third-party mirror', 'research only; original license needed'),
        ('Monofonto-current', 'https://dl.dafont.com/dl/?f=monofonto',
         'https://www.dafont.com/monofonto.font', 'author listing', 'research only; current license excludes font sharing and game embedding'),
    ]
    result = []
    for name, url, page, provenance, license_note in sources:
        target = ROOT / name
        target.mkdir(exist_ok=True)
        payload = fetch(url)
        extension = '.zip' if payload[:2] == b'PK' else '.ttf'
        archive = target / ('source' + extension)
        archive.write_bytes(payload)
        if extension == '.zip':
            with zipfile.ZipFile(archive) as z:
                for member in z.infolist():
                    if member.is_dir():
                        continue
                    # Fonts and license documents only; flattened, no execution.
                    basename = member.filename.replace('\\', '/').split('/')[-1]
                    if Path(basename).suffix.lower() in ('.ttf', '.otf', '.txt', '.pdf', '.html', '.rtf'):
                        (target / basename).write_bytes(z.read(member))
        font_rows = []
        for file in sorted(target.iterdir()):
            if file.suffix.lower() not in ('.ttf', '.otf'):
                continue
            with TTFont(file) as font:
                cmap = font.getBestCmap()
                names = {str(i): sorted({n.toUnicode() for n in font['name'].names if n.nameID == i})
                         for i in (1, 2, 4, 5, 6, 13, 14)}
                font_rows.append({'file': str(file), 'sha256': hashlib.sha256(file.read_bytes()).hexdigest(),
                                  'names': names, 'hangul_syllables': sum(c in cmap for c in range(0xAC00, 0xD7A4)),
                                  'weight': font['OS/2'].usWeightClass})
        result.append({'family': name, 'source_page': page, 'provenance': provenance,
                       'license_note': license_note, 'source_sha256': hashlib.sha256(payload).hexdigest(),
                       'fonts': font_rows})
        print(name, len(font_rows), 'fonts prepared')
    (ROOT / 'manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
