# API Documentation

Base URL for local development:

```text
http://127.0.0.1:8000
```

Interactive API docs:

```text
http://127.0.0.1:8000/docs
```

---

## GET /health

Check API and output availability.

### Example

```bash
curl http://127.0.0.1:8000/health
```

### Response Example

```json
{
  "status": "ok",
  "silent_risk_json_exists": true,
  "silent_risk_geojson_exists": true,
  "nn_model_exists": true,
  "nn_model_metadata_exists": true
}
```

---

## GET /model/info

Return neural network model metadata.

### Example

```bash
curl http://127.0.0.1:8000/model/info
```

---

## GET /silent-risk/top

Return top silent-risk villages.

### Query Parameters

| Name    | Type    | Required | Description                                                                                                         |
| ------- | ------- | -------- | ------------------------------------------------------------------------------------------------------------------- |
| limit   | integer | no       | Number of records to return. Default: 10                                                                            |
| refresh | boolean | no       | If true, fetch realtime sources, normalize features, recompute risk, and apply NN scoring before returning results. |

### Example

```bash
curl "http://127.0.0.1:8000/silent-risk/top?limit=5"
```

### Realtime Refresh Example

```bash
curl "http://127.0.0.1:8000/silent-risk/top?limit=5&refresh=true"
```

---

## GET /silent-risk

Return silent-risk villages with optional filters.

### Query Parameters

| Name      | Type    | Required | Description                                            |
| --------- | ------- | -------- | ------------------------------------------------------ |
| level     | string  | no       | Filter by risk level: low, medium, high, critical      |
| town_name | string  | no       | Filter by township name, e.g. 鳳林鎮                      |
| refresh   | boolean | no       | If true, run realtime refresh before returning results |

### Example

```bash
curl "http://127.0.0.1:8000/silent-risk?level=medium"
```

---

## GET /silent-risk/{village_id}

Return one village by village_id.

### Example

```bash
curl http://127.0.0.1:8000/silent-risk/10015020001
```

---

## GET /silent-risk.geojson

Return GeoJSON layer for map display.

### Example

```bash
curl http://127.0.0.1:8000/silent-risk.geojson
```

---

## Notes

`refresh=true` is designed for demo and internal testing.

For production deployment, realtime refresh should be moved to a scheduled background job, while query endpoints should only read `outputs/latest/`.