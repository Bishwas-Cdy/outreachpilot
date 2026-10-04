from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api import get_app_settings
from app.config import Settings
from app.database import Base, get_db
from app.main import app


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="sqlite://",
        llm_api_key=None,
        delivery_mode="mock",
        webhook_auto_process=False,
    )


@pytest_asyncio.fixture
async def client(tmp_path: Path, settings: Settings) -> AsyncGenerator[AsyncClient, None]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    testing_session = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)
    Base.metadata.create_all(bind=engine)

    async def override_db() -> AsyncGenerator[Session, None]:
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db

    async def override_settings() -> Settings:
        return settings

    app.dependency_overrides[get_app_settings] = override_settings
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def contact_payload() -> dict[str, str]:
    return {
        "first_name": "Sarah",
        "last_name": "Kim",
        "email": "sarah@example.com",
        "role": "VP of Sales",
        "company_name": "Acme Health",
        "company_website": "https://93.184.216.34",
    }
