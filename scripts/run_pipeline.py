from pathlib import Path
import subprocess
import sys
import time


PROJECT_ROOT = Path(__file__).resolve().parents[1]

LATEST_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "latest"

EXPECTED_OUTPUTS = [
    LATEST_OUTPUT_DIR / "silent_risk.json",
    LATEST_OUTPUT_DIR / "silent_risk.csv",
    LATEST_OUTPUT_DIR / "silent_risk.geojson",
]

PIPELINE_STEPS = [
    # 1. 村里界
    "scripts/export_villages_geojson.py",
    "scripts/normalize_villages.py",
    "scripts/validate_villages.py",
    "scripts/filter_mvp_area.py",

    # 2. 人口
    "scripts/normalize_population.py",
    "scripts/join_hualien_population.py",
    "scripts/finalize_hualien_population.py",

    # 3. 淹水潛勢
    "scripts/normalize_flood_potential.py",
    "scripts/repair_flood_geometry.py",
    "scripts/compute_flood_features.py",
    "scripts/finalize_flood_features.py",

    # 4. 土石流
    "scripts/normalize_debris_area.py",
    "scripts/compute_debris_features.py",

    # 5. 靜態風險
    "scripts/compute_static_risk.py",

    # 6. 感測器
    "scripts/normalize_sensors.py",
    "scripts/join_sensors_to_hualien.py",
    "scripts/compute_sensor_gap_features.py",

    # 7. 通報
    "scripts/check_reports.py",
    "scripts/join_reports_to_hualien.py",

    # 8. 沉默風險總分
    "scripts/compute_silent_risk.py",
]


def run_step(script_path: str):
    full_path = PROJECT_ROOT / script_path

    if not full_path.exists():
        raise FileNotFoundError(f"找不到 script：{script_path}")

    print("\n" + "=" * 80)
    print(f"Running: {script_path}")
    print("=" * 80)

    start = time.time()

    result = subprocess.run(
        [sys.executable, str(full_path)],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
    )

    elapsed = time.time() - start

    print(result.stdout)

    if result.returncode != 0:
        print(result.stderr)
        raise RuntimeError(f"{script_path} failed, return code={result.returncode}")

    print(f"Done: {script_path} ({elapsed:.2f}s)")


def main():
    print("Silent Disaster Zone Pipeline")
    print("Project root:", PROJECT_ROOT)

    start = time.time()

    for step in PIPELINE_STEPS:
        run_step(step)

    missing_outputs = [
        str(path.relative_to(PROJECT_ROOT))
        for path in EXPECTED_OUTPUTS
        if not path.exists()
    ]

    if missing_outputs:
        raise RuntimeError(
            "Pipeline 腳本均已完成，但預期 API 輸出不存在："
            f"{missing_outputs}"
        )

    elapsed = time.time() - start

    print("\n" + "=" * 80)
    print("Pipeline completed successfully.")
    print(f"Total time: {elapsed:.2f}s")
    print("Outputs:")
    print("- outputs/latest/silent_risk.json")
    print("- outputs/latest/silent_risk.csv")
    print("- outputs/latest/silent_risk.geojson")
    print("=" * 80)


if __name__ == "__main__":
    main()