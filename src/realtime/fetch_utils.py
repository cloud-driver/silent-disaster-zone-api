from pathlib import Path
from datetime import datetime
import json
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def make_run_id():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def fetch_json(url, headers=None, timeout=20):
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.json()


def save_json_snapshot(source_name, run_id, data):
    output_dir = PROJECT_ROOT / "data" / "realtime" / "raw" / source_name
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{run_id}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return output_path


def append_run_log(run_id, source_name, status, raw_path=None, message=""):
    log_path = PROJECT_ROOT / "data" / "runs" / "realtime_runs.csv"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    is_new = not log_path.exists()

    with open(log_path, "a", encoding="utf-8") as f:
        if is_new:
            f.write("run_id,source_name,status,raw_path,message\n")

        safe_message = str(message).replace("\n", " ").replace(",", "，")
        f.write(f"{run_id},{source_name},{status},{raw_path or ''},{safe_message}\n")