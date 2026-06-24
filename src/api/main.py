from pathlib import Path
import json
import subprocess
import sys
from typing import Optional

from fastapi import FastAPI, HTTPException, Query

from src.advisor.command_advisor import generate_command_advice
from src.advisor.ollama_client import OllamaError, check_ollama, get_ollama_settings

from src.api.output_metadata import (
    build_dataset_metadata,
    get_available_geojson_path as resolve_geojson_path,
    get_available_json_path as resolve_json_path,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_SCRIPT = PROJECT_ROOT / "scripts" / "run_pipeline.py"

app = FastAPI(
    title="Silent Disaster Zone Detection API",
    description=(
        "Detect high-risk but low-report villages "
        "in the Hualien MVP area."
    ),
    version="0.2.0",
)


def get_available_json_path():
    path = resolve_json_path()

    if path is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No silent risk JSON found. "
                "Run the pipeline or provide sample outputs."
            ),
        )

    return path


def get_available_geojson_path():
    path = resolve_geojson_path()

    if path is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No silent risk GeoJSON found. "
                "Run the pipeline or provide sample outputs."
            ),
        )

    return path


def load_silent_risk():
    json_path = get_available_json_path()

    with open(json_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise HTTPException(
            status_code=500,
            detail="silent_risk.json must contain a JSON list.",
        )

    return data, build_dataset_metadata(data)

def run_script(script_name: str):
    script_path = PROJECT_ROOT / "scripts" / script_name

    if not script_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Script not found: {script_name}",
        )

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
    )

    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"{script_name} failed.",
                "stdout_tail": result.stdout[-4000:],
                "stderr_tail": result.stderr[-4000:],
            },
        )

    return {
        "script": script_name,
        "stdout_tail": result.stdout[-2000:],
    }


def refresh_realtime_pipeline():
    steps = [
        "fetch_realtime_sources.py",
        "normalize_realtime_sources.py",
        "compute_silent_risk_realtime.py",
        "apply_silent_risk_nn.py",
    ]

    logs = []

    for step in steps:
        logs.append(run_script(step))

    return logs

@app.get("/")
def root():
    return {
        "name": "Silent Disaster Zone Detection API",
        "version": "0.1.0",
        "docs": "/docs",
        "endpoints": [
            "/health",
            "/silent-risk",
            "/silent-risk/top",
            "/silent-risk/{village_id}",
            "/silent-risk.geojson",
            "/pipeline/run",
        ],
    }


@app.get("/health")
def health():
    model_path = (
        PROJECT_ROOT
        / "models"
        / "silent_risk_mlp.joblib"
    )

    metadata_path = (
        PROJECT_ROOT
        / "models"
        / "silent_risk_mlp_metadata.json"
    )

    dataset = build_dataset_metadata()

    return {
        "status": (
            "ok"
            if dataset["availability"] == "ready"
            else "degraded"
        ),
        "dataset": dataset,
        "nn_model": {
            "exists": model_path.exists(),
            "metadata_exists": metadata_path.exists(),
        },
        "advisor": {
            "optional": True,
        },
    }

@app.get("/model/info")
def get_model_info():
    metadata_path = PROJECT_ROOT / "models" / "silent_risk_mlp_metadata.json"

    if not metadata_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Model metadata not found. Please train the model first.",
        )

    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    return metadata

@app.get("/silent-risk")
def get_silent_risk(
    level: Optional[str] = Query(default=None, description="low, medium, high, critical"),
    town_name: Optional[str] = Query(default=None, description="例如：鳳林鎮、玉里鎮"),
    refresh: bool = Query(default=False, description="是否先抓取即時資料並重算沉默風險"),
):
    refresh_logs = None

    if refresh:
        refresh_logs = refresh_realtime_pipeline()

    data, metadata = load_silent_risk()

    if level:
        data = [row for row in data if row.get("silent_risk_level") == level]

    if town_name:
        data = [row for row in data if row.get("town_name") == town_name]

    metadata["returned_count"] = len(data)

    return {
        "meta": metadata,
        "count": len(data),
        "refreshed": refresh,
        "data": data,
    }


@app.get("/silent-risk/top")
def get_top_silent_risk(
    limit: int = Query(default=10, ge=1, le=50),
    refresh: bool = Query(default=False, description="是否先抓取即時資料並重算沉默風險"),
):
    refresh_logs = None

    if refresh:
        refresh_logs = refresh_realtime_pipeline()

    data, metadata = load_silent_risk()

    data = sorted(
        data,
        key=lambda row: row.get("silent_risk_score", 0),
        reverse=True,
    )

    metadata["returned_count"] = min(limit, len(data))

    return {
        "meta": metadata,
        "count": min(limit, len(data)),
        "refreshed": refresh,
        "data": data[:limit],
    }


@app.get("/silent-risk/{village_id}")
def get_silent_risk_by_village(village_id: str):
    data, metadata = load_silent_risk()

    for row in data:
        if str(row.get("village_id")) == str(village_id):
            metadata["returned_count"] = 1

            return {
                "meta": metadata,
                "data": row,
            }

    raise HTTPException(
        status_code=404,
        detail=f"village_id not found: {village_id}",
    )


@app.get("/silent-risk.geojson")
def get_silent_risk_geojson():
    geojson_path = get_available_geojson_path()

    with open(geojson_path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.post("/pipeline/run")
def run_pipeline():
    if not PIPELINE_SCRIPT.exists():
        raise HTTPException(
            status_code=404,
            detail="scripts/run_pipeline.py not found.",
        )

    result = subprocess.run(
        [sys.executable, str(PIPELINE_SCRIPT)],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
    )

    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Pipeline failed.",
                "stdout_tail": result.stdout[-4000:],
                "stderr_tail": result.stderr[-4000:],
            },
        )

    return {
        "status": "success",
        "message": "Pipeline completed successfully.",
        "outputs": [
            "outputs/latest/silent_risk.json",
            "outputs/latest/silent_risk.csv",
            "outputs/latest/silent_risk.geojson",
            "outputs/latest/run_manifest.json",
        ],
        "meta": build_dataset_metadata(),
    }

@app.get("/advisor/health")
def advisor_health():
    status = check_ollama()

    return {
        "status": "ok" if status["available"] else "unavailable",
        "ollama": status,
        "note": (
            "Ollama advisor is optional. "
            "The silent-risk API can still run even if Ollama is unavailable."
        ),
    }

@app.get("/advisor/command")
def get_command_advice(
    limit: int = Query(default=5, ge=1, le=10),
    refresh: bool = Query(default=False, description="是否先抓取即時資料並重算沉默風險"),
):
    refresh_logs = None

    if refresh:
        refresh_logs = refresh_realtime_pipeline()

    data, metadata = load_silent_risk()

    try:
        advice_result = generate_command_advice(
            records=data,
            limit=limit,
        )

        return {
            "status": "success",
            "refreshed": refresh,
            "advisor_type": "ollama_local_llm",
            "model": advice_result["model"],
            "base_url": advice_result["base_url"],
            "selected_villages": advice_result["selected_villages"],
            "advice": advice_result["advice"],
            "meta": metadata,
            "disclaimer": (
                "This is an AI-generated command briefing for decision support only. "
                "It is not an official disaster declaration or evacuation order."
            ),
        }

    except OllamaError as e:
        settings = get_ollama_settings()

        raise HTTPException(
            status_code=503,
            detail={
                "message": "Ollama advisor is unavailable.",
                "error": str(e),
                "expected_base_url": settings["base_url"],
                "configured_model": settings["model"],
                "how_to_fix": [
                    "Install Ollama.",
                    "Run: ollama serve",
                    f"Run: ollama pull {settings['model']}",
                    "Then call /advisor/health again.",
                ],
            },
        )