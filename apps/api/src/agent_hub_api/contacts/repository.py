from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import Select, and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.contacts.models import Contact, ContactIdentity, ContactTagLink
from agent_hub_api.conversations.models import ConversationTag
from agent_hub_api.identity.models import User
from agent_hub_api.workspaces.models import WorkspaceMember

ContactRow = tuple[Contact, str | None]


class ContactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _rows() -> Select[tuple[Contact, str | None]]:
        statement = (
            select(Contact, User.normalized_email)
            .outerjoin(
                WorkspaceMember,
                (WorkspaceMember.workspace_id == Contact.workspace_id)
                & (WorkspaceMember.id == Contact.assigned_member_id),
            )
            .outerjoin(User, User.id == WorkspaceMember.user_id)
        )
        return cast(Select[tuple[Contact, str | None]], statement)

    async def list_rows(
        self,
        workspace_id: UUID,
        *,
        member: WorkspaceMember,
        limit: int,
        cursor_at: datetime | None,
        cursor_public_id: UUID | None,
        query: str | None,
        assigned_member_id: int | None,
        tag_id: int | None,
    ) -> list[ContactRow]:
        statement = self._rows().where(
            Contact.workspace_id == workspace_id,
            Contact.lifecycle_state == "active",
        )
        if member.role == "member":
            statement = statement.where(
                or_(
                    Contact.assigned_member_id.is_(None),
                    Contact.assigned_member_id == member.id,
                )
            )
        if assigned_member_id is not None:
            statement = statement.where(Contact.assigned_member_id == assigned_member_id)
        if query:
            pattern = f"%{query.casefold()}%"
            identity_match = exists(
                select(ContactIdentity.id).where(
                    ContactIdentity.workspace_id == workspace_id,
                    ContactIdentity.contact_id == Contact.id,
                    ContactIdentity.identity_type.in_(["email", "phone"]),
                    func.lower(ContactIdentity.normalized_value).like(pattern),
                )
            )
            statement = statement.where(
                or_(func.lower(Contact.display_name).like(pattern), identity_match)
            )
        if tag_id is not None:
            statement = statement.join(
                ContactTagLink,
                (ContactTagLink.workspace_id == Contact.workspace_id)
                & (ContactTagLink.contact_id == Contact.id),
            ).where(ContactTagLink.tag_id == tag_id)
        if cursor_at is not None and cursor_public_id is not None:
            statement = statement.where(
                or_(
                    Contact.updated_at < cursor_at,
                    and_(
                        Contact.updated_at == cursor_at,
                        Contact.public_id < cursor_public_id,
                    ),
                )
            )
        result = await self.session.execute(
            statement.order_by(Contact.updated_at.desc(), Contact.public_id.desc()).limit(limit)
        )
        return [row._tuple() for row in result.all()]

    async def row(
        self, workspace_id: UUID, public_id: UUID, *, for_update: bool = False
    ) -> ContactRow | None:
        statement = self._rows().where(
            Contact.workspace_id == workspace_id,
            Contact.public_id == public_id,
            Contact.lifecycle_state != "expired",
        )
        if for_update:
            statement = statement.with_for_update(of=Contact)
        result = await self.session.execute(statement)
        row = result.one_or_none()
        return row._tuple() if row is not None else None

    async def by_id(self, workspace_id: UUID, contact_id: int) -> Contact | None:
        return (
            await self.session.scalars(
                select(Contact).where(
                    Contact.workspace_id == workspace_id, Contact.id == contact_id
                )
            )
        ).one_or_none()

    async def metadata(
        self, workspace_id: UUID, contact_ids: list[int]
    ) -> tuple[dict[int, list[ContactIdentity]], dict[int, list[ConversationTag]]]:
        identities: dict[int, list[ContactIdentity]] = {item_id: [] for item_id in contact_ids}
        tags: dict[int, list[ConversationTag]] = {item_id: [] for item_id in contact_ids}
        if not contact_ids:
            return identities, tags
        identity_rows = await self.session.scalars(
            select(ContactIdentity).where(
                ContactIdentity.workspace_id == workspace_id,
                ContactIdentity.contact_id.in_(contact_ids),
            )
        )
        for identity in identity_rows:
            identities[identity.contact_id].append(identity)
        tag_rows = await self.session.execute(
            select(ContactTagLink.contact_id, ConversationTag)
            .join(
                ConversationTag,
                (ConversationTag.workspace_id == ContactTagLink.workspace_id)
                & (ConversationTag.id == ContactTagLink.tag_id),
            )
            .where(
                ContactTagLink.workspace_id == workspace_id,
                ContactTagLink.contact_id.in_(contact_ids),
            )
            .order_by(ConversationTag.name)
        )
        for contact_id, tag in tag_rows.all():
            tags[contact_id].append(tag)
        return identities, tags
