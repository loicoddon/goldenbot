from fastapi import APIRouter

from app.services.engine_runner import engine_runner

router = APIRouter()


@router.get("/status")
async def status():
    return engine_runner.status()


@router.post("/start")
async def start():
    await engine_runner.start()
    return {"ok": True, "status": engine_runner.status()}


@router.post("/stop")
async def stop():
    await engine_runner.stop()
    return {"ok": True, "status": engine_runner.status()}


@router.post("/restart")
async def restart():
    await engine_runner.restart()
    return {"ok": True, "status": engine_runner.status()}
