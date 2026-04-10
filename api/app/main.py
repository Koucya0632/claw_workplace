from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.repositories.database import ensure_database_ready
from app.routers import (
    documents,
    health,
    knowledge,
    openclaw_agents,
    openclaw_daily_news,
    openclaw_development,
    openclaw_system_inspection,
    openclaw_agent_tools,
    openclaw_config,
    openclaw_workflow_config,
    openclaw_devices,
    openclaw_hooks,
    openclaw_instances,
    openclaw_logs,
    openclaw_operations,
    reports,
    search,
    sources,
    tasks,
    workflows,
)
from app.services.openclaw_cron_service import OpenClawCronBridgeService


def create_app() -> FastAPI:
    # 建立 FastAPI app 的同時初始化資料庫 schema，確保 API 一啟動就可用。
    ensure_database_ready()

    app = FastAPI(title="OpenClaw Smart Office API", version="0.1.0")

    # 開發期先允許所有來源，方便 Next.js 本地呼叫；正式環境再收斂。
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 將各功能 router 掛到統一的 /api/v1 前綴下。
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(sources.router, prefix="/api/v1")
    app.include_router(knowledge.router, prefix="/api/v1")
    app.include_router(search.router, prefix="/api/v1")
    app.include_router(documents.router, prefix="/api/v1")
    app.include_router(tasks.router, prefix="/api/v1")
    app.include_router(reports.router, prefix="/api/v1")
    app.include_router(openclaw_instances.router, prefix="/api/v1")
    app.include_router(openclaw_agents.router, prefix="/api/v1")
    app.include_router(openclaw_agent_tools.router, prefix="/api/v1")
    app.include_router(openclaw_devices.router, prefix="/api/v1")
    app.include_router(openclaw_config.router, prefix="/api/v1")
    app.include_router(openclaw_workflow_config.router, prefix="/api/v1")
    app.include_router(openclaw_daily_news.router, prefix="/api/v1")
    app.include_router(openclaw_development.router, prefix="/api/v1")
    app.include_router(openclaw_system_inspection.router, prefix="/api/v1")
    app.include_router(openclaw_logs.router, prefix="/api/v1")
    app.include_router(openclaw_hooks.router, prefix="/api/v1")
    app.include_router(openclaw_operations.router, prefix="/api/v1")
    app.include_router(workflows.router, prefix="/api/v1")

    cron_bridge = OpenClawCronBridgeService()
    app.state.openclaw_cron_bridge = cron_bridge

    @app.on_event("startup")
    def start_openclaw_cron_bridge() -> None:
        cron_bridge.start()

    @app.on_event("shutdown")
    def stop_openclaw_cron_bridge() -> None:
        cron_bridge.stop()

    return app


app = create_app()
