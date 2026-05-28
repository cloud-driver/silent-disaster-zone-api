from pathlib import Path
import json


raw_root = Path("data/realtime/raw")


def find_latest_file(folder: Path):
    files = sorted(folder.glob("*.json"))
    if not files:
        return None
    return files[-1]


def summarize_json(obj, indent=0, max_depth=3):
    prefix = "  " * indent

    if indent > max_depth:
        print(prefix + "...")
        return

    if isinstance(obj, dict):
        print(prefix + f"dict keys={list(obj.keys())[:20]}")
        for key, value in list(obj.items())[:8]:
            print(prefix + f"- {key}: {type(value).__name__}")
            summarize_json(value, indent + 1, max_depth)

    elif isinstance(obj, list):
        print(prefix + f"list len={len(obj)}")
        if len(obj) > 0:
            print(prefix + f"first item type={type(obj[0]).__name__}")
            summarize_json(obj[0], indent + 1, max_depth)

    else:
        value = str(obj)
        if len(value) > 100:
            value = value[:100] + "..."
        print(prefix + f"{type(obj).__name__}: {value}")


print("=== Inspect realtime snapshots ===")

source_dirs = sorted([p for p in raw_root.iterdir() if p.is_dir()])

for source_dir in source_dirs:
    print("\n" + "=" * 80)
    print("source:", source_dir.name)

    latest_file = find_latest_file(source_dir)

    if latest_file is None:
        print("沒有 json 檔案")
        continue

    print("latest:", latest_file)

    try:
        with open(latest_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        summarize_json(data)

    except Exception as e:
        print("讀取失敗：", e)