import os
import time
import random
import requests
import psutil
import subprocess
import sys

target_dir = r"C:\Users\Mohit\Documents\kill_test"
os.makedirs(target_dir, exist_ok=True)

# Create files
for i in range(50):
    path = f"{target_dir}\\file_{i}.txt"
    with open(path, "w") as f:
        f.write("normal content " * 100)

print(f"Starting fake encryption... (PID: {os.getpid()})")
print("Doing rapid file modifications...")

count = 0
while True:
    for i in range(50):
        path = f"{target_dir}\\file_{i}.txt"
        try:
            with open(path, "wb") as f:
                f.write(bytes([random.randint(0, 255) for _ in range(500)]))
            new_path = path + ".LOCKED"
            if os.path.exists(path):
                os.rename(path, new_path)
            if os.path.exists(new_path):
                os.rename(new_path, path)
        except Exception:
            pass

    count += 1
    print(f"  Encrypted batch {count} (50 files)...")

    # After 3 batches, send behavioral snapshot to model
    if count == 3:
        print("\n  Sending behavior to detection API...")
        try:
            payload = {
                "file_write_count": 150,
                "file_rename_count": 150,
                "entropy_before": 3.5,
                "entropy_after": 7.9,
                "entropy_change": 4.4,
                "process_execution_time": 6.0,
                "api_call_frequency": 15000,
                "file_access_rate": 25.0,
                "extension_change_count": 150,
                "encryption_indicator": 0.95,
                "rename_to_write_ratio": 1.0,
                "entropy_spike": 0.55,
                "aggression_score": 23.75,
                "ext_change_rate": 25.0,
            }
            r = requests.post("http://127.0.0.1:5000/predict", json=payload)
            result = r.json()["data"]
            prob = result["probability"]
            label = result["label"]
            print(f"\n  Model Result: {label.upper()} (probability: {prob:.4f})")

            if label == "ransomware":
                print(f"\n  RANSOMWARE CONFIRMED — Sending kill alert...")

                # Send alert to backend
                requests.post("http://127.0.0.1:5000/alert", json={
                    "type": "process_killed",
                    "pid": os.getpid(),
                    "process_name": "fake_ransomware.py",
                    "probability": prob,
                    "action_taken": "terminated",
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "ransomware_prob": prob,
                })

                print(f"  Alert sent to dashboard!")
                print(f"\n  Simulating self-termination in 3 seconds...")
                time.sleep(3)

                # Clean up
                import shutil
                if os.path.exists(target_dir):
                    shutil.rmtree(target_dir)
                    print(f"  Cleaned up {target_dir}")

                print("\n  PROCESS TERMINATED BY RANSOMGUARD")
                sys.exit(0)

        except Exception as e:
            print(f"  API error: {e} — is backend running?")

    time.sleep(0.5)