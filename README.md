# Silent Disaster Zone Detection API

> 沉默災區偵測 API 是一個防災資料分析元件，用來找出「高風險但低通報、低觀測覆蓋」的村里，協助災防單位優先派員確認那些可能被系統忽略的區域。

GitHub Repository: <https://github.com/cloud-driver/silent-disaster-zone-api>

---

## 1. Project Overview

災情通報多的地方不一定最危險。真正需要被注意的地方，可能因為斷訊、交通中斷、高齡人口比例高、感測器覆蓋不足或數位通報能力低，反而沒有即時回報。

本專案的目標不是取代災害預測模型，而是提供一個可重複使用的 API 元件，輸出「高風險但低通報」的優先關注清單，讓防災系統、地圖儀表板或巡查派工流程可以快速整合。

---

## 2. Component Type

本作品定位為 **API 服務型元件（Service Component）**。

它可以被整合到：

- 災害應變儀表板
- 地圖系統
- LINE Bot 通報系統
- 地方政府災情查報流程
- 巡查任務派發系統
- 其他防災資料平台

---

## 3. Key Features

- 整合村里界、人口、高齡比例、淹水潛勢、土石流影響範圍。
- 串接即時資料來源，包括中央氣象署雨量、農村水保署土石流資料、警廣即時路況。
- 每次即時更新皆可保存 raw snapshot 與 history output。
- 產出 `silent_risk.json`、`silent_risk.csv`、`silent_risk.geojson`。
- 提供 FastAPI 查詢介面與 Swagger/OpenAPI 文件。
- 支援神經網路 scoring layer。
- 保留規則式分數與神經網路分數，方便比較與解釋。
- Repository 內建 sample outputs，評審 clone 後不需下載大型 raw data 也能快速 demo API。

---

## 4. Problem

傳統災情系統通常依賴「已通報資料」來判斷災情熱區，但高風險區可能因為以下原因沒有通報：

- 通訊中斷
- 高齡人口比例高
- 交通中斷
- 感測器覆蓋不足
- 數位通報能力不足
- 地方災情尚未被回報

因此，本元件關注的是：

> 高風險，但低通報或低觀測覆蓋的區域。

---

## 5. MVP Scope

目前 MVP 範圍為 **花蓮縣村里層級分析**。

分析單位：

- `village_id`
- `county_name`
- `town_name`
- `village_name`

主要輸出：

- `silent_risk_score`
- `silent_risk_level`
- `silent_reason`
- `silent_risk_rule_score`
- `silent_risk_nn_score`

---

## 6. Data Sources

### 6.1 Static / Low-frequency Data

- 村里界圖資
- 人口與年齡結構資料
- 淹水潛勢圖
- 土石流影響範圍圖

### 6.2 Realtime / Snapshot Data

- 中央氣象署雨量觀測資料
- 農村水保署土石流及大規模崩塌警戒資料
- 農村水保署土石流潛勢溪流參考雨量資料
- 警廣即時路況資料

### 6.3 Mock Data

目前通報資料使用 mock reports，用於驗證「高風險但低通報」偵測邏輯。

正式版可串接：

- LINE Bot
- 119
- 1999
- 地方災情通報系統
- 表單通報資料
- 巡查回報系統

---

## 7. Input / Process / Output

### 7.1 Input

| Input | Type | Description |
|---|---|---|
| Village boundary | GeoJSON / Shapefile | 村里界空間資料 |
| Population | CSV | 人口數、高齡人口比例 |
| Flood potential | GeoJSON / Shapefile | 淹水潛勢範圍 |
| Debris flow area | GeoJSON / Shapefile | 土石流影響範圍 |
| Realtime rainfall | JSON API snapshot | 即時雨量資料 |
| Landslide alert / debris rain | JSON API snapshot | 土石流警戒與參考雨量 |
| Road traffic | JSON API snapshot | 即時路況事件 |
| Disaster reports | JSON | 通報點位與嚴重度 |

### 7.2 Process

```text
Raw Data
  ↓
Static Pipeline
  - village boundary
  - population
  - flood potential
  - debris flow area
  ↓
Static Risk Features
  ↓
Realtime Fetch Pipeline
  - CWA rainfall
  - ARDSWC alert
  - ARDSWC debris rain
  - road traffic
  ↓
Realtime Features
  ↓
Report Features
  ↓
Scoring Layer
  - rule-based score
  - neural network score
  ↓
Outputs
  - JSON
  - CSV
  - GeoJSON
```

### 7.3 Output

| Output | Format | Description |
|---|---|---|
| `silent_risk.json` | JSON | API 查詢用的村里沉默風險資料 |
| `silent_risk.csv` | CSV | 表格分析與人工檢查 |
| `silent_risk.geojson` | GeoJSON | 地圖圖層展示 |

---

## 8. Scoring Logic

MVP 先使用可解釋的規則式分數產生基準分數，再由神經網路 scoring layer 輸出正式採用的 `silent_risk_score`。

核心概念：

```text
base_risk_score
= static risk
+ sensor gap
+ realtime event signal

silence_factor
= lower report activity → higher silence factor

silent_risk_score
= high risk × low report activity
```

白話來說：

- 風險高，但最近沒有通報 → 沉默風險上升。
- 風險高，但已有通報 → 沉默風險下降。
- 風險低，即使沒有通報 → 不會被誤判為沉默災區。

---

## 9. AI Scoring Layer

MVP 階段使用規則式分數產生 pseudo-label，訓練 `MLPRegressor` 神經網路模型，驗證 scoring layer 可替換架構。

目前模型不是使用真實災害 ground truth 訓練，因此不能宣稱能準確預測真實災情。

正式版可使用以下資料重新訓練：

- 歷史災情紀錄
- 巡查結果
- 通報延遲資料
- 救災派遣紀錄
- 專家標註的高優先巡查區

模型相關文件：

- [Model Card](docs/model.md)
- `models/silent_risk_mlp_metadata.json`

---

## 10. Environment

This MVP was developed and tested with:

- Python: **3.12.10**
- API framework: FastAPI
- Runtime server: Uvicorn
- Main geospatial libraries: GeoPandas, Shapely, PyProj
- Machine learning: scikit-learn MLPRegressor

Recommended setup differs by operating system.

### macOS / Linux

```bash
python3 --version
# Python 3.12.10

python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

### Windows PowerShell

```powershell
py -3.12 --version
# Python 3.12.10

py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell blocks virtual environment activation, run this in the same PowerShell window and try again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

---

## 11. Installation

### macOS / Linux

```bash
git clone https://github.com/cloud-driver/silent-disaster-zone-api.git
cd silent-disaster-zone-api

python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

### Windows PowerShell

```powershell
git clone https://github.com/cloud-driver/silent-disaster-zone-api.git
cd silent-disaster-zone-api

py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Create `.env` from `.env.example`:

macOS / Linux:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Then fill in your own API key:

```bash
CWA_API_KEY=your_cwa_api_key_here
```

Do not commit `.env`.

---

## 12. Quick Demo Without Raw Data

This repository does not commit raw government datasets or generated runtime outputs.

For quick review, the API automatically falls back to files in `sample_outputs/` when `outputs/latest/` does not exist.

After cloning the repository, reviewers can run:

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
uvicorn src.api.main:app --reload
```

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn src.api.main:app --reload
```

Then open:

```text
http://127.0.0.1:8000/docs
```

Useful demo endpoints:

```text
GET /health
GET /silent-risk/top?limit=5
GET /silent-risk/10015020001
GET /silent-risk.geojson
```

Expected fallback behavior:

```json
{
  "active_json_path": "sample_outputs/silent_risk_sample.json",
  "active_geojson_path": "sample_outputs/silent_risk_sample.geojson"
}
```

---

## 13. Run API

```bash
uvicorn src.api.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

Useful endpoints:

```text
GET /health
GET /model/info
GET /silent-risk/top?limit=5
GET /silent-risk/top?limit=5&refresh=true
GET /silent-risk/{village_id}
GET /silent-risk.geojson
```

---

## 14. API Endpoints

> Windows note: In PowerShell, use `curl.exe` instead of `curl` if `curl` is aliased to `Invoke-WebRequest`. You can also open the URLs directly in a browser.


### `GET /health`

Check API and output availability.

Example:

```bash
curl http://127.0.0.1:8000/health
```

### `GET /model/info`

Return neural network model metadata.

Example:

```bash
curl http://127.0.0.1:8000/model/info
```

### `GET /silent-risk/top`

Return top silent-risk villages.

Example:

```bash
curl "http://127.0.0.1:8000/silent-risk/top?limit=5"
```

### `GET /silent-risk/top?refresh=true`

Fetch realtime data, normalize features, recompute risk, apply NN scoring, and return top results.

This requires local data artifacts and a trained model. It is intended for development/demo environments after the preprocessing pipeline has been prepared.

Example:

```bash
curl "http://127.0.0.1:8000/silent-risk/top?limit=5&refresh=true"
```

### `GET /silent-risk/{village_id}`

Return one village by `village_id`.

Example:

```bash
curl http://127.0.0.1:8000/silent-risk/10015020001
```

### `GET /silent-risk.geojson`

Return GeoJSON layer for map display.

Example:

```bash
curl http://127.0.0.1:8000/silent-risk.geojson
```

---

## 15. Client Sample

### Python client example

```python
import requests

base_url = "http://127.0.0.1:8000"

response = requests.get(f"{base_url}/silent-risk/top", params={"limit": 5})
response.raise_for_status()

data = response.json()

for row in data["data"]:
    print(
        row["county_name"],
        row["town_name"],
        row["village_name"],
        row["silent_risk_score"],
        row["silent_risk_level"],
    )
```

---

## 16. Run Realtime Pipeline

Full realtime scoring requires local static/processed data artifacts.

macOS / Linux:

```bash
python3 scripts/fetch_realtime_sources.py
python3 scripts/normalize_realtime_sources.py
python3 scripts/compute_silent_risk_realtime.py
python3 scripts/apply_silent_risk_nn.py
```

Windows PowerShell:

```powershell
python scripts/fetch_realtime_sources.py
python scripts/normalize_realtime_sources.py
python scripts/compute_silent_risk_realtime.py
python scripts/apply_silent_risk_nn.py
```

Outputs will be written to:

```text
outputs/latest/silent_risk.json
outputs/latest/silent_risk.csv
outputs/latest/silent_risk.geojson
```

Historical outputs are written to:

```text
outputs/history/{run_id}/
```

### Full Pipeline Reproduction with Raw Data

This repository does not commit raw government datasets directly. To reproduce the full pipeline, download `raw_data_minimal.zip` from the GitHub Release page and unzip it into the project root.

Expected structure:

```text
data/raw/village_boundary/
data/raw/population/
data/raw/flood_potential/
data/raw/debris_flow/
data/raw/sensors/
data/raw/reports/
```

Then run:

```bash
python3 scripts/run_pipeline.py
```

On Windows PowerShell:

```powershell
py -3.12 scripts/run_pipeline.py
```

The full pipeline will regenerate processed features and output files from the raw datasets.

---

## 17. Reproducing the Neural Network Scoring Layer

Before running the API with NN scoring, train the model once:

macOS / Linux:

```bash
python3 scripts/train_silent_risk_nn.py
```

Windows PowerShell:

```powershell
python scripts/train_silent_risk_nn.py
```

Then run realtime scoring:

macOS / Linux:

```bash
python3 scripts/fetch_realtime_sources.py
python3 scripts/normalize_realtime_sources.py
python3 scripts/compute_silent_risk_realtime.py
python3 scripts/apply_silent_risk_nn.py
```

Windows PowerShell:

```powershell
python scripts/fetch_realtime_sources.py
python scripts/normalize_realtime_sources.py
python scripts/compute_silent_risk_realtime.py
python scripts/apply_silent_risk_nn.py
```

The API `refresh=true` mode will run the realtime refresh pipeline and apply the NN scoring layer if the trained model exists.

---

## 18. Example Output

See:

```text
sample_outputs/silent_risk_sample.json
sample_outputs/silent_risk_sample.csv
sample_outputs/silent_risk_sample.geojson
```

Example fields:

```json
{
  "village_id": "10015020001",
  "county_name": "花蓮縣",
  "town_name": "鳳林鎮",
  "village_name": "鳳仁里",
  "silent_risk_score": 0.392821,
  "silent_risk_level": "medium",
  "silent_reason": "靜態災害風險偏高；感測器覆蓋缺口偏高；近6小時無通報；近24小時無通報"
}
```

---

## 19. Project Structure

```text
silent-disaster-zone-api/
├── README.md
├── requirements.txt
├── .env.example
├── docs/
│   ├── api.md
│   ├── model.md
│   ├── submission.md
│   └── schemas/
├── sample_data/
├── sample_outputs/
├── scripts/
├── src/
│   ├── api/
│   └── realtime/
└── models/
    └── silent_risk_mlp_metadata.json
```

---

## 20. Raw Data and Generated Artifacts Policy

This repository does not commit large raw datasets or generated runtime outputs.

Ignored paths include:

```text
data/raw/
data/interim/
data/processed/
data/realtime/
outputs/
models/*.joblib
.env
```

Reasons:

- raw government datasets may be large,
- realtime API snapshots should be regenerated,
- generated outputs should be reproducible,
- API keys must not be committed,
- model binary artifacts can be retrained from scripts.

For quick review, the API falls back to `sample_outputs/` when `outputs/latest/` is not available.

The neural network model metadata is committed, but the `.joblib` model artifact is ignored. To regenerate the model, run:

macOS / Linux:

```bash
python3 scripts/train_silent_risk_nn.py
```

Windows PowerShell:

```powershell
python scripts/train_silent_risk_nn.py
```

---

## 21. Documentation

Additional documentation:

- [API Documentation](docs/api.md)
- [Model Card](docs/model.md)
- [Submission Description](docs/submission.md)
- [Silent Risk JSON Schema](docs/schemas/silent_risk.schema.json)
- [Report Input JSON Schema](docs/schemas/report_input.schema.json)

---

## 22. Reviewer Note

The repository includes sample outputs so the API can be reviewed without downloading large raw datasets. If `outputs/latest/` is not available, the API automatically falls back to `sample_outputs/`.

The full realtime refresh pipeline requires local raw/processed data artifacts and API credentials. The sample-output mode is provided so reviewers can immediately inspect the API behavior and output format.

---

## 23. Limitations

- 通報資料目前為 mock data。
- 神經網路目前使用 pseudo-label，不是真實災害標籤。
- 即時 API 可能受外部服務可用性影響。
- WRA 水利署水位資料尚未完成串接。
- 路況事件分數目前為關鍵字規則，仍需進一步細分事件嚴重程度。
- 本元件提供優先關注清單，不直接等同實際災情判定。
- Repository 不包含大型 raw data；完整重跑 pipeline 需要依資料來源重新準備資料。

---

## 24. Project Status

Current status: MVP completed.

The project can currently:

- fetch realtime data,
- preserve raw snapshots,
- generate realtime village-level features,
- compute silent risk scores,
- output JSON / CSV / GeoJSON,
- serve results through FastAPI.

---

## 25. Roadmap

Planned improvements:

- 串接 WRA 水利署水位資料。
- 串接真實災情通報系統。
- 將路況事件分數從關鍵字規則改為更細緻的事件分類。
- 使用歷史災情與巡查結果重新訓練 AI scoring layer。
- 加入 Docker 部署設定。
- 加入前端地圖 demo。

---

## 26. Optional Extension: Ollama Command Advisor

This project can be extended with a local Ollama-based command advisor layer.

The advisor layer is **not** responsible for deciding whether a place is actually in disaster or issuing official evacuation orders. Its role is to convert the API output into a concise, human-readable command briefing for discussion, triage, and follow-up checks.

Recommended positioning:

```text
silent_risk_score = model output
Ollama advisor = command suggestion / briefing generator
human commander = final decision maker
```

### Why use Ollama here?

Ollama can run a local LLM on a developer machine or internal server. This is useful for disaster-response discussion because the generated advice can be based on local API outputs without sending village-level risk records to an external cloud model.

### Suggested input to the advisor

The advisor should receive structured JSON from the API, for example the response from:

```text
GET /silent-risk/top?limit=5
```

Each record may include:

```json
{
  "village_id": "10015020001",
  "county_name": "花蓮縣",
  "town_name": "鳳林鎮",
  "village_name": "鳳仁里",
  "silent_risk_score": 0.392821,
  "silent_risk_level": "medium",
  "silent_reason": "靜態災害風險偏高；感測器覆蓋缺口偏高；近6小時無通報；近24小時無通報",
  "static_risk_score": 0.611599,
  "sensor_gap_score": 0.611599,
  "realtime_event_score": 0.0,
  "report_count_6h": 0,
  "report_count_24h": 0
}
```

### Suggested prompt design

The prompt should force the model to stay inside the data and avoid overclaiming.

```text
You are a disaster-response command assistant.

Use only the provided JSON records.
Do not claim that a disaster has definitely occurred.
Do not issue official evacuation orders.
Do not invent facts, sensor values, road conditions, or casualty information.

Your task:
1. Summarize the top priority villages.
2. Explain why each village needs attention.
3. Suggest field verification actions.
4. Suggest communication actions.
5. Point out data limitations.
6. Return concise Traditional Chinese output.

Input JSON:
{silent_risk_records}
```

### Example output style

```text
指揮建議摘要：

1. 優先確認：花蓮縣鳳林鎮鳳仁里
   - 原因：靜態災害風險偏高，且感測器覆蓋不足，近 6/24 小時無通報。
   - 建議：優先透過村里長、消防分隊或巡查人員確認現地狀況。

2. 次優先確認：花蓮縣玉里鎮啟模里
   - 原因：風險分數偏高，但目前缺乏通報資料。
   - 建議：確認道路、通訊與弱勢住戶狀況。

資料限制：
目前通報資料可能不完整，模型輸出代表優先關注順序，不等同於實際災情判定。
```

### Local Ollama setup

macOS / Linux:

```bash
ollama pull qwen2.5:7b
ollama serve
```

Windows PowerShell:

```powershell
ollama pull qwen2.5:7b
ollama serve
```

Recommended environment variables:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
```

### Minimal Python example

```python
import json
import os
import requests

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

records = [
    {
        "county_name": "花蓮縣",
        "town_name": "鳳林鎮",
        "village_name": "鳳仁里",
        "silent_risk_score": 0.392821,
        "silent_risk_level": "medium",
        "silent_reason": "靜態災害風險偏高；感測器覆蓋缺口偏高；近6小時無通報；近24小時無通報"
    }
]

prompt = f"""
你是防災應變指揮輔助助手。

請只根據以下 JSON 資料產生建議。
不要宣稱災害已經確定發生。
不要發布正式撤離命令。
不要編造資料中沒有的道路、傷亡、感測器或通報資訊。

請輸出：
1. 優先確認區域
2. 原因
3. 建議現地查證動作
4. 建議通訊聯繫動作
5. 資料限制

JSON:
{json.dumps(records, ensure_ascii=False, indent=2)}
"""

response = requests.post(
    f"{OLLAMA_BASE_URL}/api/generate",
    json={
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False
    },
    timeout=120,
)

response.raise_for_status()
print(response.json()["response"])
```

### Suggested future API endpoint

A future version can expose this advisor through FastAPI:

```text
GET /advisor/command?limit=5
```

Expected behavior:

```text
1. Read /silent-risk/top records.
2. Build a constrained prompt.
3. Call local Ollama.
4. Return command suggestions with data limitations.
```

This advisor should remain an **assistive briefing layer**, not an automated decision-maker.

