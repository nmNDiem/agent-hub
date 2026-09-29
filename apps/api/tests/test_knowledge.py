import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Protocol, cast
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from agent_hub_api.core.config import Settings
from agent_hub_api.identity.security import CSRF_COOKIE
from agent_hub_api.knowledge.models import IngestionJob, MediaAsset
from agent_hub_api.main import create_app
from agent_hub_api.models import Base
from agent_hub_api.workspaces.models import WorkspaceMember

PASSWORD = "secure-password-123"
ORIGIN = "http://127.0.0.1:3000"


class FakeKnowledgeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def upload_file(self, *, object_key: str, source: Path, content_type: str) -> None:
        self.objects[object_key] = source.read_bytes()

    async def download_file(
        self, *, object_key: str, destination: Path, max_bytes: int
    ) -> None:
        content = self.objects[object_key]
        if len(content) > max_bytes:
            raise RuntimeError("test object too large")
        destination.write_bytes(content)

    async def delete(self, *, object_key: str) -> None:
        self.objects.pop(object_key, None)


class AppFactory(Protocol):
    def __call__(
        self,
    ) -> tuple[
        FastAPI,
        async_sessionmaker[AsyncSession],
        FakeKnowledgeStorage,
    ]: ...


@pytest.fixture
def app_factory(tmp_path: Path) -> Iterator[AppFactory]:
    resources: list[AsyncEngine] = []

    def build() -> tuple[
        FastAPI,
        async_sessionmaker[AsyncSession],
        FakeKnowledgeStorage,
    ]:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'knowledge.db'}")

        async def prepare() -> None:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)

        asyncio.run(prepare())
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        storage = FakeKnowledgeStorage()
        app = create_app(
            settings=Settings(
                app_env="test",
                jwt_signing_key="test-signing-key-with-at-least-32-bytes",
            ),
            session_factory=session_factory,
            knowledge_storage=storage,
        )
        resources.append(engine)
        return app, session_factory, storage

    yield build

    async def dispose() -> None:
        for engine in resources:
            await engine.dispose()

    asyncio.run(dispose())


def csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get(CSRF_COOKIE)
    assert token is not None
    return {"x-csrf-token": token, "origin": ORIGIN}


def register_and_create_workspace(
    client: TestClient, email: str, slug: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    registration = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD},
        headers={"origin": ORIGIN},
    )
    assert registration.status_code == 201, registration.text
    workspace = client.post(
        "/api/v1/workspaces",
        json={"slug": slug, "display_name": slug},
        headers=csrf_headers(client),
    )
    assert workspace.status_code == 201, workspace.text
    return cast(dict[str, Any], registration.json()), cast(dict[str, Any], workspace.json())


def test_knowledge_api_is_idempotent_and_tenant_scoped(app_factory: AppFactory) -> None:
    app, session_factory, storage = app_factory()
    with TestClient(app) as owner_a, TestClient(app) as owner_b:
        user_a, workspace_a = register_and_create_workspace(
            owner_a, "knowledge-a@example.com", "knowledge-a"
        )
        user_b, workspace_b = register_and_create_workspace(
            owner_b, "knowledge-b@example.com", "knowledge-b"
        )
        created_base = owner_a.post(
            f"/api/v1/workspaces/{workspace_a['id']}/knowledge-bases",
            json={"name": "Shop information", "kind": "shop"},
            headers=csrf_headers(owner_a),
        )
        assert created_base.status_code == 201, created_base.text
        knowledge_base = created_base.json()

        manual_url = (
            f"/api/v1/workspaces/{workspace_a['id']}/knowledge-bases/"
            f"{knowledge_base['id']}/documents/text"
        )
        manual_headers = {**csrf_headers(owner_a), "Idempotency-Key": "manual-profile-1"}
        manual = owner_a.post(
            manual_url,
            json={
                "title": "About the shop",
                "kind": "profile",
                "content": "We sell verified catalog products.",
            },
            headers=manual_headers,
        )
        assert manual.status_code == 201, manual.text
        assert manual.json()["ingestion_job"]["status"] == "awaiting_profile"
        repeated = owner_a.post(
            manual_url,
            json={
                "title": "About the shop",
                "kind": "profile",
                "content": "We sell verified catalog products.",
            },
            headers=manual_headers,
        )
        assert repeated.status_code == 201
        assert repeated.json()["id"] == manual.json()["id"]
        conflict = owner_a.post(
            manual_url,
            json={"title": "Changed", "kind": "profile", "content": "Different"},
            headers=manual_headers,
        )
        assert conflict.status_code == 409

        upload = owner_a.post(
            f"/api/v1/workspaces/{workspace_a['id']}/knowledge-bases/"
            f"{knowledge_base['id']}/documents",
            data={"title": "Returns", "kind": "policy"},
            files={"file": ("returns.txt", b"Returns within seven days.", "text/plain")},
            headers={**csrf_headers(owner_a), "Idempotency-Key": "file-policy-1"},
        )
        assert upload.status_code == 201, upload.text
        assert upload.json()["ingestion_job"]["status"] == "awaiting_profile"
        assert list(storage.objects.values()) == [b"Returns within seven days."]

        cross_workspace_base = owner_b.get(
            f"/api/v1/workspaces/{workspace_a['id']}/knowledge-bases"
        )
        assert cross_workspace_base.status_code == 404
        cross_workspace_job = owner_b.get(
            f"/api/v1/workspaces/{workspace_a['id']}/ingestion-jobs/"
            f"{manual.json()['ingestion_job']['id']}"
        )
        assert cross_workspace_job.status_code == 404

        agent = owner_a.post(
            f"/api/v1/workspaces/{workspace_a['id']}/agents",
            json={"name": "Knowledge agent"},
            headers=csrf_headers(owner_a),
        ).json()
        foreign_base = owner_b.post(
            f"/api/v1/workspaces/{workspace_b['id']}/knowledge-bases",
            json={"name": "Foreign", "kind": "general"},
            headers=csrf_headers(owner_b),
        ).json()
        forged_link = owner_a.put(
            f"/api/v1/workspaces/{workspace_a['id']}/agents/{agent['public_id']}"
            "/knowledge-bases",
            json={"knowledge_base_ids": [foreign_base["id"]]},
            headers=csrf_headers(owner_a),
        )
        assert forged_link.status_code == 404

        async def add_member() -> None:
            async with session_factory() as session, session.begin():
                session.add(
                    WorkspaceMember(
                        workspace_id=UUID(workspace_a["id"]),
                        user_id=UUID(user_b["user"]["id"]),
                        role="member",
                    )
                )

        asyncio.run(add_member())
        assert (
            owner_b.get(f"/api/v1/workspaces/{workspace_a['id']}/knowledge-bases").status_code
            == 200
        )
        forbidden_write = owner_b.post(
            f"/api/v1/workspaces/{workspace_a['id']}/knowledge-bases",
            json={"name": "Forbidden", "kind": "general"},
            headers=csrf_headers(owner_b),
        )
        assert forbidden_write.status_code == 403

        deleted = owner_a.delete(
            f"/api/v1/workspaces/{workspace_a['id']}/knowledge-bases/"
            f"{knowledge_base['id']}/documents/{upload.json()['id']}",
            headers=csrf_headers(owner_a),
        )
        assert deleted.status_code == 204

        async def verify_cleanup_state() -> None:
            async with session_factory() as session:
                asset = await session.scalar(
                    select(MediaAsset).where(MediaAsset.workspace_id == UUID(workspace_a["id"]))
                )
                job = await session.scalar(
                    select(IngestionJob).where(
                        IngestionJob.id == upload.json()["ingestion_job"]["id"]
                    )
                )
                assert asset is not None and asset.status == "delete_pending"
                assert job is not None and job.status == "cancelled"

        asyncio.run(verify_cleanup_state())


def test_knowledge_upload_rejects_invalid_signature_and_size(app_factory: AppFactory) -> None:
    app, _, storage = app_factory()
    with TestClient(app) as client:
        _, workspace = register_and_create_workspace(
            client, "knowledge-files@example.com", "knowledge-files"
        )
        knowledge_base = client.post(
            f"/api/v1/workspaces/{workspace['id']}/knowledge-bases",
            json={"name": "Documents", "kind": "general"},
            headers=csrf_headers(client),
        ).json()
        url = (
            f"/api/v1/workspaces/{workspace['id']}/knowledge-bases/"
            f"{knowledge_base['id']}/documents"
        )
        invalid = client.post(
            url,
            data={"title": "Fake PDF", "kind": "document"},
            files={"file": ("fake.pdf", b"not a pdf", "application/pdf")},
            headers={**csrf_headers(client), "Idempotency-Key": "fake-pdf"},
        )
        assert invalid.status_code == 415
        assert storage.objects == {}
