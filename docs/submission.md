# 防災積木元件創新賽投稿說明

## 作品名稱

沉默災區偵測 API：高風險但低通報區域辨識元件

## 一句話介紹

本元件用公開災害資料、人口脆弱度、即時感測與通報資料，找出「本來應該被注意，但目前缺乏通報或觀測覆蓋」的村里，協助災防單位優先派員確認。

## 核心問題

災情通報多的地方不一定最危險；真正危險的地方，可能因為斷訊、交通中斷、高齡人口比例高、感測器覆蓋不足或數位通報能力低，反而沒有即時回報。

因此，本元件不是只看「哪裡有通報」，而是找出「高風險但低通報」的沉默災區候選點。

## 元件定位

本作品定位為可重複使用的防災 API 元件，而不是完整防災平台。

它可以被接到：

- 災害應變儀表板
- 地圖系統
- LINE Bot 通報系統
- 地方政府災情查報流程
- 巡查任務派發系統

## Input

目前 MVP 使用以下資料：

- 村里界圖資
- 人口與高齡比例資料
- 淹水潛勢圖
- 土石流影響範圍圖
- 中央氣象署即時雨量資料
- 農村水保署土石流警戒與雨量資料
- 警廣即時路況資料
- mock 災情通報資料

## Process

系統流程包含：

1. 靜態資料清洗與空間標準化
2. 村里層級人口與高齡脆弱度計算
3. 淹水與土石流風險特徵計算
4. 即時 API 快照抓取與歷史保存
5. 即時雨量、土石流、路況資料轉成村里層級特徵
6. 通報資料空間 join 到村里
7. 產生沉默風險分數
8. 透過 FastAPI 輸出 JSON、CSV、GeoJSON

## Output

元件輸出：

- `silent_risk.json`
- `silent_risk.csv`
- `silent_risk.geojson`

主要欄位：

- `village_id`
- `county_name`
- `town_name`
- `village_name`
- `silent_risk_score`
- `silent_risk_level`
- `silent_reason`
- `silent_risk_rule_score`
- `silent_risk_nn_score`

## API Endpoints

- `GET /health`
- `GET /model/info`
- `GET /silent-risk/top?limit=5`
- `GET /silent-risk/top?limit=5&refresh=true`
- `GET /silent-risk/{village_id}`
- `GET /silent-risk.geojson`

## AI 使用方式

MVP 階段使用規則式分數產生 pseudo-label，訓練 MLPRegressor 神經網路模型作為 scoring layer，驗證未來可替換模型的架構。

目前神經網路不是使用真實災害 ground truth 訓練，因此不宣稱能準確預測真實災情。正式版可使用歷史災情、巡查結果、救災派遣紀錄或通報延遲資料重新訓練。

## MVP 限制

- 通報資料目前為 mock data。
- 神經網路目前使用 pseudo-label，不是真實災害標籤。
- WRA 水利署水位資料尚未完成串接。
- 路況事件嚴重程度目前使用關鍵字規則。
- 本元件輸出的是優先關注清單，不等同於實際災情判定。

## GitHub

https://github.com/cloud-driver/silent-disaster-zone-api
