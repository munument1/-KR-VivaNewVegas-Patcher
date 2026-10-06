"""MO2 provider discovery and shared path/hash helpers for VNV Korean Patcher.

Plugin translation is handled by the SST/XEditLib backend in vnvkr_xedit.py.
"""
from __future__ import annotations

import configparser
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

VERSION = "1.0.6"
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
                and relative.casefold().startswith(
                    ("menus/", "nvse/", "config/", "mcm/", "interface/")) else None)
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
        # Mirror MO2/VFS provider order: the real game Data directory is the
        # lowest-priority provider, then enabled MO2 mods override it. This is
        # required for stock VNV because the four preorder pack ESMs remain only
        # in game Data, while FalloutNV.esm and the main DLC ESMs are overridden
        # by the enabled Fixed ESMs mod.
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
