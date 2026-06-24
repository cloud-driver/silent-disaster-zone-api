from pathlib import Path
import os
import sys

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.realtime.fetch_utils import (
    append_run_log,
    fetch_json,
    make_run_id,
    save_json_snapshot,
)
from src.runtime.run_manifest import (
    create_manifest,
    mark_fetch_complete,
    update_source,
    write_manifest,
)


load_dotenv()

SOURCE_NAMES = [
    "cwa_rain",
    "ardswc_alert",
    "ardswc_debris_rain",
    "road_traffic",
]

run_id = make_run_id()
manifest = create_manifest(
    run_id=run_id,
    source_names=SOURCE_NAMES,
)

write_manifest(manifest)

print("=== Realtime Fetch ===")
print("run_id:", run_id)


CWA_API_KEY = os.getenv("CWA_API_KEY")


def mask_url(url: str) -> str:
    if not url:
        return url

    if "Authorization=" in url:
        before, after = url.split("Authorization=", 1)
        token = after.split("&", 1)[0]

        masked = (
            token[:6] + "..." + token[-4:]
            if len(token) > 10
            else "***"
        )

        suffix = (
            "&" + after.split("&", 1)[1]
            if "&" in after
            else ""
        )

        return before + "Authorization=" + masked + suffix

    return url


sources = []

if CWA_API_KEY:
    sources.append(
        {
            "source_name": "cwa_rain",
            "url": (
                "https://opendata.cwa.gov.tw/api/v1/rest/"
                "datastore/O-A0002-001"
                f"?Authorization={CWA_API_KEY}&format=JSON"
            ),
        }
    )
else:
    message = "未設定 CWA_API_KEY，跳過 cwa_rain。"

    print(message)

    append_run_log(
        run_id,
        "cwa_rain",
        "skipped",
        "",
        message,
    )

    update_source(
        manifest,
        "cwa_rain",
        "skipped",
        message=message,
    )

    write_manifest(manifest)


sources.extend(
    [
        {
            "source_name": "ardswc_alert",
            "url": (
                "https://ls.ardswc.gov.tw/"
                "api/LandslideAlertOpenData"
            ),
        },
        {
            "source_name": "ardswc_debris_rain",
            "url": (
                "https://246.ardswc.gov.tw/"
                "webService/GetDebrisRainData.ashx"
            ),
        },
        {
            "source_name": "road_traffic",
            "url": (
                "https://rtr.pbs.gov.tw/"
                "NMP103_PbsWS/resources/roadData/opendata"
            ),
        },
    ]
)


for source in sources:
    source_name = source["source_name"]
    url = source["url"]

    print("\n--------------------------------")
    print("source:", source_name)
    print("url:", mask_url(url))

    try:
        data = fetch_json(url)

        raw_path = save_json_snapshot(
            source_name,
            run_id,
            data,
        )

        raw_path_relative = str(
            raw_path.relative_to(PROJECT_ROOT)
        )

        append_run_log(
            run_id,
            source_name,
            "success",
            raw_path_relative,
            "",
        )

        update_source(
            manifest,
            source_name,
            "success",
            raw_path=raw_path_relative,
        )

        print("success:", raw_path)

    except Exception as error:
        message = str(error)

        append_run_log(
            run_id,
            source_name,
            "failed",
            "",
            message,
        )

        update_source(
            manifest,
            source_name,
            "failed",
            message=message,
        )

        print("failed:", message)

    finally:
        write_manifest(manifest)


mark_fetch_complete(manifest)
write_manifest(manifest)

print("\n完成 realtime fetch")
print("run_id:", run_id)
print(
    "manifest:",
    "outputs/latest/run_manifest.json",
)