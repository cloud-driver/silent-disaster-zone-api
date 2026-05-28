from pathlib import Path
import geopandas as gpd
from shapely.validation import make_valid


debris_path = Path("data/raw/debris_flow/area/debris1745_20250114_twd97_UTF8.shp")
villages_path = Path("data/processed/villages_hualien_with_flood_final.geojson")

output_geojson_path = Path("data/processed/debris_area_hualien.geojson")
output_csv_path = Path("data/processed/debris_area_hualien.csv")


def repair_geometry(geometry):
    if geometry is None or geometry.is_empty:
        return geometry

    if geometry.is_valid:
        return geometry

    try:
        return make_valid(geometry)
    except Exception:
        return geometry.buffer(0)


print("=== 1. 讀取土石流影響範圍 polygon ===")

if not debris_path.exists():
    raise FileNotFoundError(f"找不到檔案：{debris_path}")

debris = gpd.read_file(debris_path, encoding="big5")

print("原始筆數：", len(debris))
print("原始 CRS：", debris.crs)
print("原始欄位：", debris.columns.tolist())
print("geometry 類型：")
print(debris.geometry.geom_type.value_counts())
print("修復前無效 geometry 數量：", int((~debris.geometry.is_valid).sum()))
print("空 geometry 數量：", int(debris.geometry.is_empty.sum()))


print("\n=== 2. 讀取花蓮村里主表 ===")

villages = gpd.read_file(villages_path)

print("花蓮村里筆數：", len(villages))
print("村里 CRS：", villages.crs)


if debris.crs is None:
    raise ValueError("土石流資料缺 CRS，不能繼續。")

if villages.crs is None:
    raise ValueError("村里資料缺 CRS，不能繼續。")


print("\n=== 3. 修復土石流 geometry ===")

debris["geometry"] = debris["geometry"].apply(repair_geometry)

print("修復後無效 geometry 數量：", int((~debris.geometry.is_valid).sum()))
print("修復後空 geometry 數量：", int(debris.geometry.is_empty.sum()))


print("\n=== 4. explode 並只保留 polygon ===")

debris = debris.explode(index_parts=False).reset_index(drop=True)

print("explode 後筆數：", len(debris))
print("explode 後 geometry 類型：")
print(debris.geometry.geom_type.value_counts())

debris = debris[debris.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].copy()

print("保留 polygon 後筆數：", len(debris))


print("\n=== 5. 用空間關係篩選花蓮縣範圍 ===")

# 轉成同一 CRS。這裡使用 EPSG:3826 做空間運算。
debris_m = debris.to_crs(epsg=3826)
villages_m = villages.to_crs(epsg=3826)

# 只要土石流 polygon 和花蓮村里有相交，就視為花蓮相關資料
joined = gpd.sjoin(
    debris_m,
    villages_m[["village_id", "county_name", "town_name", "village_name", "geometry"]],
    how="inner",
    predicate="intersects"
)

print("空間 join 後筆數：", len(joined))

if len(joined) == 0:
    raise ValueError("找不到和花蓮村里相交的土石流 polygon，請檢查 CRS 或資料範圍。")


print("\n=== 6. 去除重複 polygon ===")

# 同一個土石流 polygon 可能跨多個村里，sjoin 會變多筆。
# 這裡用原始 index 去重，先保留唯一 polygon。
joined["source_index"] = joined.index

# 更穩的方式：用 geometry WKB 去重
joined["geometry_key"] = joined.geometry.apply(lambda g: g.wkb_hex)

hualien_debris = joined.drop_duplicates(subset=["geometry_key"]).copy()

print("去重後花蓮土石流 polygon 數：", len(hualien_debris))


print("\n=== 7. 建立標準欄位 ===")

# 不依賴亂碼文字欄位，只保留穩定欄位與 geometry
keep_columns = []

for col in ["ID", "Debrisno", "Total_Res", "Res_Class", "Risk", "Dbno_old"]:
    if col in hualien_debris.columns:
        keep_columns.append(col)

hualien_debris = hualien_debris[keep_columns + ["geometry"]].copy()

hualien_debris = hualien_debris.rename(
    columns={
        "ID": "debris_id",
        "Debrisno": "debris_no",
        "Total_Res": "total_residents_exposed",
        "Res_Class": "resident_class",
        "Risk": "source_risk",
        "Dbno_old": "old_debris_no",
    }
)

# 加一個固定欄位，說明這是 polygon 影響範圍資料
hualien_debris["debris_source_type"] = "area_polygon"

# 轉成 4326 給地圖/API 使用
hualien_debris_4326 = hualien_debris.to_crs(epsg=4326)

print("輸出 CRS：", hualien_debris_4326.crs)
print("輸出 bounds：", hualien_debris_4326.total_bounds)
print("輸出欄位：", hualien_debris_4326.columns.tolist())
print("輸出 geometry 類型：")
print(hualien_debris_4326.geometry.geom_type.value_counts())


print("\n=== 8. 輸出資料 ===")

output_geojson_path.parent.mkdir(parents=True, exist_ok=True)

hualien_debris_4326.to_file(output_geojson_path, driver="GeoJSON")

hualien_debris_4326.drop(columns=["geometry"]).to_csv(
    output_csv_path,
    index=False,
    encoding="utf-8-sig"
)

print("完成：", output_geojson_path)
print("完成：", output_csv_path)