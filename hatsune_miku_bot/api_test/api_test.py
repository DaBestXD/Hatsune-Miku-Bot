from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from hatsune_miku_bot.api_test.api_helpers import  all_uptime_windows, get_status, last_n_events

app = FastAPI()
router = APIRouter()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://YOUR_GITHUB_USERNAME.github.io",
        "https://YOUR_GITHUB_USERNAME.github.io/YOUR_REPO_NAME",
    ],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)
@router.get("/status")
async def status() -> dict:
    return {**await get_status(), **await all_uptime_windows(), **await last_n_events(5)}

app.include_router(router)
