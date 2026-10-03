"""Version-pinned VNV translation deltas. Plugin contents are opaque bytes.

Translation and record validation belong to xTranslator/xEdit, not this tool.
"""
from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

VERSION = "1.0.0"
ROOT = Path(__file__).resolve().parent
RESERVED = {"meta.ini", ".vnv-kr-report.json"}
HASH = re.compile(r"[0-9a-f]{64}\Z")


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def virtual_path(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"Use a non-empty relative path with / separators: {value!r}")
    parts = value.split("/")
    devices = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
               *(f"lpt{i}" for i in range(1, 10))}
    if PurePosixPath(value).is_absolute() or any(
        p in ("", ".", "..") or p.endswith((".", " "))
        or any(c in p for c in '<>:"|?*') or any(ord(c) < 32 for c in p)
        or p.split(".")[0].casefold() in devices for p in parts
    ):
        raise ValueError(f"Unsafe relative path: {value!r}")
    if value.casefold() in RESERVED:
        raise ValueError(f"Reserved output path: {value}")
    return value


def contained(root: Path, relative: str) -> Path:
    result = (root / virtual_path(relative)).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError(f"Path escapes root: {relative}")
    return result


def qt_value(value: str) -> str:
    value = value.strip().strip('"')
    for wrapper in ("@ByteArray(", "@String("):
        if value.startswith(wrapper) and value.endswith(")"):
            value = value[len(wrapper):-1]
    return value.replace("\\\\", "\\")


def list_lines(path: Path, encoding="utf-8-sig") -> list[str]:
    return [line.strip() for line in path.read_text(encoding=encoding).splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


class Installation:
    """Offline loose-file provider inventory; does not claim live VFS proof."""

    def __init__(self, root: Path, profile: str | None = None, game_dir: Path | None = None):
        self.root = root.resolve()
        config = configparser.ConfigParser(interpolation=None, strict=False)
        config.read_string((self.root / "ModOrganizer.ini").read_text(encoding="utf-8-sig"))
        general = config["General"]
        game = qt_value(general.get("gameName", "")).casefold()
        if game not in {"fallout new vegas", "fallout: new vegas", "falloutnv", "new vegas", "newvegas"}:
            raise ValueError(f"This is not a New Vegas MO2 instance: {game!r}")
        self.profile = profile or qt_value(general.get("selected_profile", ""))
        if not self.profile or Path(self.profile).name != self.profile or self.profile in (".", ".."):
            raise ValueError("Choose a valid --profile explicitly")
        settings = config["Settings"] if config.has_section("Settings") else {}
        base_value = qt_value(settings.get("base_directory", str(self.root)))
        base_value = base_value.replace("%BASE_DIR%", str(self.root))
        base_path = Path(base_value)
        self.base = (base_path if base_path.is_absolute() else self.root / base_path).resolve()

        def configured(key: str, default: str) -> Path:
            value = qt_value(settings.get(key, default))
            value = value.replace("%BASE_DIR%", str(self.base))
            path = Path(value)
            return (path if path.is_absolute() else self.root / path).resolve()

        self.mods = configured("mod_directory", "%BASE_DIR%/mods")
        self.profiles = configured("profiles_directory", "%BASE_DIR%/profiles")
        self.overwrite = configured("overwrite_directory", "%BASE_DIR%/overwrite")
        configured_game = qt_value(general.get("gamePath", ""))
        if not game_dir and not configured_game:
            raise ValueError("MO2 gamePath is absent; supply --game-dir")
        self.game = (game_dir or Path(configured_game)).resolve()
        self.data = self.game / "Data"
        if not (self.data / "FalloutNV.esm").is_file():
            raise ValueError(f"FalloutNV.esm is missing: {self.data}")
        self.profile_dir = contained(self.profiles, self.profile)
        self.warnings: list[str] = []
        self.providers: dict[str, list[dict]] = {}
        self.mods_enabled: list[str] = []
        self.archives: list[dict] = []
        self.scan()

    def add_tree(self, root: Path, provider: str):
        if not root.is_dir():
            self.warnings.append(f"Provider directory is missing: {root}")
            return
        seen = set()
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            suffix = path.suffix.casefold()
            if suffix == ".bsa":
                self.archives.append({"provider": provider, "path": relative, "size": path.stat().st_size})
                continue
            category = "plugin" if suffix in {".esm", ".esp"} and "/" not in relative else (
                "loose_text_candidate" if suffix in {".xml", ".json", ".ini", ".txt", ".csv"}
                and relative.casefold().startswith(("menus/", "nvse/", "config/", "mcm/")) else None)
            if category is None:
                continue
            virtual_path(relative)
            key = relative.casefold()
            if key in seen:
                raise ValueError(f"Case-insensitive filename collision in {root}: {relative}")
            seen.add(key)
            resolved = contained(root, relative)
            self.providers.setdefault(key, []).append({"path": relative, "provider": provider,
                                                      "physical": str(resolved), "category": category})

    def scan(self):
        self.add_tree(self.data, "game:Data")
        # MO2 persists modlist in descending priority: first enabled entry wins.
        for line in reversed(list_lines(self.profile_dir / "modlist.txt")):
            if line.startswith("+") and not line.endswith("_separator"):
                name = virtual_path(line[1:])
                if "/" in name:
                    raise ValueError(f"Invalid MO2 mod name: {name}")
                self.mods_enabled.append(name)
                self.add_tree(contained(self.mods, name), name)
            elif line.startswith("*"):
                self.warnings.append(f"Foreign mod requires live VFS confirmation: {line[1:]}")
        if self.overwrite.is_dir():
            self.add_tree(self.overwrite, "MO2:overwrite")
        active = list_lines(self.profile_dir / "plugins.txt", "cp1252")
        if any(name.startswith("*") for name in active):
            raise ValueError("New Vegas plugins.txt is legacy format: no * activation markers")
        active = [virtual_path(name) for name in active]
        if any("/" in name or Path(name).suffix.casefold() not in {".esm", ".esp"} for name in active):
            raise ValueError("Invalid plugin name in plugins.txt")
        if len({name.casefold() for name in active}) != len(active):
            raise ValueError("Duplicate active plugin names")
        # The primary game master may be omitted by the profile writer.
        if "falloutnv.esm" not in {name.casefold() for name in active}:
            active.insert(0, "FalloutNV.esm")
        loadorder_file = self.profile_dir / "loadorder.txt"
        order = list_lines(loadorder_file, "utf-8-sig") if loadorder_file.is_file() else []
        if not order:
            self.warnings.append("loadorder.txt is absent/empty; record order is unverified")
        ranks = {name.casefold(): i for i, name in enumerate(order)}
        self.active = sorted(active, key=lambda n: ranks.get(n.casefold(), -1))
        self.active_keys = {name.casefold() for name in self.active}
        for name in self.active:
            if name.casefold() not in self.providers:
                self.warnings.append(f"Active plugin has no loose provider: {name}")
            if order and name.casefold() not in ranks:
                self.warnings.append(f"Active plugin is absent from loadorder.txt: {name}")

    def source(self, relative: str) -> Path:
        key = virtual_path(relative).casefold()
        chain = self.providers.get(key)
        if not chain:
            raise ValueError(f"No enabled loose-file provider: {relative}")
        if chain[-1]["category"] == "plugin" and key not in self.active_keys:
            raise ValueError(f"Plugin is inactive: {relative}")
        return Path(chain[-1]["physical"])

    def inventory(self) -> dict:
        files = []
        for key, chain in sorted(self.providers.items()):
            winner = chain[-1]
            source = Path(winner["physical"])
            files.append({**winner, "size": source.stat().st_size, "sha256": sha256(source),
                          "active": key in self.active_keys if winner["category"] == "plugin" else None,
                          "provider_chain": [row["provider"] for row in chain],
                          "translation_status": "not_audited"})
        return {"schema_version": 1, "tool_version": VERSION, "mo2_root": str(self.root),
                "profile": self.profile, "game_dir": str(self.game), "active_plugins": self.active,
                "enabled_mods_low_to_high": self.mods_enabled, "files": files, "archives": self.archives,
                "warnings": self.warnings, "validation": "offline_loose_files_only",
                "notes": ["BSA text, root-builder files and plugin records are not inspected.",
                          "Provider order does not establish record winners or translation coverage."]}

    def guard_output(self, output: Path):
        output = output.resolve()
        if output.exists():
            raise FileExistsError(f"Use a new output directory: {output}")
        for protected in (self.game, self.profiles, self.overwrite):
            if output.is_relative_to(protected) or protected.is_relative_to(output):
                raise ValueError(f"Output overlaps protected tree: {protected}")
        if output.is_relative_to(self.root):
            if output.parent != self.mods:
                raise ValueError("Output inside MO2 must be a new direct child of mods")
        if output.is_relative_to(self.mods) and output.parent != self.mods:
            raise ValueError("Do not write into an existing source mod")
        for chain in self.providers.values():
            for row in chain:
                if Path(row["physical"]).is_relative_to(output):
                    raise ValueError("Output contains a source file")


def engine(explicit: Path | None) -> Path:
    program = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else ROOT
    candidates = [explicit] if explicit else [
        program / 'Backend/xdelta3.exe',
        ROOT / ".tools/xdelta3-3.2.0-windows-x86_64/xdelta3.exe",
        Path(shutil.which("xdelta3") or "__missing_xdelta3__")]
    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError("xdelta3 is absent; run tools/setup_xdelta.ps1 or supply --xdelta")


def delta(executable: Path, mode: str, source: Path, input_file: Path, output: Path):
    env = os.environ.copy()
    env.pop("XDELTA", None)
    # Process exact bytes, suppress source-name headers; never force an overwrite.
    options = ["-e", "-A", "-D"] if mode == "encode" else ["-d", "-D", "-R"]
    result = subprocess.run([str(executable), *options, "-s", str(source), str(input_file), str(output)],
                            capture_output=True, env=env, timeout=600)
    if result.returncode:
        raise ValueError(f"xdelta3 {mode} failed: {result.stderr.decode('utf-8', errors='replace').strip()}")


def validate_entries(entries):
    if not isinstance(entries, list) or not entries:
        raise ValueError("No translation deltas: empty bundles cannot be built/applied")
    seen = set()
    for entry in entries:
        key = virtual_path(entry["path"]).casefold()
        if key in seen or any(key.startswith(k + "/") or k.startswith(key + "/") for k in seen):
            raise ValueError(f"Duplicate/overlapping output path: {entry['path']}")
        seen.add(key)


def build_bundle(installation: Installation, spec_path: Path, translated: Path,
                 output: Path, executable: Path):
    spec = read_json(spec_path)
    if not isinstance(spec, dict) or spec.get("schema_version") != 1 or spec.get("scope") not in {"base", "extended"}:
        raise ValueError("Spec must have schema_version=1 and scope=base or extended")
    entries = spec["files"]
    validate_entries(entries)
    installation.guard_output(output)
    if translated.resolve().is_relative_to(output.resolve()) or output.resolve().is_relative_to(translated.resolve()):
        raise ValueError("Bundle output overlaps translated staging")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".vnvkr-build-", dir=output.parent) as temp:
        temp = Path(temp)
        bundle = temp / "bundle"
        (bundle / "deltas").mkdir(parents=True)
        (bundle / "reviews").mkdir()
        manifest = {"schema_version": 1, "tool_version": VERSION, "scope": spec["scope"],
                    "files": [], "runtime_validation": "not_tested"}
        for i, entry in enumerate(entries):
            relative = virtual_path(entry["path"])
            source = installation.source(relative)
            target = contained(translated, relative)
            review = contained(spec_path.parent, entry["review"])
            if not review.is_file() or not review.stat().st_size:
                raise ValueError(f"A non-empty review evidence file is required: {review}")
            source_hash, target_hash = sha256(source), sha256(target)
            if source_hash == target_hash:
                raise ValueError(f"Translation is identical to source: {relative}")
            patch_name = f"deltas/{i:04d}.vcdiff"
            patch = bundle / patch_name
            delta(executable, "encode", source, target, patch)
            check = temp / f"{i:04d}.roundtrip"
            delta(executable, "decode", source, patch, check)
            if sha256(check) != target_hash or sha256(target) != target_hash or sha256(source) != source_hash:
                raise ValueError(f"Roundtrip mismatch or input changed during build: {relative}")
            evidence_name = f"reviews/{i:04d}.txt"
            shutil.copyfile(review, bundle / evidence_name)
            manifest["files"].append({"path": relative, "source_sha256": source_hash,
                                      "target_sha256": target_hash, "target_size": target.stat().st_size,
                                      "delta": patch_name, "delta_sha256": sha256(patch),
                                      "review": evidence_name, "review_sha256": sha256(bundle / evidence_name)})
        write_json(bundle / "manifest.json", manifest)
        installation.guard_output(output)
        bundle.rename(output)
    return manifest


def preflight(installation: Installation, bundle: Path):
    manifest = read_json(bundle / "manifest.json")
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1 or manifest.get("scope") not in {"base", "extended"}:
        raise ValueError("Unsupported bundle schema/scope")
    validate_entries(manifest["files"])
    rows = []
    for entry in manifest["files"]:
        for name in ("source_sha256", "target_sha256", "delta_sha256", "review_sha256"):
            if not isinstance(entry[name], str) or not HASH.fullmatch(entry[name]):
                raise ValueError(f"Invalid {name}: {entry['path']}")
        if type(entry["target_size"]) is not int or entry["target_size"] < 0:
            raise ValueError("Invalid target_size")
        source = installation.source(entry["path"])
        patch = contained(bundle, entry["delta"])
        review = contained(bundle, entry["review"])
        if sha256(source) != entry["source_sha256"]:
            raise ValueError(f"Source version differs; rebuild for this installation: {entry['path']}")
        if sha256(patch) != entry["delta_sha256"] or sha256(review) != entry["review_sha256"]:
            raise ValueError(f"Bundle integrity mismatch: {entry['path']}")
        rows.append((entry, source, patch))
    return manifest, rows


def apply_bundle(installation: Installation, bundle: Path, output: Path, executable: Path):
    installation.guard_output(output)
    manifest, rows = preflight(installation, bundle)
    if output.resolve().is_relative_to(bundle.resolve()) or bundle.resolve().is_relative_to(output.resolve()):
        raise ValueError("Output overlaps the patch bundle")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".vnvkr-apply-", dir=output.parent) as temp:
        stage = Path(temp) / "mod"
        stage.mkdir()
        for entry, source, patch in rows:
            target = contained(stage, entry["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            delta(executable, "decode", source, patch, target)
            if target.stat().st_size != entry["target_size"] or sha256(target) != entry["target_sha256"]:
                raise ValueError(f"Reconstructed translation differs: {entry['path']}")
        for entry, source, patch in rows:
            if sha256(source) != entry["source_sha256"] or sha256(patch) != entry["delta_sha256"]:
                raise ValueError(f"Input changed during patching: {entry['path']}")
        report = {"tool_version": VERSION, "scope": manifest["scope"], "profile": installation.profile,
                  "created_at": datetime.now(timezone.utc).isoformat(), "files": manifest["files"],
                  "byte_validation": "passed", "runtime_validation": "not_tested",
                  "inventory_warnings": installation.warnings,
                  "manifest_sha256": sha256(bundle / "manifest.json")}
        write_json(stage / ".vnv-kr-report.json", report)
        (stage / "meta.ini").write_text(f"[General]\nversion={VERSION}\ncomments=VNV Korean translation delta overlay\n", encoding="utf-8")
        installation.guard_output(output)
        stage.rename(output)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="VNV 한국어 번역 패쳐")
    parser.add_argument("command", choices=("inventory", "build", "check", "apply"))
    parser.add_argument("--mo2-root", required=True, type=Path)
    parser.add_argument("--profile")
    parser.add_argument("--game-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--spec", type=Path)
    parser.add_argument("--translated-dir", type=Path)
    parser.add_argument("--xdelta", type=Path)
    args = parser.parse_args(argv)
    required = {"inventory": ["output"], "build": ["output", "spec", "translated_dir"],
                "check": ["bundle"], "apply": ["bundle", "output"]}[args.command]
    for name in required:
        if getattr(args, name) is None:
            parser.error(f"{args.command} requires --{name.replace('_', '-')}")
    installation = Installation(args.mo2_root, args.profile, args.game_dir)
    if args.command == "inventory":
        installation.guard_output(args.output)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(installation.inventory(), stream, ensure_ascii=False, indent=2)
        result = {"inventory": str(args.output), "active_plugins": len(installation.active),
                  "warnings": installation.warnings}
    elif args.command == "build":
        result = build_bundle(installation, args.spec, args.translated_dir, args.output, engine(args.xdelta))
    elif args.command == "check":
        manifest, rows = preflight(installation, args.bundle)
        result = {"source_and_bundle_validation": "passed", "scope": manifest["scope"], "files": len(rows),
                  "note": "check verifies inputs only; apply also verifies decoded bytes"}
    else:
        result = apply_bundle(installation, args.bundle, args.output, engine(args.xdelta))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, configparser.Error, subprocess.SubprocessError) as error:
        print(f"실패: {error}", file=sys.stderr)
        raise SystemExit(1)
