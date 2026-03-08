"""
PHASE 11 — RANSOMWARE SIMULATOR (SAFE TESTING)
================================================
⚠️  THIS IS A SAFE SIMULATOR — it does NOT contain malware.
    It only simulates the BEHAVIORAL PATTERNS of ransomware
    (rapid file writes + renames + entropy changes) to test
    whether our detection system responds correctly.

HOW TO USE:
    python tests/ransomware_simulator.py --dir /tmp/test_sandbox --mode ransomware
    python tests/ransomware_simulator.py --dir /tmp/test_sandbox --mode benign
    python tests/ransomware_simulator.py --dir /tmp/test_sandbox --mode mixed

The simulator:
1. Creates a sandbox directory with dummy files
2. Simulates mass file modifications (high entropy + bulk rename)
3. Checks if the detection engine fires an alert
"""

import os
import sys
import time
import random
import string
import struct
import hashlib
import argparse
import threading
from pathlib import Path
from datetime import datetime


# ─────────────────────────────────────────────────────────────
# SAFE FILE OPERATIONS
# ─────────────────────────────────────────────────────────────

def create_sandbox(base_dir: str, n_files: int = 50) -> list:
    """Create dummy files to simulate a Documents folder."""
    os.makedirs(base_dir, exist_ok=True)
    created = []

    extensions = [".txt", ".docx", ".xlsx", ".pdf", ".jpg", ".png"]
    for i in range(n_files):
        ext = random.choice(extensions)
        name = f"document_{i:03d}{ext}"
        path = os.path.join(base_dir, name)
        # Write realistic-looking random text (low entropy ≈ normal file)
        content = " ".join(random.choices(string.ascii_lowercase + " ", k=500))
        with open(path, "w") as f:
            f.write(content)
        created.append(path)

    print(f"📁 Created {n_files} sandbox files in {base_dir}")
    return created


def low_entropy_bytes(n: int) -> bytes:
    """Generate low-entropy (plaintext-like) bytes."""
    chars = (string.ascii_lowercase + " ").encode()
    return bytes(random.choices(chars, k=n))


def high_entropy_bytes(n: int) -> bytes:
    """Generate high-entropy (encryption-like) bytes — pure random."""
    return bytes([random.randint(0, 255) for _ in range(n)])


# ─────────────────────────────────────────────────────────────
# SIMULATION MODES
# ─────────────────────────────────────────────────────────────

class BenignSimulator:
    """Simulates normal file activity (word processor, browser, etc.)"""

    def run(self, files: list, duration: int = 30):
        print(f"\n🟢 Benign simulator running for {duration}s...")
        end = time.time() + duration
        modified = 0
        while time.time() < end:
            if not files:
                break
            path = random.choice(files)
            try:
                with open(path, "w") as f:
                    f.write(low_entropy_bytes(200).decode("latin-1"))
                modified += 1
            except Exception:
                pass
            time.sleep(random.uniform(0.5, 2.0))   # slow, infrequent writes
        print(f"   ✅ Benign: modified {modified} files in {duration}s")


class RansomwareSimulator:
    """
    Simulates ransomware behavior:
    - Bulk file reads (get entropy before)
    - Bulk writes with high-entropy data (simulate encryption)
    - Mass file renames with suspicious extension
    
    ⚠️  SAFE: writes random bytes but does NOT implement any actual
       encryption algorithm. Files are recoverable (just random data).
    """

    RANSOM_EXTENSIONS = [".LOCKED", ".WNCRY", ".encrypted", ".crypt"]

    def run(self, files: list, speed: str = "fast", silent: bool = False):
        """
        speed: 'fast' (aggressive), 'slow' (evasive ransomware)
        """
        if not silent:
            print(f"\n🔴 Ransomware simulator starting ({speed} mode)...")
            print(f"   Targets: {len(files)} files")

        ransom_ext = random.choice(self.RANSOM_EXTENSIONS)
        delay = 0.01 if speed == "fast" else 0.3

        renamed = []
        for i, path in enumerate(files):
            try:
                # Step 1: Read file (collect entropy before)
                with open(path, "rb") as f:
                    original = f.read()

                # Step 2: Write "encrypted" (high entropy) data
                with open(path, "wb") as f:
                    f.write(high_entropy_bytes(len(original) + 100))

                # Step 3: Rename with ransom extension
                new_path = path + ransom_ext
                os.rename(path, new_path)
                renamed.append(new_path)

                if not silent:
                    print(f"   [{i+1:3d}/{len(files)}] "
                          f"{os.path.basename(path)} → "
                          f"{os.path.basename(new_path)}")

                time.sleep(delay)

            except Exception as e:
                if not silent:
                    print(f"   [ERR] {path}: {e}")

        if not silent:
            print(f"\n   💀 Ransomware simulation: {len(renamed)}/{len(files)} files affected")
        return renamed


class DropperSimulator:
    """
    Simulates initial ransomware 'dropper' phase:
    - Slow initial recon
    - Then aggressive encryption
    This tests whether the system catches it BEFORE mass damage.
    """

    def run(self, files: list):
        print(f"\n🟡 Dropper simulator (recon → attack)...")

        # Phase 1: Slow recon (should not trigger alert yet)
        print("   Phase 1: Recon (slow file reads)...")
        for path in files[:5]:
            try:
                with open(path, "rb") as f:
                    _ = f.read()
            except Exception:
                pass
            time.sleep(0.5)

        # Phase 2: Rapid encryption (should trigger alert)
        print("   Phase 2: Mass encryption (should trigger detection)...")
        sim = RansomwareSimulator()
        renamed = sim.run(files[5:], speed="fast", silent=True)
        print(f"   Files encrypted: {len(renamed)}")


# ─────────────────────────────────────────────────────────────
# DETECTION VERIFICATION
# ─────────────────────────────────────────────────────────────

def verify_detection(backend_url: str = "http://127.0.0.1:5000") -> bool:
    """Check if the backend received any alerts."""
    try:
        import requests
        r = requests.get(f"{backend_url}/monitor", timeout=3)
        data = r.json()
        detections = data["data"]["ransomware_detections"]
        alerts     = data["data"]["alert_count"]
        killed     = data["data"]["processes_killed"]
        print(f"\n📊 Detection Results:")
        print(f"   Ransomware detections : {detections}")
        print(f"   Alerts generated      : {alerts}")
        print(f"   Processes killed      : {killed}")
        return detections > 0
    except Exception as e:
        print(f"   ⚠️  Backend check failed: {e}")
        return False


def direct_api_test(backend_url: str = "http://127.0.0.1:5000"):
    """Test the /predict endpoint directly with ransomware features."""
    try:
        import requests

        print(f"\n🧪 Direct API Tests:")

        # Benign sample
        benign = requests.get(f"{backend_url}/simulate/benign").json()
        bp = benign["data"]["prediction"]["probability"]
        print(f"   Benign sample  → probability = {bp:.4f} "
              f"({'✅ correct' if bp < 0.5 else '❌ incorrect'})")

        # Ransomware sample
        ransom = requests.get(f"{backend_url}/simulate/ransomware").json()
        rp = ransom["data"]["prediction"]["probability"]
        print(f"   Ransom sample  → probability = {rp:.4f} "
              f"({'✅ correct' if rp >= 0.5 else '❌ incorrect'})")

    except Exception as e:
        print(f"   API test failed: {e} (backend may not be running)")


# ─────────────────────────────────────────────────────────────
# CLEANUP
# ─────────────────────────────────────────────────────────────

def cleanup_sandbox(base_dir: str):
    """Remove all files from sandbox."""
    import shutil
    if os.path.exists(base_dir):
        shutil.rmtree(base_dir)
        print(f"\n🧹 Sandbox cleaned: {base_dir}")


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Ransomware Behavior Simulator (SAFE)")
    parser.add_argument("--dir",   default="/tmp/ransom_sandbox", help="Sandbox directory")
    parser.add_argument("--mode",  choices=["benign", "ransomware", "dropper", "all"],
                        default="all")
    parser.add_argument("--files", type=int, default=30, help="Number of test files")
    parser.add_argument("--no-cleanup", action="store_true")
    parser.add_argument("--api-test", action="store_true", help="Test backend API directly")
    args = parser.parse_args()

    print("=" * 55)
    print("  RANSOMWARE BEHAVIOR SIMULATOR (SAFE)")
    print("=" * 55)
    print(f"  Mode      : {args.mode}")
    print(f"  Directory : {args.dir}")
    print(f"  Files     : {args.files}")

    if args.api_test:
        direct_api_test()
        return

    files = create_sandbox(args.dir, args.files)

    if args.mode == "benign":
        BenignSimulator().run(files, duration=20)

    elif args.mode == "ransomware":
        RansomwareSimulator().run(files, speed="fast")

    elif args.mode == "dropper":
        DropperSimulator().run(files)

    elif args.mode == "all":
        # Run all modes sequentially in different sandboxes
        for mode, cls in [("benign", BenignSimulator),
                          ("ransomware", RansomwareSimulator),
                          ("dropper", DropperSimulator)]:
            sub_dir = os.path.join(args.dir, mode)
            sub_files = create_sandbox(sub_dir, 20)
            print(f"\n{'─'*40}")
            if mode == "benign":
                cls().run(sub_files, duration=10)
            elif mode == "ransomware":
                cls().run(sub_files)
            else:
                cls().run(sub_files)
            time.sleep(2)

    # Check if detection fired
    time.sleep(3)
    detected = verify_detection()
    if detected:
        print("\n✅ PASS: Detection system caught the ransomware behavior!")
    else:
        print("\n⚠️  Detection system did not fire (engine may not be running)")

    if not args.no_cleanup:
        cleanup_sandbox(args.dir)

    print("\n✅ Simulation complete")


if __name__ == "__main__":
    main()
