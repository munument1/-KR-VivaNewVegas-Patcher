import json
import tempfile
import unittest
from pathlib import Path

import vnvkr


class PatcherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="VNV 한글 시험 ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.mo2 = self.root / "MO2"
        self.game = self.root / "Game"
        self.data = self.game / "Data"
        self.data.mkdir(parents=True)
        # Synthetic placeholders, deliberately not Bethesda plugin records.
        (self.data / "FalloutNV.esm").write_bytes(b"synthetic primary-master placeholder")
        self.profile = self.mo2 / "profiles/Extended"
        self.profile.mkdir(parents=True)
        (self.mo2 / "ModOrganizer.ini").write_text(
            f"[General]\ngameName=Fallout New Vegas\ngamePath={self.game}\n"
            "selected_profile=@ByteArray(Extended)\n", encoding="utf-8")
        self.low = self.mo2 / "mods/Low"
        self.high = self.mo2 / "mods/High"
        for folder, text in ((self.low, "Old"), (self.high, "New")):
            (folder / "menus").mkdir(parents=True)
            (folder / "menus/strings.xml").write_text(f"<text>{text}</text>", encoding="utf-8")
        (self.profile / "modlist.txt").write_text("+High\n-Locked\n+Low\n", encoding="utf-8")
        (self.profile / "plugins.txt").write_text("FalloutNV.esm\n", encoding="cp1252")
        (self.profile / "loadorder.txt").write_text("FalloutNV.esm\nInactive.esp\n", encoding="utf-8")
        self.translated = self.root / "검수본"
        (self.translated / "menus").mkdir(parents=True)
        (self.translated / "menus/strings.xml").write_text("<text>시험용 새 문구</text>", encoding="utf-8")
        (self.root / "review.txt").write_text("Synthetic fixture only. Not a real game translation.", encoding="utf-8")
        self.spec = self.root / "spec.json"
        vnvkr.write_json(self.spec, {"schema_version": 1, "scope": "extended",
                                    "files": [{"path": "menus/strings.xml", "review": "review.txt"}]})
        self.installation = vnvkr.Installation(self.mo2)
        self.executable = vnvkr.engine(None)
        self.bundle = self.root / "bundle"
        self.output = self.mo2 / "mods/[NoDelete] VNV KR"

    def build(self):
        return vnvkr.build_bundle(self.installation, self.spec, self.translated, self.bundle, self.executable)

    def test_real_xdelta_roundtrip_and_originals_preserved(self):
        before = {p: p.read_bytes() for p in self.mo2.rglob("*") if p.is_file()}
        manifest = self.build()
        self.assertEqual(len(manifest["files"]), 1)
        self.assertEqual(len(vnvkr.preflight(self.installation, self.bundle)[1]), 1)
        report = vnvkr.apply_bundle(self.installation, self.bundle, self.output, self.executable)
        self.assertEqual((self.output / "menus/strings.xml").read_bytes(),
                         (self.translated / "menus/strings.xml").read_bytes())
        self.assertEqual(report["byte_validation"], "passed")
        self.assertEqual(report["runtime_validation"], "not_tested")
        self.assertTrue(all(path.read_bytes() == data for path, data in before.items()))
        self.assertFalse((self.bundle / "menus/strings.xml").exists())

    def test_mo2_provider_priority(self):
        result = self.installation.inventory()
        row = next(row for row in result["files"] if row["path"] == "menus/strings.xml")
        self.assertEqual(row["provider"], "High")
        self.assertEqual(row["provider_chain"], ["Low", "High"])

    def test_game_data_is_lowest_priority_provider(self):
        install = vnvkr.Installation(self.mo2)
        chain = install.providers['falloutnv.esm']
        self.assertEqual(chain[0]['provider'], 'game:Data')
        self.assertEqual(install.source('FalloutNV.esm'), self.data / 'FalloutNV.esm')

        fixed = self.high / 'FalloutNV.esm'
        fixed.write_bytes(b'synthetic fixed master')
        install = vnvkr.Installation(self.mo2)
        chain = install.providers['falloutnv.esm']
        self.assertEqual([row['provider'] for row in chain], ['game:Data', 'High'])
        self.assertEqual(install.source('FalloutNV.esm'), fixed)

    def test_overwrite_wins(self):
        (self.mo2 / "overwrite/menus").mkdir(parents=True)
        (self.mo2 / "overwrite/menus/strings.xml").write_text("overwrite", encoding="utf-8")
        install = vnvkr.Installation(self.mo2)
        self.assertEqual(install.source("menus/strings.xml").read_text(), "overwrite")

    def test_source_version_mismatch_rejected_before_output(self):
        self.build()
        (self.high / "menus/strings.xml").write_text("updated by installer", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Source version differs"):
            vnvkr.apply_bundle(self.installation, self.bundle, self.output, self.executable)
        self.assertFalse(self.output.exists())

    def test_corrupt_delta_rejected_before_output(self):
        self.build()
        (self.bundle / "deltas/0000.vcdiff").write_bytes(b"broken")
        with self.assertRaisesRegex(ValueError, "integrity mismatch"):
            vnvkr.apply_bundle(self.installation, self.bundle, self.output, self.executable)
        self.assertFalse(self.output.exists())

    def test_wrong_expected_translation_does_not_publish_partial_mod(self):
        self.build()
        manifest = vnvkr.read_json(self.bundle / "manifest.json")
        manifest["files"][0]["target_sha256"] = "0" * 64
        vnvkr.write_json(self.bundle / "manifest.json", manifest)
        with self.assertRaisesRegex(ValueError, "Reconstructed translation differs"):
            vnvkr.apply_bundle(self.installation, self.bundle, self.output, self.executable)
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.output.parent.glob(".vnvkr-apply-*")), [])

    def test_second_apply_refuses_existing_mod(self):
        self.build()
        vnvkr.apply_bundle(self.installation, self.bundle, self.output, self.executable)
        with self.assertRaises(FileExistsError):
            vnvkr.apply_bundle(self.installation, self.bundle, self.output, self.executable)

    def test_protected_outputs(self):
        self.build()
        for target in (self.data / "KR", self.profile / "KR", self.high / "KR", self.mo2 / "KR"):
            with self.subTest(target=target), self.assertRaises(ValueError):
                vnvkr.apply_bundle(self.installation, self.bundle, target, self.executable)
            self.assertFalse(target.exists())

    def test_bundle_cannot_escape_output(self):
        self.build()
        manifest = vnvkr.read_json(self.bundle / "manifest.json")
        manifest["files"][0]["path"] = "../escape.xml"
        vnvkr.write_json(self.bundle / "manifest.json", manifest)
        with self.assertRaises(ValueError):
            vnvkr.apply_bundle(self.installation, self.bundle, self.output, self.executable)
        self.assertFalse((self.root / "escape.xml").exists())

    def test_empty_bundle_is_not_success(self):
        vnvkr.write_json(self.spec, {"schema_version": 1, "scope": "base", "files": []})
        with self.assertRaisesRegex(ValueError, "empty bundles"):
            self.build()
        self.assertFalse(self.bundle.exists())

    def test_inactive_plugin_refused(self):
        (self.high / "Inactive.esp").write_bytes(b"synthetic inactive placeholder")
        with self.assertRaisesRegex(ValueError, "inactive"):
            vnvkr.Installation(self.mo2).source("Inactive.esp")

    def test_wrong_game_and_modern_plugin_format_refused(self):
        (self.profile / "plugins.txt").write_text("*FalloutNV.esm\n", encoding="cp1252")
        with self.assertRaisesRegex(ValueError, "legacy format"):
            vnvkr.Installation(self.mo2)
        (self.mo2 / "ModOrganizer.ini").write_text("[General]\ngameName=Fallout 4\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "not a New Vegas"):
            vnvkr.Installation(self.mo2)

    def test_custom_base_directory(self):
        base = self.root / "Separate instance"
        (base / "mods").mkdir(parents=True)
        import shutil
        shutil.copytree(self.profile.parent, base / "profiles")
        shutil.copytree(self.high, base / "mods/High")
        shutil.copytree(self.low, base / "mods/Low")
        with (self.mo2 / "ModOrganizer.ini").open("a", encoding="utf-8") as stream:
            stream.write(f"[Settings]\nbase_directory={base}\nmod_directory=%BASE_DIR%/mods\n")
        install = vnvkr.Installation(self.mo2)
        self.assertEqual(install.mods, base / "mods")
        self.assertEqual(install.source("menus/strings.xml"), base / "mods/High/menus/strings.xml")

    def test_case_insensitive_duplicates_and_windows_path_rules(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            vnvkr.validate_entries([{"path": "menus/a.xml"}, {"path": "Menus/A.xml"}])
        for value in ("../a", "C:/a", "menus\\a", "con.txt", "a/../b", "a.", "a//b", "meta.ini"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                vnvkr.virtual_path(value)


if __name__ == "__main__":
    unittest.main()
