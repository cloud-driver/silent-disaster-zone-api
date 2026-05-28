from pathlib import Path
import os
import sys
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


from src.realtime.fetch_utils import (
    make_run_id,
    fetch_json,
    save_json_snapshot,
    append_run_log,
)


load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[1]

run_id = make_run_id()

print("=== Realtime Fetch ===")
print("run_id:", run_id)


CWA_API_KEY = os.getenv("CWA_API_KEY")
WRA_API_URL = os.getenv("WRA_API_URL")


sources = []

def mask_url(url: str) -> str:
    if not url:
        return url

    if "Authorization=" in url:
        before, after = url.split("Authorization=", 1)
        token = after.split("&", 1)[0]
        masked = token[:6] + "..." + token[-4:] if len(token) > 10 else "***"
        return before + "Authorization=" + masked + (
            "&" + after.split("&", 1)[1] if "&" in after else ""
        )

    return url

# 1. 中央氣象署雨量觀測資料 O-A0002-001
# 實際 endpoint 你要用自己的授權碼。
# 若你的 API key 沒設，先跳過。
if CWA_API_KEY:
    sources.append({
        "source_name": "cwa_rain",
        "url": f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0002-001?Authorization={CWA_API_KEY}&format=JSON",
    })
else:
    print("跳過 cwa_rain：未設定 CWA_API_KEY")


# 2. 農村水保署：土石流及大規模崩塌警戒資料
sources.append({
    "source_name": "ardswc_alert",
    "url": "https://ls.ardswc.gov.tw/api/LandslideAlertOpenData",
})


# 3. 農村水保署：土石流潛勢溪流參考雨量站雨量資料
sources.append({
    "source_name": "ardswc_debris_rain",
    "url": "https://246.ardswc.gov.tw/webService/GetDebrisRainData.ashx",
})


# 4. 警廣即時路況
sources.append({
    "source_name": "road_traffic",
    "url": "https://rtr.pbs.gov.tw/NMP103_PbsWS/resources/roadData/opendata",
})


# 5. 水利署 WRA
# 這個先讓你從 Swagger 複製實際 URL 放進 .env 的 WRA_API_URL
if WRA_API_URL:
    sources.append({
        "source_name": "wra_water",
        "url": WRA_API_URL,
    })
else:
    print("跳過 wra_water：未設定 WRA_API_URL")


for source in sources:
    source_name = source["source_name"]
    url = source["url"]

    print("\n--------------------------------")
    print("source:", source_name)
    print("url:", mask_url(url))

    try:
        data = fetch_json(url)
        raw_path = save_json_snapshot(source_name, run_id, data)
        append_run_log(run_id, source_name, "success", raw_path, "")
        print("success:", raw_path)

    except Exception as e:
        append_run_log(run_id, source_name, "failed", "", str(e))
        print("failed:", e)


print("\n完成 realtime fetch")
print("run_id:", run_id)