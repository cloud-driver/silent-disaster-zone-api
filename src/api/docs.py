from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.docs import (
    get_redoc_html,
    get_swagger_ui_html,
)
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse


TAGS_METADATA = [
    {
        "name": "00 · System & Documentation",
        "description": (
            "系統資訊、健康狀態、模型資訊與 API 文件入口。"
        ),
    },
    {
        "name": "01 · Authentication",
        "description": (
            "短效 Bearer Token 的登入、狀態查詢與撤銷。"
        ),
    },
    {
        "name": "10 · Silent Risk Detection",
        "description": (
            "沉默災區偵測資料。"
            "用於辨識高風險、低觀測或低通報的村里。"
        ),
    },
    {
        "name": "20 · Command Decision Support",
        "description": (
            "規則式優先隊列與 AI 摘要。"
            "僅供人工確認、巡查與資源準備參考。"
        ),
    },
    {
        "name": "30 · Citizen Reports · Admin",
        "description": (
            "LINE 民眾回報的統計、待審核清單與人工驗證流程。"
            "部分端點需要 X-Admin-Key。"
        ),
    },
    {
        "name": "40 · Verified Incidents · Admin",
        "description": (
            "已由人工查證且可對應村里的事件 snapshot。"
            "需要 X-Admin-Key。"
        ),
    },
    {
        "name": "50 · LINE Integration",
        "description": (
            "LINE 官方帳號 webhook 與設定健康狀態。"
        ),
    },
    {
        "name": "90 · Internal Operations · Admin",
        "description": (
            "會重新執行 pipeline 或改變系統資料的管理操作。"
            "禁止提供給一般使用者。"
        ),
    },
]


def input_item(
    name: str,
    location: str,
    required: bool,
    default: str,
    description: str,
    example: str = "",
) -> dict[str, str | bool]:
    return {
        "name": name,
        "location": location,
        "required": required,
        "default": default,
        "description": description,
        "example": example,
    }


API_OPERATIONS: dict[
    tuple[str, str],
    dict[str, Any],
] = {
    ("post", "/auth/login"): {
        "number": "01-1",
        "tag": "01 · Authentication",
        "title": "登入並取得 15 分鐘 Token",
        "purpose": (
            "使用帳號與密碼登入。"
            "成功後回傳唯一 Bearer Token，固定有效 15 分鐘。"
        ),
        "inputs": [
            input_item(
                name="username",
                location="JSON body",
                required=True,
                default="無，必填",
                description="API 登入帳號。",
                example="api-admin",
            ),
            input_item(
                name="password",
                location="JSON body",
                required=True,
                default="無，必填",
                description=(
                    "API 登入密碼。"
                    "同一 IP 一分鐘最多可呼叫登入 API 5 次。"
                ),
                example="不應公開展示",
            ),
        ],
    },
    ("get", "/auth/session"): {
        "number": "01-2",
        "tag": "01 · Authentication",
        "title": "查詢目前 Token 狀態",
        "purpose": (
            "確認目前 Bearer Token 是否仍有效，"
            "並回傳到期時間。"
        ),
        "inputs": [],
    },
    ("post", "/auth/logout"): {
        "number": "01-3",
        "tag": "01 · Authentication",
        "title": "撤銷目前 Token",
        "purpose": (
            "立即撤銷目前 Bearer Token。"
            "撤銷後需重新登入。"
        ),
        "inputs": [],
    },
    ("get", "/"): {
        "number": "00-1",
        "tag": "00 · System & Documentation",
        "title": "取得 API 入口資訊",
        "purpose": (
            "回傳 API 名稱、版本、文件入口與主要端點清單。"
        ),
        "inputs": [],
    },
    ("get", "/health"): {
        "number": "00-2",
        "tag": "00 · System & Documentation",
        "title": "取得系統健康狀態",
        "purpose": (
            "檢查目前資料集、輸出檔案、模型與 advisor 狀態。"
        ),
        "inputs": [],
    },
    ("get", "/model/info"): {
        "number": "00-3",
        "tag": "00 · System & Documentation",
        "title": "取得實驗模型 metadata",
        "purpose": (
            "讀取神經網路實驗模型資訊。"
            "正式排序仍以 rule-based MVP 為主。"
        ),
        "inputs": [],
    },
    ("get", "/silent-risk"): {
        "number": "10-1",
        "tag": "10 · Silent Risk Detection",
        "title": "查詢沉默災區風險清單",
        "purpose": (
            "查詢所有村里的沉默風險，"
            "可依風險等級或鄉鎮名稱篩選。"
        ),
        "inputs": [
            input_item(
                name="level",
                location="query",
                required=False,
                default="null",
                description=(
                    "只回傳指定沉默風險等級。"
                    "可用值：low、medium、high、critical。"
                ),
                example="high",
            ),
            input_item(
                name="town_name",
                location="query",
                required=False,
                default="null",
                description=(
                    "以完整鄉鎮名稱篩選，例如鳳林鎮、玉里鎮。"
                ),
                example="鳳林鎮",
            ),
            input_item(
                name="refresh",
                location="query",
                required=False,
                default="false",
                description=(
                    "是否先執行 realtime pipeline 再讀取結果。"
                    "正式環境應由管理者操作。"
                ),
                example="false",
            ),
        ],
    },
    ("get", "/silent-risk/top"): {
        "number": "10-2",
        "tag": "10 · Silent Risk Detection",
        "title": "取得沉默風險最高村里",
        "purpose": (
            "依 silent_risk_score 由高到低取得前幾名村里。"
        ),
        "inputs": [
            input_item(
                name="limit",
                location="query",
                required=False,
                default="10",
                description=(
                    "回傳筆數，允許範圍為 1 至 50。"
                ),
                example="5",
            ),
            input_item(
                name="refresh",
                location="query",
                required=False,
                default="false",
                description=(
                    "是否先執行 realtime pipeline 再讀取結果。"
                ),
                example="false",
            ),
        ],
    },
    ("get", "/silent-risk/{village_id}"): {
        "number": "10-3",
        "tag": "10 · Silent Risk Detection",
        "title": "查詢單一村里沉默風險",
        "purpose": (
            "依 village_id 取得單一村里的最新沉默風險資料。"
        ),
        "inputs": [
            input_item(
                name="village_id",
                location="path",
                required=True,
                default="無，必填",
                description=(
                    "村里唯一識別碼。"
                    "可由 /silent-risk 或 /silent-risk/top 查得。"
                ),
                example="10015020001",
            ),
        ],
    },
    ("get", "/silent-risk.geojson"): {
        "number": "10-4",
        "tag": "10 · Silent Risk Detection",
        "title": "取得沉默風險 GeoJSON",
        "purpose": (
            "提供 GIS、地圖前端與外部元件使用的 GeoJSON。"
        ),
        "inputs": [],
    },
    ("get", "/advisor/health"): {
        "number": "20-1",
        "tag": "20 · Command Decision Support",
        "title": "檢查 AI 摘要服務狀態",
        "purpose": (
            "檢查 Ollama 是否可用。"
            "Ollama 不可用時，規則式 command plan 仍可使用。"
        ),
        "inputs": [],
    },
    ("get", "/advisor/command"): {
        "number": "20-2",
        "tag": "20 · Command Decision Support",
        "title": "取得雙隊列指揮建議",
        "purpose": (
            "回傳 silent watch queue、verified incident queue、"
            "規則式 command plan 與 AI 摘要。"
        ),
        "inputs": [
            input_item(
                name="limit",
                location="query",
                required=False,
                default="5",
                description=(
                    "每條隊列最多回傳幾個區域。"
                    "允許範圍為 1 至 10。"
                ),
                example="5",
            ),
            input_item(
                name="refresh",
                location="query",
                required=False,
                default="false",
                description=(
                    "是否先執行 realtime pipeline。"
                    "建議在管理操作後使用。"
                ),
                example="false",
            ),
        ],
    },
    ("get", "/reports/summary"): {
        "number": "30-1",
        "tag": "30 · Citizen Reports · Admin",
        "title": "取得民眾回報統計",
        "purpose": (
            "統計 pending、verified、rejected 的通報數量。"
        ),
        "inputs": [],
    },
    ("get", "/reports/pending"): {
        "number": "30-2",
        "tag": "30 · Citizen Reports · Admin",
        "title": "取得待人工審核通報",
        "purpose": (
            "列出 pending 通報，供管理者確認或拒絕。"
        ),
        "inputs": [
            input_item(
                name="X-Admin-Key",
                location="header",
                required=True,
                default="無，必填",
                description=(
                    "管理者 API 金鑰。"
                    "可透過 Swagger 的 Authorize 設定。"
                ),
                example="不應公開展示",
            ),
            input_item(
                name="limit",
                location="query",
                required=False,
                default="50",
                description=(
                    "回傳筆數，允許範圍為 1 至 200。"
                ),
                example="20",
            ),
        ],
    },
    ("post", "/reports/{report_id}/review"): {
        "number": "30-3",
        "tag": "30 · Citizen Reports · Admin",
        "title": "人工審核單筆民眾回報",
        "purpose": (
            "將 pending 通報標示為 verified 或 rejected。"
            "只有 verified 通報會進入後續 realtime pipeline。"
        ),
        "inputs": [
            input_item(
                name="X-Admin-Key",
                location="header",
                required=True,
                default="無，必填",
                description="管理者 API 金鑰。",
                example="不應公開展示",
            ),
            input_item(
                name="report_id",
                location="path",
                required=True,
                default="無，必填",
                description=(
                    "欲審核的通報編號，例如 RPT-XXXXXXXXXXXX。"
                ),
                example="RPT-AB12CD34EF56",
            ),
            input_item(
                name="decision",
                location="JSON body",
                required=True,
                default="無，必填",
                description=(
                    "審核結果，只能填 verified 或 rejected。"
                ),
                example="verified",
            ),
            input_item(
                name="reviewer_id",
                location="JSON body",
                required=False,
                default="admin",
                description="執行審核的人員識別名稱。",
                example="duty-officer",
            ),
            input_item(
                name="reviewer_note",
                location="JSON body",
                required=False,
                default='""',
                description="人工審核備註，最長 1000 字。",
                example="已由里長確認道路積水。",
            ),
        ],
    },
    ("get", "/incidents/verified"): {
        "number": "40-1",
        "tag": "40 · Verified Incidents · Admin",
        "title": "取得已驗證事件 snapshot",
        "purpose": (
            "讀取最新 realtime pipeline 產生的 verified incident 資料。"
        ),
        "inputs": [
            input_item(
                name="X-Admin-Key",
                location="header",
                required=True,
                default="無，必填",
                description="管理者 API 金鑰。",
                example="不應公開展示",
            ),
            input_item(
                name="limit",
                location="query",
                required=False,
                default="20",
                description=(
                    "回傳筆數，允許範圍為 1 至 100。"
                ),
                example="20",
            ),
        ],
    },
    ("get", "/line/health"): {
        "number": "50-1",
        "tag": "50 · LINE Integration",
        "title": "檢查 LINE 設定狀態",
        "purpose": (
            "檢查 LINE Channel Secret、Access Token、"
            "Reporter Hash Secret 是否已設定。"
        ),
        "inputs": [],
    },
    ("post", "/line/webhook"): {
        "number": "50-2",
        "tag": "50 · LINE Integration",
        "title": "接收 LINE Messaging API webhook",
        "purpose": (
            "僅供 LINE Platform 呼叫。"
            "不得用 Swagger UI 手動模擬真實 webhook。"
        ),
        "inputs": [
            input_item(
                name="X-Line-Signature",
                location="header",
                required=True,
                default="無，必填",
                description=(
                    "由 LINE Platform 依原始 request body "
                    "與 Channel Secret 產生的簽章。"
                ),
                example="由 LINE 自動帶入",
            ),
            input_item(
                name="request body",
                location="JSON body",
                required=True,
                default="無，必填",
                description=(
                    "LINE Platform 發送的 events payload。"
                    "不可自行偽造正式測試資料。"
                ),
                example='{"events": [...]}',
            ),
        ],
    },
    ("post", "/pipeline/run"): {
        "number": "90-1",
        "tag": "90 · Internal Operations · Admin",
        "title": "執行完整 batch pipeline",
        "purpose": (
            "重新執行完整批次資料流程，並更新 latest output。"
        ),
        "inputs": [
            input_item(
                name="X-Admin-Key",
                location="header",
                required=True,
                default="無，必填",
                description="管理者 API 金鑰。",
                example="不應公開展示",
            ),
        ],
    },
}


ADMIN_OPERATIONS = {
    ("get", "/reports/pending"),
    ("post", "/reports/{report_id}/review"),
    ("get", "/incidents/verified"),
    ("post", "/pipeline/run"),
}

PUBLIC_API_OPERATIONS = {
    ("post", "/auth/login"),
    ("get", "/health"),
    ("get", "/advisor/health"),
    ("get", "/line/health"),
    ("post", "/line/webhook"),
}

BEARER_TOKEN_INPUT = input_item(
    name="Authorization",
    location="header",
    required=True,
    default="無，必填",
    description=(
        "短效登入 Token。"
        "格式：Bearer <access_token>。"
        "Token 固定有效 15 分鐘。"
    ),
    example="Bearer eyJ... 或其他登入後取得的 token",
)

SWAGGER_UI_PARAMETERS = {
    "docExpansion": "list",
    "deepLinking": True,
    "displayRequestDuration": True,
    "filter": True,
    "persistAuthorization": True,
    "tryItOutEnabled": True,
    "defaultModelsExpandDepth": 1,
    "defaultModelExpandDepth": 2,
    "syntaxHighlight": {
        "theme": "obsidian",
    },
}


PORTAL_CSS = """
<style>
:root {
    --portal-navy: #0b1f3a;
    --portal-blue: #1769aa;
    --portal-cyan: #20a4c5;
    --portal-bg: #f4f7fb;
}

body {
    background: var(--portal-bg);
}

.portal-banner {
    background:
        linear-gradient(
            135deg,
            var(--portal-navy),
            var(--portal-blue)
        );
    color: #ffffff;
    padding: 22px 28px;
    font-family: Arial, sans-serif;
}

.portal-banner h1 {
    margin: 0 0 8px;
    font-size: 22px;
}

.portal-banner p {
    margin: 0;
    max-width: 960px;
    line-height: 1.65;
    opacity: 0.96;
}

.swagger-ui .topbar {
    background-color: var(--portal-navy);
}

.swagger-ui .topbar .download-url-wrapper {
    display: none;
}

.swagger-ui .info .title {
    color: var(--portal-navy);
}

.swagger-ui .opblock-tag {
    font-size: 17px;
    color: var(--portal-navy);
}

.swagger-ui .scheme-container {
    background: #ffffff;
    box-shadow: none;
    border-top: 1px solid #dbe4ef;
    border-bottom: 1px solid #dbe4ef;
}

.swagger-ui .opblock.opblock-get {
    border-color: #3b82f6;
    background: rgba(59, 130, 246, 0.06);
}

.swagger-ui .opblock.opblock-post {
    border-color: #10b981;
    background: rgba(16, 185, 129, 0.06);
}

.swagger-ui .btn.authorize {
    border-color: var(--portal-blue);
    color: var(--portal-blue);
}
</style>
"""


def escape_markdown(value: Any) -> str:
    return str(value).replace("|", "\\|")


def build_input_table(
    inputs: list[dict[str, str | bool]],
) -> str:
    if not inputs:
        return (
            "### 輸入欄位\n\n"
            "此 API 不需要使用者輸入任何欄位。"
        )

    lines = [
        "### 輸入欄位",
        "",
        "| 欄位 | 傳遞位置 | 必填 | 預設值 | 說明 | 範例 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    for item in inputs:
        required_text = (
            "是" if item["required"] else "否"
        )

        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{escape_markdown(item['name'])}`",
                    escape_markdown(item["location"]),
                    required_text,
                    f"`{escape_markdown(item['default'])}`",
                    escape_markdown(item["description"]),
                    f"`{escape_markdown(item['example'])}`",
                ]
            )
            + " |"
        )

    return "\n".join(lines)


def enrich_parameter(
    parameter: dict[str, Any],
    input_metadata: dict[str, str | bool],
) -> None:
    required_text = (
        "是" if input_metadata["required"] else "否"
    )

    parameter["description"] = (
        f"{input_metadata['description']}\n\n"
        f"**必填：** {required_text}\n\n"
        f"**預設值：** `{input_metadata['default']}`"
    )

    parameter["required"] = bool(
        input_metadata["required"]
    )

    example = str(
        input_metadata.get("example", "")
    ).strip()

    if example:
        parameter["example"] = example


def apply_parameter_metadata(
    operation: dict[str, Any],
    inputs: list[dict[str, str | bool]],
) -> None:
    generated_parameters = operation.get(
        "parameters",
        [],
    )

    for parameter in generated_parameters:
        parameter_name = parameter.get("name")
        parameter_location = parameter.get("in")

        for item in inputs:
            if (
                item["name"] == parameter_name
                and item["location"] == parameter_location
            ):
                enrich_parameter(parameter, item)


def configure_openapi(app: FastAPI) -> None:
    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            summary=(
                "沉默災區偵測、LINE 民眾回報、"
                "已驗證事件與指揮建議 API"
            ),
            description="""
## API 使用原則

- `10 · Silent Risk Detection`：高風險、低觀測、低通報的主動確認候選。
- `20 · Command Decision Support`：規則式隊列與 AI 中性摘要。
- `30 · Citizen Reports`：民眾回報與人工審核流程。
- `40 · Verified Incidents`：已完成審核的事件資料。
- `50 · LINE Integration`：LINE 官方帳號 webhook。
- `90 · Internal Operations`：管理操作，禁止提供一般使用者。

## 權限說明

標示為 Admin 的 API 必須在 Swagger UI 右上角點選
`Authorize`，輸入 `X-Admin-Key`。

## 安全界線

本系統只提供人工確認、巡查與資源準備參考，
不得直接作為撤離、封路、停班停課或其他強制命令依據。
            """.strip(),
            routes=app.routes,
            tags=TAGS_METADATA,
        )

        schema["info"]["contact"] = {
            "name": "Islewise Tech",
            "url": (
                "https://github.com/cloud-driver/"
                "silent-disaster-zone-api"
            ),
        }

        schema["servers"] = [
            {
                "url": "/",
                "description": "目前部署環境",
            }
        ]

        components = schema.setdefault(
            "components",
            {},
        )

        security_schemes = components.setdefault(
            "securitySchemes",
            {},
        )

        security_schemes.setdefault(
            "ReportAdminKey",
            {
                "type": "apiKey",
                "in": "header",
                "name": "X-Admin-Key",
                "description": (
                    "管理者 API 金鑰。"
                    "只可由授權管理者設定與使用。"
                ),
            },  
        )

        security_schemes["BearerAccessToken"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "Opaque access token",
            "description": (
                "所有一般 API 都需要此短效登入 Token。"
                "請在 Swagger UI 的 Authorize 輸入原始 token，"
                "不要自行加上 Bearer 前綴。"
            ),
        }

        for (
            method,
            path,
        ), metadata in API_OPERATIONS.items():
            operation = (
                schema.get("paths", {})
                .get(path, {})
                .get(method)
            )

            if operation is None:
                continue

            api_number = metadata["number"]

            operation["operationId"] = (
                "api_"
                + api_number.replace("-", "_")
            )

            operation["tags"] = [metadata["tag"]]

            operation["summary"] = (
                f"【{api_number}】"
                f"{metadata['title']}"
            )

            documented_inputs = list(
                metadata["inputs"]
            )

            if (method, path) not in PUBLIC_API_OPERATIONS:
                documented_inputs.insert(
                    0,
                    BEARER_TOKEN_INPUT,
                )

            operation["description"] = (
                "### 功能說明\n\n"
                + metadata["purpose"]
                + "\n\n"
                + build_input_table(
                    documented_inputs
                )
            )

            apply_parameter_metadata(
                operation,
                metadata["inputs"],
            )

            operation.setdefault("responses", {})

            operation["responses"].setdefault(
                "422",
                {
                    "description": "輸入參數格式錯誤。",
                },
            )

            if (method, path) in ADMIN_OPERATIONS:
                operation["security"] = [
                    {"ReportAdminKey": []}
                ]

                operation["responses"].setdefault(
                    "403",
                    {
                        "description": (
                            "X-Admin-Key 缺失或無效。"
                        ),
                    },
                )

        webhook_operation = (
            schema.get("paths", {})
            .get("/line/webhook", {})
            .get("post")
        )

        if webhook_operation is not None:
            webhook_operation["requestBody"] = {
                "required": True,
                "description": (
                    "LINE Platform 自動傳送的 webhook payload。"
                    "不可在 Swagger UI 直接模擬正式事件。"
                ),
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "description": (
                                "LINE Messaging API webhook event payload。"
                            ),
                        },
                        "example": {
                            "destination": "Uxxxxxxxx",
                            "events": [],
                        },
                    }
                },
            }
        
        http_methods = {
            "get",
            "post",
            "put",
            "patch",
            "delete",
            "head",
            "options",
        }

        for path, path_item in schema["paths"].items():
            for method, operation in path_item.items():
                if method not in http_methods:
                    continue

                operation_key = (method, path)

                if operation_key in PUBLIC_API_OPERATIONS:
                    operation.pop("security", None)
                    continue

                if operation_key in ADMIN_OPERATIONS:
                    operation["security"] = [
                        {
                            "BearerAccessToken": [],
                            "ReportAdminKey": [],
                        }
                    ]
                    continue

                operation["security"] = [
                    {
                        "BearerAccessToken": [],
                    }
                ]
                
        app.openapi_schema = schema

        return app.openapi_schema

    app.openapi = custom_openapi


def swagger_ui_html(app: FastAPI) -> HTMLResponse:
    response = get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} · API Portal",
        swagger_ui_parameters=SWAGGER_UI_PARAMETERS,
    )

    html = response.body.decode("utf-8")

    banner = """
<div class="portal-banner">
    <h1>Silent Disaster Zone API Portal</h1>
    <p>
        每支 API 皆以編號、輸入位置、必填性、預設值與範例說明。
        系統結果僅供人工確認與決策輔助，不是官方災害命令。
    </p>
</div>
"""

    html = html.replace(
        "</head>",
        PORTAL_CSS + "\n</head>",
    )

    html = html.replace(
        '<div id="swagger-ui">',
        banner + '\n<div id="swagger-ui">',
    )

    return HTMLResponse(html)


def redoc_html(app: FastAPI) -> HTMLResponse:
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} · Reference",
        with_google_fonts=False,
    )