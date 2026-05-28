# src/ingest/village_boundary.py

import geopandas as gpd
from pathlib import Path

def load_villages(raw_path: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(raw_path)

    if gdf.crs is None:
        raise ValueError("村里界缺 CRS，請確認 .prj 或原始資料說明")

    gdf = gdf.to_crs(epsg=4326)

    print("村里界欄位：", gdf.columns.tolist())

    # 這裡先不要硬寫欄位名，因為你要先實際看欄位
    return gdf

def normalize_villages(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    # 你要依實際欄位名稱改這裡
    rename_map = {
        "COUNTYNAME": "county_name",
        "TOWNNAME": "town_name",
        "VILLNAME": "village_name",
        "VILLCODE": "village_id"
    }

    existing = {k: v for k, v in rename_map.items() if k in gdf.columns}
    gdf = gdf.rename(columns=existing)

    required = ["county_name", "town_name", "village_name", "geometry"]
    missing = [c for c in required if c not in gdf.columns]
    if missing:
        raise ValueError(f"村里界缺必要欄位：{missing}")

    if "village_id" not in gdf.columns:
        gdf["village_id"] = (
            gdf["county_name"].astype(str)
            + "_"
            + gdf["town_name"].astype(str)
            + "_"
            + gdf["village_name"].astype(str)
        )

    return gdf[["village_id", "county_name", "town_name", "village_name", "geometry"]]

def save_villages(gdf: gpd.GeoDataFrame, output_path: str):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(output_path, driver="GeoJSON")