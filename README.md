# Silent Disaster Zone Detection API

沉默災區偵測 API 是一個防災資料分析元件，用來找出「高風險但低通報、低觀測覆蓋」的村里。

本專案的核心想法是：災情通報多的地方不一定最危險；真正需要被注意的地方，可能因為斷訊、交通中斷、高齡人口比例高、感測器覆蓋不足或數位通報能力低，反而沒有即時回報。

本元件不是要取代災害預測模型，而是提供一個可重複使用的 API 元件，協助防災系統優先找出需要主動確認的區域。

---

## Features

- 整合村里界、人口、高齡比例、淹水潛勢、土石流影響範圍。
- 串接即時資料來源，包括中央氣象署雨量、農村水保署土石流資料、警廣即時路況。
- 每次即時更新都保存 raw snapshot 與 history output。
- 產出 `silent_risk.json`、`silent_risk.csv`、`silent_risk.geojson`。
- 提供 FastAPI 查詢介面。
- 支援神經網路 scoring layer。
- 保留規則式分數與神經網路分數，方便比較與解釋。

---

## Problem

傳統災情系統通常依賴「已通報資料」來判斷災情熱區，但高風險區可能因為以下原因沒有通報：

- 通訊中斷
- 老年人口比例高
- 交通中斷
- 感測器覆蓋不足
- 數位通報能力不足
- 地方災情尚未被回報

因此，本元件關注的是：

> 高風險，但低通報或低觀測覆蓋的區域。

---

## MVP Scope

目前 MVP 範圍為花蓮縣村里層級分析。

分析單位：

- village_id
- county_name
- town_name
- village_name

主要輸出：

- silent_risk_score
- silent_risk_level
- silent_reason
- silent_risk_rule_score
- silent_risk_nn_score

---

## Data Sources

### Static / Low-frequency Data

- 村里界圖資
- 人口與年齡結構資料
- 淹水潛勢圖
- 土石流影響範圍圖

### Realtime / Snapshot Data

- 中央氣象署雨量觀測資料
- 農村水保署土石流及大規模崩塌警戒資料
- 農村水保署土石流潛勢溪流參考雨量資料
- 警廣即時路況資料

### Mock Data

目前通報資料使用 mock reports，用於驗證「高風險但低通報」偵測邏輯。正式版可串接 LINE Bot、119、1999、地方災情通報系統或表單通報資料。

---

## Pipeline

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

---

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `.env` from `.env.example`:

```bash
cp .env.example .env
```

Then fill in your own API key:

```bash
CWA_API_KEY=your_cwa_api_key_here
```

Do not commit `.env`.

---

## Run Realtime Pipeline

```bash
python3 scripts/fetch_realtime_sources.py
python3 scripts/normalize_realtime_sources.py
python3 scripts/compute_silent_risk_realtime.py
python3 scripts/apply_silent_risk_nn.py
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

---

## Run API

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

## Example Output

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

## AI Scoring Layer

MVP 階段使用規則式分數產生 pseudo-label，訓練 MLPRegressor 神經網路模型，驗證 scoring layer 可替換架構。

目前模型不是使用真實災害 ground truth 訓練，因此不能宣稱能準確預測真實災情。

正式版可使用以下資料重新訓練：

* 歷史災情紀錄
* 巡查結果
* 通報延遲資料
* 救災派遣紀錄
* 專家標註的高優先巡查區

---

## Limitations

* 通報資料目前為 mock data。
* 神經網路目前使用 pseudo-label，不是真實災害標籤。
* 即時 API 可能受外部服務可用性影響。
* WRA 水利署水位資料尚未完成串接。
* 路況事件分數目前為關鍵字規則，仍需進一步細分事件嚴重程度。
* 本元件提供優先關注清單，不直接等同實際災情判定。

---

## Project Status

Current status: MVP completed.

The project can currently:

* fetch realtime data,
* preserve raw snapshots,
* generate realtime village-level features,
* compute silent risk scores,
* output JSON / CSV / GeoJSON,
* serve results through FastAPI.

---

## Documentation

Additional documentation:

- [API Documentation](docs/api.md)
- [Model Card](docs/model.md)
- [Silent Risk JSON Schema](docs/schemas/silent_risk.schema.json)
- [Report Input JSON Schema](docs/schemas/report_input.schema.json)

---

## Reproducing the Neural Network Scoring Layer

Before running the API with NN scoring, train the model once:

```bash
python3 scripts/train_silent_risk_nn.py
```

Then run realtime scoring:

```bash
python3 scripts/fetch_realtime_sources.py
python3 scripts/normalize_realtime_sources.py
python3 scripts/compute_silent_risk_realtime.py
python3 scripts/apply_silent_risk_nn.py
```

The API `refresh=true` mode will run the realtime refresh pipeline and apply the NN scoring layer if the trained model exists.

---

## Quick Demo Without Raw Data

This repository does not commit raw government datasets or generated runtime outputs.

For quick review, the API automatically falls back to files in `sample_outputs/` when `outputs/latest/` does not exist.

So after cloning the repository, reviewers can run:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn src.api.main:app --reload
````

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

To run with fresh realtime data, create `.env` from `.env.example`, add your CWA API key, then use:

```text
GET /silent-risk/top?limit=5&refresh=true
```