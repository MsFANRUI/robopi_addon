#!/usr/bin/env python3
"""Offline checks for the single STM32F103C8 PMIC firmware bundle."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("pmic_bundle", ROOT / "scripts/robopi-pmic-ota.py")
PMIC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PMIC)
SOURCE = ROOT / "firmware/pmic/candidate/stm32f103c8"


def copy_bundle(target):
    for name in ("manifest.json", "boot.bin", "ChargeBAT.bin"):
        (target / name).write_bytes((SOURCE / name).read_bytes())


class PmicBundleTest(unittest.TestCase):
    def test_current_bundle(self):
        manifest, images = PMIC.load_bundle(SOURCE / "manifest.json")
        self.assertEqual(manifest["target"], "stm32f103c8")
        self.assertEqual(manifest["version"], "0.1.8-left")
        self.assertFalse(manifest["ota_supported"])
        self.assertGreater(len(images["app"]), len(images["boot"]))

    def test_corrupted_image_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            copy_bundle(target)
            with (target / "ChargeBAT.bin").open("r+b") as image:
                image.seek(20)
                image.write(b"\0")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                PMIC.load_bundle(target / "manifest.json")

    def test_wrong_target_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            copy_bundle(target)
            manifest_path = target / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["target"] = "gd32f503"
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "unsupported"):
                PMIC.load_bundle(manifest_path)

    def test_manifest_version_must_match_image(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            copy_bundle(target)
            manifest_path = target / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["version"] = "0.1.8-stm32f103c8"
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "version is absent"):
                PMIC.load_bundle(manifest_path)

    def test_verify_bundle_needs_no_serial_device(self):
        self.assertEqual(PMIC.main(["verify-bundle", "--bundle", str(SOURCE / "manifest.json")]), 0)


if __name__ == "__main__":
    unittest.main()
