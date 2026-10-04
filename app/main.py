import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import router
from app.config import get_settings
from app.database import Base, engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="OutreachPilot",
    version="0.1.0",
    description=(
        "Evidence-grounded B2B account research and outreach drafting with mandatory "
        "human approval."
    ),
    lifespan=lifespan,
)
app.include_router(router)
