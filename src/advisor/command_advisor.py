from typing import Any, Dict, List

from src.advisor.ollama_client import chat_with_ollama


IMPORTANT_FIELDS = [
    "village_id",
    "county_name",
    "town_name",
    "village_name",
    "population_total",
    "elderly_ratio",
    "static_risk_score",
    "sensor_gap_score",
    "sensor_realtime_score",
    "rainfall_realtime_score",
    "landslide_realtime_score",
    "road_realtime_score",
    "realtime_event_score",
    "report_count_6h",
    "report_count_24h",
    "silent_risk_rule_score",
    "silent_risk_nn_score",
    "silent_risk_score",
    "silent_risk_level",
    "silent_reason",
    "realtime_run_id",
]


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def select_top_villages(records: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    sorted_records = sorted(
        records,
        key=lambda row: safe_float(row.get("silent_risk_score")),
        reverse=True,
    )

    selected = []

    for row in sorted_records[:limit]:
        item = {}

        for field in IMPORTANT_FIELDS:
            item[field] = row.get(field)

        selected.append(item)

    return selected


def build_advisor_prompts(selected_villages: List[Dict[str, Any]]) -> Dict[str, str]:
    system_prompt = """
你是一個「防災指揮建議輔助系統」，不是官方決策者。

你的任務：
根據使用者提供的沉默災區風險資料，產生給災害應變中心或地方防災人員參考的行動建議。

嚴格限制：
1. 只能根據提供的資料推論，不得編造沒有出現在資料中的災情。
2. 不得宣稱某地已經發生災害，除非資料明確顯示。
3. 不得發布撤離命令、封路命令或任何官方強制命令。
4. 可以建議「優先確認」、「派員查證」、「聯繫里長」、「比對通報」、「查看感測器狀態」等低風險行動。
5. 必須清楚標示資料限制，例如 mock 通報資料、感測器覆蓋不足、即時資料可能延遲。
6. 回答必須使用繁體中文。
7. 回答要具體、可執行、不要空泛。
"""

    user_prompt = f"""
以下是目前沉默災區偵測 API 回傳的高風險村里資料。

資料欄位說明：
- silent_risk_score：沉默風險分數，越高代表越需要主動確認。
- silent_risk_level：沉默風險等級。
- static_risk_score：靜態災害與脆弱度風險。
- sensor_gap_score：感測器覆蓋缺口。
- realtime_event_score：即時雨量、土石流、路況事件分數。
- report_count_6h / report_count_24h：近 6 小時 / 24 小時通報數。
- silent_reason：系統計算出的主要原因。

請根據資料產生「指揮建議 briefing」。

請用以下格式回答：

# 指揮建議摘要

## 1. 優先關注區域
列出最需要優先確認的 3～5 個村里，說明原因。

## 2. 建議立即行動
列出 5～8 個具體行動，例如聯繫對象、查證項目、資料比對、巡查優先順序。

## 3. 不建議立即升級為災害事件的原因
說明為什麼目前只能列為「優先確認」，不能直接判定為災害。

## 4. 資料缺口與下一步
指出目前資料不足處，並建議補強資料。

## 5. 給指揮官的一句話
用一句話總結目前最重要的判斷。

資料如下：
{selected_villages}
"""

    return {
        "system_prompt": system_prompt.strip(),
        "user_prompt": user_prompt.strip(),
    }


def generate_command_advice(
    records: List[Dict[str, Any]],
    limit: int = 5,
) -> Dict[str, Any]:
    selected_villages = select_top_villages(records, limit=limit)

    prompts = build_advisor_prompts(selected_villages)

    result = chat_with_ollama(
        system_prompt=prompts["system_prompt"],
        user_prompt=prompts["user_prompt"],
        temperature=0.2,
    )

    return {
        "model": result["model"],
        "base_url": result["base_url"],
        "selected_villages": selected_villages,
        "advice": result["content"],
    }