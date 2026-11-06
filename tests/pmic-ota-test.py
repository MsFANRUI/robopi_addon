#!/usr/bin/env python3
"""Offline checks for both PMIC firmware bundles."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("pmic_bundle", ROOT / "scripts/robopi-pmic-ota.py")
PMIC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PMIC)
BUNDLES = {
    "stm32f103c8": ("0.1.9-left", "ChargeBAT.bin", False),
    "gd32f503vet6": ("0.1.1-gd32", "ChargeBAT_GD32.bin", True),
}


def source_for(target):
    directory = "gd32f503" if target == "gd32f503vet6" else target
    return ROOT / "firmware/pmic/candidate" / directory


def copy_bundle(source, target, app_file):
    for name in ("manifest.json", "boot.bin", app_file):
        (target / name).write_bytes((source / name).read_bytes())


class PmicBundleTest(unittest.TestCase):
    def test_current_bundle(self):
        for target, (version, _, ota_supported) in BUNDLES.items():
            with self.subTest(target=target):
                manifest, images = PMIC.load_bundle(source_for(target) / "manifest.json")
                self.assertEqual(manifest["target"], target)
                self.assertEqual(manifest["version"], version)
                self.assertIs(manifest["ota_supported"], ota_supported)
                self.assertGreater(len(images["app"]), len(images["boot"]))

    def test_corrupted_image_is_rejected(self):
        for target, (_, app_file, _) in BUNDLES.items():
            with self.subTest(target=target), tempfile.TemporaryDirectory() as directory:
                destination = Path(directory)
                copy_bundle(source_for(target), destination, app_file)
                with (destination / app_file).open("r+b") as image:
                    image.seek(20)
                    original = image.read(1)
                    image.seek(20)
                    image.write(bytes([original[0] ^ 0xFF]))
                with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                    PMIC.load_bundle(destination / "manifest.json")

    def test_wrong_target_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            copy_bundle(source_for("stm32f103c8"), target, "ChargeBAT.bin")
            manifest_path = target / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["target"] = "unknown"
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "unsupported"):
                PMIC.load_bundle(manifest_path)

    def test_manifest_version_must_match_image(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            copy_bundle(source_for("stm32f103c8"), target, "ChargeBAT.bin")
            manifest_path = target / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["version"] = "0.1.8-stm32f103c8"
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "version is absent"):
                PMIC.load_bundle(manifest_path)

    def test_verify_bundle_needs_no_serial_device(self):
        for target in BUNDLES:
            with self.subTest(target=target):
                self.assertEqual(PMIC.main(["verify-bundle", "--bundle",
                                            str(source_for(target) / "manifest.json")]), 0)


if __name__ == "__main__":
    unittest.main()
