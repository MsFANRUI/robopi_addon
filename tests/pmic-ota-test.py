#!/usr/bin/env python3
"""Offline checks for both PMIC firmware bundles."""

import importlib.util
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("pmic_bundle", ROOT / "scripts/robopi-pmic-ota.py")
PMIC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PMIC)
BUNDLES = {
    "stm32f103c8": ("0.1.10", "ChargeBAT.bin", True),
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

    def test_stm32_flash_protocol(self):
        class Port:
            def __init__(self):
                self.reply = bytearray()
                self.image = bytearray()
                self.entered = False

            def reset_input_buffer(self):
                self.reply.clear()

            def write(self, value):
                command = value.decode("ascii")
                if command == "SN_GET:1;":
                    answer = "CHRG_SN:0669FF555553787287104058;"
                elif command == "FW_VER:1;":
                    answer = "FW_VER:0.1.10;"
                elif command == "OTA_ENTER:1;":
                    self.entered = True
                    answer = "OTA_BOOT;"
                elif command == "OTA_PING:1;":
                    answer = "OTA_BOOT:1;"
                elif command.startswith("OTA_BEGIN:"):
                    answer = "OTA_READY;"
                elif command.startswith("OTA_DATA:"):
                    offset, block = command[9:-1].split(",")
                    self.assert_offset(int(offset))
                    self.image.extend(bytes.fromhex(block))
                    answer = f"OTA_ACK:{len(self.image)};"
                elif command == "OTA_END:1;":
                    answer = "OTA_DONE;"
                else:
                    raise AssertionError(command)
                self.reply.extend(answer.encode("ascii"))

            def assert_offset(self, offset):
                if offset != len(self.image):
                    raise AssertionError("wrong OTA offset")

            def flush(self):
                pass

            def read(self, size):
                result = bytes(self.reply[:size])
                del self.reply[:size]
                return result

        image = struct.pack("<II", 0x20005000, 0x08001101) + bytes(range(256)) * 5
        port = Port()
        PMIC.flash_stm32(port, image, 0.1, "0669FF555553787287104058")
        self.assertTrue(port.entered)
        self.assertEqual(port.image, image)
        self.assertEqual(zlib.crc32(port.image), zlib.crc32(image))

    def test_stm32_wrong_uid_cannot_erase(self):
        image = struct.pack("<II", 0x20005000, 0x08001101) + bytes(512)

        class Port:
            def __init__(self):
                self.reply = bytearray()
                self.commands = []

            def reset_input_buffer(self):
                self.reply.clear()

            def write(self, value):
                self.commands.append(value)
                self.reply.extend(b"CHRG_SN:0669FF555553787287104058;"
                                  if value == b"SN_GET:1;" else b"FW_VER:0.1.10;")

            def flush(self):
                pass

            def read(self, size):
                result = bytes(self.reply[:size])
                del self.reply[:size]
                return result

        port = Port()
        with self.assertRaisesRegex(ValueError, "UID mismatch"):
            PMIC.flash_stm32(port, image, 0.1, "000000000000000000000000")
        self.assertNotIn(b"OTA_BEGIN:", b"".join(port.commands))


if __name__ == "__main__":
    unittest.main()
