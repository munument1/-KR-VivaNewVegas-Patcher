"""Copy VNV translation inputs into an isolated, provenance-backed workspace.

Never interprets plugin records, translates text, or modifies MO2/game state.
"""
from __future__ import annotations

import argparse
import configparser
import csv
import json
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vnvkr import Installation, contained, sha256, write_json

TEXT = {".txt", ".ini", ".xml", ".json", ".csv", ".gek", ".strings", ".dlstrings", ".ilstrings"}


def category(relative: str):
    path = Path(relative)
    parts = relative.casefold().replace("\\", "/").split("/")
    suffix = path.suffix.casefold()
    if suffix not in TEXT:
        return None
    if any(part in {"translations", "translation", "localization", "strings"} for part in parts) or "translations" in path.stem.casefold():
        return "03_Translations"
    if any(part in {"mcm", "mcmextender"} for part in parts) or "mcm" in path.stem.casefold():
        return "02_MCM"
    if (parts[0] == "menus" and suffix == ".xml") or (
        parts[0] == "nvse" and any(part in {"scripts", "user_defined_functions"} for part in parts)
        and suffix in {".txt", ".gek"}
    ):
        return "04_UI_Scripts_Reference"
    return None


def archive_command(executable: Path, command: str, archive: Path, *options):
    result = subprocess.run([str(executable), "--json", command, str(archive),
                             "--allow-game-data", *map(str, options)], capture_output=True, timeout=180)
    try:
        value = json.loads(result.stdout.decode("utf-8-sig"))
    except (UnicodeError, ValueError):
        raise ValueError(f"Invalid archive tool response: {archive}") from None
    if result.returncode or not value.get("ok"):
        raise ValueError(f"Archive inspection failed: {archive}: {value.get('error')}")
    return value["data"]


def collect(mo2_root: Path, output: Path, archive_tool: Path):
    selected = Installation(mo2_root)
    profile_names = [p.name for p in selected.profiles.iterdir()
                     if p.is_dir() and (p / "modlist.txt").is_file() and (p / "plugins.txt").is_file()]
    installations = {name: Installation(mo2_root, name) for name in profile_names}
    if output.exists():
        raise FileExistsError(f"Use a new folder: {output}")
    selected.guard_output(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    rows, archive_reports, mods = [], [], set()
    winners = {}
    mod_profiles = {}
    for name, install in installations.items():
        for mod in install.mods_enabled:
            mods.add(mod)
            mod_profiles.setdefault(mod, []).append(name)
        mapping = {}
        trees = [("game:Data", install.data), *[(mod, contained(install.mods, mod)) for mod in install.mods_enabled]]
        if install.overwrite.is_dir():
            trees.append(("MO2:overwrite", install.overwrite))
        for provider, tree in trees:
            for path in tree.rglob("*"):
                if path.is_file():
                    relative = path.relative_to(tree).as_posix()
                    if category(relative):
                        mapping[relative.casefold()] = str(path.resolve())
        winners[name] = mapping
    with tempfile.TemporaryDirectory(prefix=".vnv-collection-", dir=output.parent) as temp:
        stage = Path(temp) / "workspace"
        stage.mkdir()

        def copy(source: Path, relative_output: str, kind: str, provider: str, data_path: str,
                 active_profiles=None, winning_profiles=None, archive_entry=None):
            destination = contained(stage, relative_output)
            if destination.exists():
                raise ValueError(f"Duplicate collection output: {relative_output}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            digest = sha256(source)
            shutil.copy2(source, destination)
            if sha256(destination) != digest or sha256(source) != digest:
                raise ValueError(f"Copy mismatch or source changed: {source}")
            rows.append({"category": kind, "output": relative_output, "data_path": data_path,
                         "provider": provider, "source": str(source), "source_archive_entry": archive_entry,
                         "size": destination.stat().st_size, "sha256": digest,
                         "enabled_profiles": active_profiles or [], "loose_winner_profiles": winning_profiles or []})

        plugin_keys = set()
        for name, install in installations.items():
            for plugin in install.active:
                plugin_keys.add(plugin.casefold())
        # Flat effective selected-profile plugin set, including Fixed ESMs.
        selected_paths = {}
        for plugin in selected.active:
            source = selected.source(plugin)
            provider = selected.providers[plugin.casefold()][-1]["provider"]
            selected_paths[plugin.casefold()] = source
            active = [name for name, install in installations.items()
                      if plugin.casefold() in install.active_keys and install.source(plugin) == source]
            copy(source, f"01_Plugins/{plugin}", "01_Plugins", provider, plugin, active, active)
        for name, install in installations.items():
            for plugin in install.active:
                source = install.source(plugin)
                if source == selected_paths.get(plugin.casefold()):
                    continue
                copy(source, f"99_Optional_Plugins/ProfileVariants/{name}/{plugin}", "99_Optional_Plugins",
                     install.providers[plugin.casefold()][-1]["provider"], plugin, [name], [name])

        archives = []
        for mod_dir in sorted(selected.mods.iterdir()):
            if not mod_dir.is_dir() or mod_dir.name.endswith("_separator"):
                continue
            mod = mod_dir.name
            enabled = mod_profiles.get(mod, [])
            for path in sorted(mod_dir.rglob("*")):
                if not path.is_file():
                    continue
                relative = path.relative_to(mod_dir).as_posix()
                suffix = path.suffix.casefold()
                if suffix in {".esp", ".esm"} and "/" not in relative:
                    if not any(relative.casefold() in install.active_keys and install.source(relative) == path.resolve()
                               for install in installations.values()):
                        copy(path, f"99_Optional_Plugins/InstalledVariants/{mod}/{relative}", "99_Optional_Plugins",
                             mod, relative, enabled)
                    continue
                if not enabled:
                    continue
                kind = category(relative)
                if kind:
                    win = [name for name, mapping in winners.items()
                           if mapping.get(relative.casefold()) == str(path.resolve())]
                    copy(path, f"{kind}/{mod}/{relative}", kind, mod, relative, enabled, win)
                if suffix == ".bsa":
                    archives.append((mod, path, enabled))
            if enabled and (mod_dir / "meta.ini").is_file():
                copy(mod_dir / "meta.ini", f"05_Reference/ModMetadata/{mod}/meta.ini", "05_Reference", mod,
                     "meta.ini", enabled)
        # Overwrite text and loose game MCM/translation references, if present.
        for provider, tree in (("Game_Data", selected.data), ("MO2_Overwrite", selected.overwrite)):
            if not tree.is_dir():
                continue
            for path in sorted(tree.rglob("*")):
                if path.is_file():
                    relative = path.relative_to(tree).as_posix()
                    kind = category(relative)
                    if kind:
                        copy(path, f"{kind}/{provider}/{relative}", kind, provider, relative)
        # Vanilla miscellaneous archives can hold menu text; meshes/textures/audio are not copied.
        for archive in selected.data.glob("*.bsa"):
            if archive.name.casefold() in {"fallout - misc.bsa", "update.bsa"}:
                archives.append(("Game_Data", archive, list(installations)))
        for provider, archive, enabled in archives:
            info = archive_command(archive_tool, "info", archive)
            entries = archive_command(archive_tool, "list", archive)
            matches = [entry["path"] for entry in entries if category(entry["path"])]
            record = {"provider": provider, "archive": str(archive), "info": info,
                      "matched_paths": matches, "enabled_profiles": enabled}
            archive_reports.append(record)
            for relative in matches:
                scratch = Path(temp) / "archive-extract" / str(len(rows))
                scratch.mkdir(parents=True)
                extracted = archive_command(archive_tool, "extract", archive, "--out", scratch, "--filter", relative)
                if extracted["extracted_count"] != 1:
                    raise ValueError(f"Unexpected archive extraction set: {archive}: {relative}")
                source = contained(scratch, relative.replace("\\", "/"))
                kind = category(relative)
                target = f"06_Archive_Text/{provider}/{archive.stem}/{relative.replace(chr(92), '/')}"
                copy(source, target, kind, provider, relative.replace("\\", "/"), enabled, archive_entry=relative)
                rows[-1]["source"] = str(archive)
        for name, install in installations.items():
            for filename in ("modlist.txt", "plugins.txt", "loadorder.txt"):
                source = install.profile_dir / filename
                if source.is_file():
                    copy(source, f"05_Reference/Profiles/{name}/{filename}", "05_Reference", name, filename)
        counts = dict(Counter(row["category"] for row in rows))
        manifest = {"schema_version": 1, "source_mo2": str(selected.root), "game_dir": str(selected.game),
                    "selected_profile": selected.profile, "profiles": profile_names, "created_on": "2026-10-03",
                    "counts": counts, "files": rows, "archives_inspected": archive_reports,
                    "profile_active_plugins": {name: install.active for name, install in installations.items()},
                    "validation": "byte-identical copies; no translation or record parsing",
                    "archive_winner_validation": "not_performed"}
        write_json(stage / "source_manifest.json", manifest)
        fields = ["category", "output", "provider", "data_path", "size", "sha256", "enabled_profiles",
                  "loose_winner_profiles", "source", "source_archive_entry"]
        with (stage / "source_manifest.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({**row, "enabled_profiles": " | ".join(row["enabled_profiles"]),
                                 "loose_winner_profiles": " | ".join(row["loose_winner_profiles"])})
        readme = f"""# VNV 번역 작업용 원본 모음

설치 경로: {selected.root}
기준 프로필: {selected.profile}
수집일: 2026-10-03. 파일은 원본과 같은 바이트로 복사했고 설치 상태는 수정하지 않았습니다.

## 작업 위치

- **01_Plugins**: 활성 Extended 플러그인 {len(selected.active)}개. ESP/ESM을 xTranslator 또는 ESP-ESM Translator로 열면 됩니다. 본편/DLC도 포함하며 VNV의 Fixed ESMs 파일을 사용합니다.
- **02_MCM**: MCM JSON/설정, MCM 및 MCM Extender UI/XML과 관련 스크립트. 모드 이름 아래 원래 Data 상대 경로를 유지합니다.
- **03_Translations**: MCM/Translations 및 config의 번역용 INI/문자열 파일. 번역할 값만 수정하고 키·토큰·참조 경로는 유지하세요.
- **04_UI_Scripts_Reference**: 메뉴 XML과 런타임 스크립트 참고본. 코드 전체를 번역하지 말고 화면에 표시되는 문구만 확인하세요.
- **05_Reference**: Base/Extended의 plugins/loadorder/modlist와 모드 출처·버전 meta.ini 복사본.
- **06_Archive_Text**: BSA에서 추출한 텍스트 후보가 있으면 모드/아카이브별로 보관합니다. 아카이브 간 최종 제공 순서는 아직 검증하지 않았습니다.
- **99_Optional_Plugins**: 비활성 또는 다른 제공 모드의 플러그인. 활성 목록과 구분해 두었습니다.

같은 Data 경로의 MCM/XML이 여러 모드에 있으면 source_manifest.csv의 **loose_winner_profiles**에 기준 프로필이 표시된 복사본을 먼저 작업하세요. 프로필당 파일 제공 순서의 정적 확인이며 플러그인 레코드 충돌 검증은 아닙니다.

플러그인은 기존 파일명, FormID, masters, 스크립트와 레코드 구조를 유지해서 문자열만 번역합니다. JSON은 displayName/description/title 등의 표시값, INI는 번역 문자열 값, XML/스크립트는 화면 문구만 대상으로 삼으세요. $로 시작하는 참조 키, % 포맷 기호, 변수·명령·경로를 바꾸지 않습니다.

이 모음에는 기존 한국어 원천이나 tNVSE 설정을 섞지 않았습니다. 설치된 영문 팩을 기준으로 새 번역을 만드는 작업용 복사본입니다. 이 폴더 전체를 MO2에 설치하지 말고 번역 결과만 별도 모드로 준비하세요.

파일별 원본 경로·제공 모드·프로필·SHA-256: source_manifest.csv 및 source_manifest.json.
"""
        (stage / "README.md").write_text(readme, encoding="utf-8")
        for folder in ("02_MCM", "03_Translations", "04_UI_Scripts_Reference", "06_Archive_Text"):
            (stage / folder).mkdir(exist_ok=True)
        # Final copied-file readback; source files and profile snapshots also must remain unchanged.
        for row in rows:
            if sha256(contained(stage, row["output"])) != row["sha256"]:
                raise ValueError(f"Final copy readback failed: {row['output']}")
            if row["source_archive_entry"] is None and sha256(Path(row["source"])) != row["sha256"]:
                raise ValueError(f"Source changed while collecting: {row['source']}")
        stage.rename(output)
    return {"output": str(output), "selected_profile": selected.profile, "counts": counts,
            "archives_inspected": len(archive_reports), "archive_text_files": sum(len(r["matched_paths"]) for r in archive_reports),
            "files_copied": len(rows), "bytes_copied": sum(row["size"] for row in rows)}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--mo2-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive-tool", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(collect(args.mo2_root, args.output.resolve(), args.archive_tool), ensure_ascii=False, indent=2))
