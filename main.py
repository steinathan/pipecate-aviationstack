import os
from typing import Any

import aiohttp
from fastapi.responses import RedirectResponse
from fastapi import HTTPException, Request, FastAPI

from loguru import logger
from pipecat.transports.services.helpers.daily_rest import (
    DailyRESTHelper,
    DailyRoomParams,
)
from fastapi.middleware.cors import CORSMiddleware


from agent_bot import run_in_background

app = FastAPI()


app.add_middleware(
    CORSMiddleware,  # type:ignore
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


daily_rest_helpers = DailyRESTHelper(
    daily_api_key=os.getenv(
        "DAILY_API_KEY",
        "",
    ),
    daily_api_url=os.getenv("DAILY_API_URL", "https://api.daily.co/v1"),
    aiohttp_session=aiohttp.ClientSession(),
)


async def maybe_room_and_token() -> tuple[str, str]:
    if os.getenv("DAILY_SAMPLE_ROOM_URL", None):
        room = await daily_rest_helpers.get_room_from_url(
            os.getenv("DAILY_SAMPLE_ROOM_URL", "")
        )
    else:
        logger.warning("No DAILY_SAMPLE_ROOM_URL specified. Creating room...")
        room = await daily_rest_helpers.create_room(DailyRoomParams())

    if not room.url:
        raise HTTPException(status_code=500, detail="Failed to create room")

    token = await daily_rest_helpers.get_token(room.url)
    if not token:
        raise HTTPException(
            status_code=500, detail=f"Failed to get token for room: {room.url}"
        )

    return room.url, token


@app.get("/call")
async def create_room(request: Request):
    room_url, token = await maybe_room_and_token()
    logger.debug(f"Room URL: {room_url}")
    return RedirectResponse(room_url)


@app.post("/call/connect")
async def rtvi_connect(
    request: Request,
) -> dict[Any, Any]:
    room_url, token = await maybe_room_and_token()
    logger.debug(f"Room URL: {room_url}")

    try:
        await run_in_background(room_url, token)
    except Exception as e:
        logger.error(f"Failed to start subprocess: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start subprocess: {e}")

    return {"room_url": room_url, "token": token}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, port=1337, reload=True)
