"""Seed a realistic local-only demo workspace.

Revision ID: 20261019_0022
Revises: 20261016_0021
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import NamedTuple, cast
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

revision: str = "20261019_0022"
down_revision: str | None = "20261016_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEMO_WORKSPACE_ID = UUID("70000000-0000-4000-8000-000000000001")
DEMO_WORKSPACE_SLUG = "moc-may-studio"


class VariantSeed(NamedTuple):
    sku: str
    name: str
    color: str | None
    size: str | None
    price_override: Decimal | None
    quantities: tuple[int, int, int]


class ProductSeed(NamedTuple):
    sku: str
    name: str
    slug: str
    category: str
    description: str
    price: Decimal
    compare_at_price: Decimal | None
    attributes: Mapping[str, object]
    variants: tuple[VariantSeed, ...]
    collection_indexes: tuple[int, ...]
    has_size_guide: bool = False


def _variant_option_value(variant: VariantSeed, attribute_name: str) -> str | None:
    if attribute_name == "color":
        return variant.color
    if attribute_name == "size":
        return variant.size
    raise ValueError(f"Unsupported variant option attribute: {attribute_name}")


PRODUCTS = (
    ProductSeed(
        sku="MM-LINEN-001",
        name="Áo sơ mi linen An Nhiên",
        slug="ao-so-mi-linen-an-nhien",
        category="Áo nữ",
        description="Sơ mi linen pha mềm, phom suông nhẹ, phù hợp đi làm và cuối tuần.",
        price=Decimal("689000"),
        compare_at_price=Decimal("790000"),
        attributes={"material": "linen pha", "fit": "regular", "season": "xuân hè"},
        variants=(
            VariantSeed("MM-LINEN-001-TR-S", "Trắng / S", "Trắng", "S", None, (12, 20, 8)),
            VariantSeed("MM-LINEN-001-TR-M", "Trắng / M", "Trắng", "M", None, (18, 24, 10)),
            VariantSeed("MM-LINEN-001-NA-S", "Nâu / S", "Nâu", "S", None, (9, 16, 6)),
            VariantSeed("MM-LINEN-001-NA-M", "Nâu / M", "Nâu", "M", None, (14, 18, 7)),
        ),
        collection_indexes=(0, 1),
        has_size_guide=True,
    ),
    ProductSeed(
        sku="MM-PANTS-002",
        name="Quần suông cạp cao Hạ",
        slug="quan-suong-cap-cao-ha",
        category="Quần nữ",
        description="Quần suông cạp cao, đường ly trước giúp dáng gọn và dễ phối đồ công sở.",
        price=Decimal("749000"),
        compare_at_price=None,
        attributes={"material": "twill", "fit": "wide-leg", "care": "giặt nhẹ"},
        variants=(
            VariantSeed("MM-PANTS-002-D-S", "Đen / S", "Đen", "S", None, (8, 15, 5)),
            VariantSeed("MM-PANTS-002-D-M", "Đen / M", "Đen", "M", None, (11, 19, 7)),
            VariantSeed("MM-PANTS-002-D-L", "Đen / L", "Đen", "L", None, (6, 10, 4)),
        ),
        collection_indexes=(0, 2),
        has_size_guide=True,
    ),
    ProductSeed(
        sku="MM-DRESS-003",
        name="Đầm midi Lam",
        slug="dam-midi-lam",
        category="Đầm",
        description="Đầm midi cổ vuông, eo chiết vừa phải và lớp lót thoáng nhẹ.",
        price=Decimal("1190000"),
        compare_at_price=Decimal("1390000"),
        attributes={"material": "cotton tencel", "length": "midi", "lining": True},
        variants=(
            VariantSeed("MM-DRESS-003-X-S", "Xanh lam / S", "Xanh lam", "S", None, (5, 8, 3)),
            VariantSeed("MM-DRESS-003-X-M", "Xanh lam / M", "Xanh lam", "M", None, (7, 11, 4)),
            VariantSeed("MM-DRESS-003-X-L", "Xanh lam / L", "Xanh lam", "L", None, (4, 6, 2)),
        ),
        collection_indexes=(0, 1),
        has_size_guide=True,
    ),
    ProductSeed(
        sku="MM-BLAZER-004",
        name="Blazer nhẹ ban mai",
        slug="blazer-nhe-ban-mai",
        category="Áo khoác",
        description="Blazer một lớp, vai mềm, thiết kế tối giản cho thời tiết chuyển mùa.",
        price=Decimal("1490000"),
        compare_at_price=None,
        attributes={"material": "viscose pha", "lining": False, "fit": "relaxed"},
        variants=(
            VariantSeed("MM-BLAZER-004-B-S", "Be / S", "Be", "S", None, (4, 7, 2)),
            VariantSeed("MM-BLAZER-004-B-M", "Be / M", "Be", "M", None, (6, 9, 3)),
            VariantSeed("MM-BLAZER-004-B-L", "Be / L", "Be", "L", None, (3, 5, 1)),
        ),
        collection_indexes=(2,),
        has_size_guide=True,
    ),
    ProductSeed(
        sku="MM-SCARF-005",
        name="Khăn lụa Vườn Sớm",
        slug="khan-lua-vuon-som",
        category="Phụ kiện",
        description="Khăn vuông họa tiết thực vật, hoàn thiện viền cuốn thủ công.",
        price=Decimal("459000"),
        compare_at_price=None,
        attributes={"material": "lụa", "dimensions_cm": "65x65"},
        variants=(
            VariantSeed("MM-SCARF-005-X", "Xanh rêu", "Xanh rêu", None, None, (15, 26, 9)),
            VariantSeed("MM-SCARF-005-C", "Cam đất", "Cam đất", None, None, (10, 21, 7)),
        ),
        collection_indexes=(0, 1),
    ),
    ProductSeed(
        sku="MM-BAG-006",
        name="Túi da mini Mây",
        slug="tui-da-mini-may",
        category="Túi xách",
        description="Túi đeo chéo nhỏ gọn, ngăn chính có khóa và dây đeo điều chỉnh.",
        price=Decimal("1290000"),
        compare_at_price=Decimal("1450000"),
        attributes={"material": "da thuộc thực vật", "strap": "adjustable"},
        variants=(
            VariantSeed("MM-BAG-006-N", "Nâu hạt dẻ", "Nâu hạt dẻ", None, None, (7, 12, 4)),
            VariantSeed("MM-BAG-006-D", "Đen", "Đen", None, None, (5, 10, 3)),
        ),
        collection_indexes=(0,),
    ),
    ProductSeed(
        sku="MM-SHOES-007",
        name="Giày loafer Tĩnh",
        slug="giay-loafer-tinh",
        category="Giày",
        description="Loafer mũi vuông, đế thấp và lót êm cho ngày dài di chuyển.",
        price=Decimal("1390000"),
        compare_at_price=None,
        attributes={"material": "da", "heel_cm": 2},
        variants=(
            VariantSeed("MM-SHOES-007-36", "Đen / 36", "Đen", "36", None, (3, 5, 2)),
            VariantSeed("MM-SHOES-007-37", "Đen / 37", "Đen", "37", None, (5, 8, 3)),
            VariantSeed("MM-SHOES-007-38", "Đen / 38", "Đen", "38", None, (4, 7, 2)),
            VariantSeed("MM-SHOES-007-39", "Đen / 39", "Đen", "39", None, (2, 4, 1)),
        ),
        collection_indexes=(2,),
    ),
    ProductSeed(
        sku="MM-TEE-008",
        name="Áo thun cotton Mộc",
        slug="ao-thun-cotton-moc",
        category="Áo nữ",
        description="Áo thun cotton dày vừa, bề mặt mịn và phom thoải mái.",
        price=Decimal("399000"),
        compare_at_price=None,
        attributes={"material": "cotton", "fit": "relaxed", "gsm": 220},
        variants=(
            VariantSeed("MM-TEE-008-TR-M", "Trắng / M", "Trắng", "M", None, (20, 35, 12)),
            VariantSeed("MM-TEE-008-TR-L", "Trắng / L", "Trắng", "L", None, (14, 28, 9)),
            VariantSeed("MM-TEE-008-D-M", "Đen / M", "Đen", "M", None, (18, 30, 10)),
            VariantSeed("MM-TEE-008-D-L", "Đen / L", "Đen", "L", None, (12, 22, 8)),
        ),
        collection_indexes=(0, 1),
        has_size_guide=True,
    ),
)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json_parameters(
    values: Mapping[str, object], json_columns: frozenset[str]
) -> dict[str, object]:
    return {
        key: json.dumps(value, ensure_ascii=False) if key in json_columns else value
        for key, value in values.items()
    }


def _insert(
    bind: Connection,
    table: str,
    values: Mapping[str, object],
    *,
    jsonb_columns: frozenset[str] = frozenset(),
    json_columns: frozenset[str] = frozenset(),
) -> None:
    columns = ", ".join(values)
    expressions = ", ".join(
        f"CAST(:{column} AS jsonb)"
        if column in jsonb_columns
        else f"CAST(:{column} AS json)"
        if column in json_columns
        else f":{column}"
        for column in values
    )
    bind.execute(
        sa.text(f"INSERT INTO {table} ({columns}) VALUES ({expressions})"),
        _json_parameters(values, jsonb_columns | json_columns),
    )


def _insert_id(
    bind: Connection,
    table: str,
    values: Mapping[str, object],
    *,
    jsonb_columns: frozenset[str] = frozenset(),
    json_columns: frozenset[str] = frozenset(),
) -> int:
    columns = ", ".join(values)
    expressions = ", ".join(
        f"CAST(:{column} AS jsonb)"
        if column in jsonb_columns
        else f"CAST(:{column} AS json)"
        if column in json_columns
        else f":{column}"
        for column in values
    )
    result = bind.execute(
        sa.text(f"INSERT INTO {table} ({columns}) VALUES ({expressions}) RETURNING id"),
        _json_parameters(values, jsonb_columns | json_columns),
    )
    return cast(int, result.scalar_one())


def _seed_catalog(bind: Connection, now: datetime) -> tuple[list[int], list[int], list[int]]:
    workspace_id = DEMO_WORKSPACE_ID
    location_ids = [
        _insert_id(
            bind,
            "locations",
            {
                "workspace_id": workspace_id,
                "name": name,
                "code": code,
                "type": location_type,
                "address_json": address,
                "metadata_json": {"demo": True},
                "is_active": True,
                "created_at": now - timedelta(days=210 - index * 10),
                "updated_at": now - timedelta(days=index),
            },
            jsonb_columns=frozenset({"address_json", "metadata_json"}),
        )
        for index, (name, code, location_type, address) in enumerate(
            (
                (
                    "Cửa hàng Nguyễn Trãi",
                    "HCM-Q1",
                    "store",
                    {"line1": "142 Nguyễn Trãi", "district": "Quận 1", "city": "TP.HCM"},
                ),
                (
                    "Kho vận Thủ Đức",
                    "HCM-TD",
                    "warehouse",
                    {"line1": "28 Đường số 6", "district": "Thủ Đức", "city": "TP.HCM"},
                ),
                (
                    "Cửa hàng trực tuyến",
                    "ONLINE",
                    "online",
                    {"channel": "website", "service_area": "Toàn quốc"},
                ),
            )
        )
    ]
    collection_ids = [
        _insert_id(
            bind,
            "catalog_collections",
            {
                "workspace_id": workspace_id,
                "name": name,
                "description": description,
                "is_active": True,
                "created_at": now - timedelta(days=150 - index * 7),
                "updated_at": now - timedelta(days=index + 1),
            },
        )
        for index, (name, description) in enumerate(
            (
                ("Bán chạy", "Những thiết kế được khách hàng lựa chọn nhiều trong 30 ngày gần đây."),
                ("Linen mùa hè", "Chất liệu nhẹ, thoáng và bảng màu trung tính."),
                ("Đi làm thanh lịch", "Các thiết kế dễ phối cho tủ đồ công sở hiện đại."),
            )
        )
    ]

    product_ids: list[int] = []
    for product_index, product in enumerate(PRODUCTS):
        product_id = _insert_id(
            bind,
            "products",
            {
                "workspace_id": workspace_id,
                "product_sku": product.sku,
                "name": product.name,
                "slug": product.slug,
                "brand": "Mộc & Mây",
                "description": product.description,
                "description_text": product.description,
                "category": product.category,
                "currency": "VND",
                "price": product.price,
                "compare_at_price": product.compare_at_price,
                "inventory_policy": "tracked",
                "attributes_json": product.attributes,
                "status": "active",
                "created_at": now - timedelta(days=120 - product_index * 5),
                "updated_at": now - timedelta(hours=product_index * 9 + 2),
            },
            jsonb_columns=frozenset({"attributes_json"}),
        )
        product_ids.append(product_id)
        for collection_index in product.collection_indexes:
            _insert(
                bind,
                "catalog_collection_products",
                {
                    "workspace_id": workspace_id,
                    "collection_id": collection_ids[collection_index],
                    "product_id": product_id,
                },
            )

        variant_records: list[tuple[int, VariantSeed]] = []
        for variant_index, variant in enumerate(product.variants):
            variant_id = _insert_id(
                bind,
                "product_variants",
                {
                    "workspace_id": workspace_id,
                    "product_id": product_id,
                    "variant_sku": variant.sku,
                    "name": variant.name,
                    "color": variant.color,
                    "size": variant.size,
                    "price_override": variant.price_override,
                    "inventory_policy": "tracked",
                    "option_signature": f"color={variant.color or ''}|size={variant.size or ''}",
                    "attributes_json": {"demo": True},
                    "status": "active",
                    "created_at": now - timedelta(days=100 - product_index * 3),
                    "updated_at": now - timedelta(hours=variant_index + product_index),
                },
                jsonb_columns=frozenset({"attributes_json"}),
            )
            variant_records.append((variant_id, variant))
            for location_index, location_id in enumerate(location_ids):
                _insert(
                    bind,
                    "location_variants",
                    {
                        "workspace_id": workspace_id,
                        "location_id": location_id,
                        "variant_id": variant_id,
                        "is_active": True,
                        "metadata_json": {"replenishment": "weekly"},
                        "created_at": now - timedelta(days=90),
                        "updated_at": now - timedelta(hours=location_index + 1),
                    },
                    jsonb_columns=frozenset({"metadata_json"}),
                )
                _insert(
                    bind,
                    "inventory_levels",
                    {
                        "workspace_id": workspace_id,
                        "location_id": location_id,
                        "variant_id": variant_id,
                        "quantity": variant.quantities[location_index],
                        "updated_at": now - timedelta(hours=location_index + variant_index),
                    },
                )

        for option_position, (option_name, attribute_name) in enumerate(
            (("Màu sắc", "color"), ("Kích thước", "size"))
        ):
            option_values = tuple(
                dict.fromkeys(
                    value
                    for _, variant in variant_records
                    if (value := _variant_option_value(variant, attribute_name)) is not None
                )
            )
            if not option_values:
                continue
            definition_id = _insert_id(
                bind,
                "product_option_definitions",
                {
                    "workspace_id": workspace_id,
                    "product_id": product_id,
                    "name": option_name,
                    "normalized_name": attribute_name,
                    "position": option_position,
                },
            )
            option_value_ids: dict[str, int] = {}
            for value_position, value in enumerate(option_values):
                option_value_ids[value] = _insert_id(
                    bind,
                    "product_option_values",
                    {
                        "workspace_id": workspace_id,
                        "option_definition_id": definition_id,
                        "value": value,
                        "normalized_value": value.casefold(),
                        "position": value_position,
                    },
                )
            for variant_id, variant in variant_records:
                value = _variant_option_value(variant, attribute_name)
                if value is None:
                    continue
                _insert(
                    bind,
                    "variant_option_values",
                    {
                        "workspace_id": workspace_id,
                        "variant_id": variant_id,
                        "option_value_id": option_value_ids[value],
                        "option_definition_id": definition_id,
                    },
                )

        if product.has_size_guide:
            _insert(
                bind,
                "size_guides",
                {
                    "workspace_id": workspace_id,
                    "product_id": product_id,
                    "title": "Hướng dẫn chọn kích thước",
                    "content": {
                        "unit": "cm",
                        "columns": ["Size", "Ngực", "Eo", "Mông"],
                        "rows": [
                            ["S", "82-86", "64-68", "88-92"],
                            ["M", "87-91", "69-73", "93-97"],
                            ["L", "92-96", "74-78", "98-102"],
                        ],
                    },
                    "created_at": now - timedelta(days=80),
                    "updated_at": now - timedelta(days=5),
                },
                json_columns=frozenset({"content"}),
            )
    return location_ids, collection_ids, product_ids


def _seed_knowledge(
    bind: Connection, owner_user_id: UUID, now: datetime
) -> tuple[list[int], list[int]]:
    base_specs = (
        ("Sản phẩm & phối đồ", "shop"),
        ("Chính sách mua hàng", "policy"),
        ("Chăm sóc khách hàng", "faq"),
    )
    base_ids = [
        _insert_id(
            bind,
            "knowledge_bases",
            {
                "workspace_id": DEMO_WORKSPACE_ID,
                "name": name,
                "kind": kind,
                "status": "active",
                "created_at": now - timedelta(days=95 - index * 4),
                "updated_at": now - timedelta(days=index + 2),
            },
        )
        for index, (name, kind) in enumerate(base_specs)
    ]
    document_specs = (
        (
            0,
            "Gợi ý phối đồ theo hoàn cảnh",
            "profile",
            "Đi làm: phối blazer nhẹ với quần suông và áo thun trơn. Cuối tuần: sơ mi linen "
            "cùng quần sáng màu. Luôn ưu tiên nhu cầu, số đo và phong cách khách cung cấp.",
        ),
        (
            0,
            "Cách bảo quản chất liệu",
            "faq",
            "Linen và cotton nên giặt nhẹ bằng nước mát, tránh sấy nhiệt cao. Sản phẩm da cần "
            "được lau khô, bảo quản nơi thoáng và tránh tiếp xúc nước kéo dài.",
        ),
        (
            1,
            "Chính sách đổi hàng",
            "policy",
            "Đổi hàng trong 14 ngày kể từ ngày nhận. Sản phẩm phải còn tem, chưa qua sử dụng "
            "và có hóa đơn. Hàng giảm trên 30% không áp dụng đổi vì lý do chủ quan.",
        ),
        (
            1,
            "Giao hàng và kiểm tra đơn",
            "policy",
            "Đơn nội thành dự kiến 1-2 ngày làm việc; các tỉnh thành khác 3-5 ngày. Khách được "
            "kiểm tra đúng mẫu, màu và số lượng trước khi nhận nhưng không thử sản phẩm.",
        ),
        (
            2,
            "Câu hỏi thường gặp",
            "faq",
            "Giữ hàng tối đa 24 giờ sau khi xác nhận. Có thể điều chỉnh địa chỉ trước khi đơn "
            "bàn giao cho đơn vị vận chuyển. Hóa đơn điện tử được gửi qua email.",
        ),
        (
            2,
            "Quy trình hỗ trợ sau mua",
            "policy",
            "Ghi nhận mã đơn, vấn đề và phương án mong muốn. Trường hợp cần kiểm tra chất lượng "
            "được chuyển cho nhân viên và phản hồi trong một ngày làm việc.",
        ),
    )
    document_ids: list[int] = []
    for index, (base_index, title, kind, content) in enumerate(document_specs):
        document_id = _insert_id(
            bind,
            "knowledge_documents",
            {
                "workspace_id": DEMO_WORKSPACE_ID,
                "knowledge_base_id": base_ids[base_index],
                "title": title,
                "kind": kind,
                "status": "active",
                "created_at": now - timedelta(days=75 - index * 3),
                "updated_at": now - timedelta(days=index + 1),
            },
        )
        document_ids.append(document_id)
        _insert(
            bind,
            "knowledge_document_versions",
            {
                "workspace_id": DEMO_WORKSPACE_ID,
                "document_id": document_id,
                "version_no": 1,
                "source_kind": "manual",
                "source_text": content,
                "content_sha256": _sha256_text(content),
                "mime_type": "text/plain",
                "byte_size": len(content.encode("utf-8")),
                "created_by_user_id": owner_user_id,
                "reviewed_at": now - timedelta(days=12 - index),
                "review_due_at": now + timedelta(days=78 + index * 7),
                "reviewed_by_user_id": owner_user_id,
                "created_at": now - timedelta(days=70 - index * 3),
            },
        )
    return base_ids, document_ids


def _seed_agents(
    bind: Connection,
    owner_user_id: UUID,
    knowledge_base_ids: list[int],
    location_ids: list[int],
    collection_ids: list[int],
    now: datetime,
) -> tuple[list[int], list[int | None]]:
    agent_specs = (
        (
            UUID("71000000-0000-4000-8000-000000000001"),
            "Tư vấn bán hàng",
            "Xin chào! Mình có thể giúp bạn chọn sản phẩm, kích thước và kiểm tra tồn kho.",
            "Chỉ tư vấn từ dữ liệu được cấp. Không tự suy đoán tồn kho, giá hoặc chính sách.",
            "published",
            True,
            True,
            knowledge_base_ids,
        ),
        (
            UUID("71000000-0000-4000-8000-000000000002"),
            "Chăm sóc khách hàng",
            "Mình sẵn sàng hỗ trợ đổi hàng, giao nhận và các vấn đề sau mua.",
            "Ưu tiên giải thích chính sách rõ ràng và chuyển nhân viên khi cần xác minh đơn hàng.",
            "published",
            False,
            False,
            knowledge_base_ids[1:],
        ),
        (
            UUID("71000000-0000-4000-8000-000000000003"),
            "Stylist cá nhân",
            "Hãy chia sẻ dịp sử dụng và phong cách bạn thích để mình gợi ý.",
            "Không suy đoán số đo hoặc đặc điểm nhạy cảm của khách hàng.",
            "draft",
            False,
            False,
            knowledge_base_ids[:1],
        ),
    )
    agent_ids: list[int] = []
    revision_ids: list[int | None] = []
    for index, (
        public_id,
        name,
        greeting,
        instructions,
        status,
        all_locations,
        all_collections,
        assigned_knowledge_ids,
    ) in enumerate(agent_specs):
        agent_id = _insert_id(
            bind,
            "agents",
            {
                "public_id": public_id,
                "workspace_id": DEMO_WORKSPACE_ID,
                "name": name,
                "greeting": greeting,
                "safe_instructions": instructions,
                "default_locale": "vi",
                "status": status,
                "all_locations": all_locations,
                "all_collections": all_collections,
                "created_by_user_id": owner_user_id,
                "created_at": now - timedelta(days=60 - index * 8),
                "updated_at": now - timedelta(hours=index * 6 + 1),
            },
        )
        agent_ids.append(agent_id)
        for knowledge_base_id in assigned_knowledge_ids:
            _insert(
                bind,
                "agent_knowledge_bases",
                {
                    "workspace_id": DEMO_WORKSPACE_ID,
                    "agent_id": agent_id,
                    "knowledge_base_id": knowledge_base_id,
                },
            )
        if not all_locations:
            for location_id in location_ids[:2]:
                _insert(
                    bind,
                    "agent_locations",
                    {
                        "workspace_id": DEMO_WORKSPACE_ID,
                        "agent_id": agent_id,
                        "location_id": location_id,
                    },
                )
        if not all_collections:
            for collection_id in collection_ids[:2]:
                _insert(
                    bind,
                    "agent_catalog_collections",
                    {
                        "workspace_id": DEMO_WORKSPACE_ID,
                        "agent_id": agent_id,
                        "collection_id": collection_id,
                    },
                )
        if status != "published":
            revision_ids.append(None)
            continue
        catalog_scope: dict[str, object] = {
            "location_ids": None if all_locations else location_ids[:2],
            "collection_ids": None if all_collections else collection_ids[:2],
        }
        widget_config: dict[str, object] = {
            "brand_color": "#0F8F87" if index == 0 else "#315D8A",
            "launcher_position": "right",
            "handoff_url": "https://example.test/support",
            "handoff_label": "Gặp nhân viên",
        }
        snapshot = {
            "name": name,
            "greeting": greeting,
            "safe_instructions": instructions,
            "default_locale": "vi",
            "catalog_scope": catalog_scope,
            "knowledge_base_ids": assigned_knowledge_ids,
            "widget": widget_config,
        }
        revision_ids.append(
            _insert_id(
                bind,
                "agent_revisions",
                {
                    "workspace_id": DEMO_WORKSPACE_ID,
                    "agent_id": agent_id,
                    "revision_no": 1,
                    "name": name,
                    "greeting": greeting,
                    "safe_instructions": instructions,
                    "default_locale": "vi",
                    "catalog_scope_json": catalog_scope,
                    "knowledge_base_ids_json": assigned_knowledge_ids,
                    "widget_config_json": widget_config,
                    "config_hash": _sha256_text(
                        json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                    ),
                    "created_by_user_id": owner_user_id,
                    "published_at": now - timedelta(days=20 - index * 4),
                },
                jsonb_columns=frozenset(
                    {"catalog_scope_json", "knowledge_base_ids_json", "widget_config_json"}
                ),
            )
        )
    return agent_ids, revision_ids


def _seed_channels(
    bind: Connection,
    agent_ids: list[int],
    revision_ids: list[int | None],
    now: datetime,
) -> list[int]:
    channel_ids: list[int] = []
    for index, (name, color) in enumerate(
        (("Website Mộc & Mây", "#0F8F87"), ("Trung tâm hỗ trợ", "#315D8A"))
    ):
        revision_id = revision_ids[index]
        if revision_id is None:
            raise RuntimeError("Published demo agent is missing its revision")
        channel_id = _insert_id(
            bind,
            "channel_connections",
            {
                "workspace_id": DEMO_WORKSPACE_ID,
                "provider": "web",
                "display_name": name,
                "lifecycle_state": "active",
                "health_state": "unknown",
                "created_at": now - timedelta(days=18 - index * 3),
                "updated_at": now - timedelta(hours=index + 2),
            },
        )
        channel_ids.append(channel_id)
        _insert(
            bind,
            "website_channel_configs",
            {
                "connection_id": channel_id,
                "workspace_id": DEMO_WORKSPACE_ID,
                "brand_color": color,
                "launcher_position": "right",
                "handoff_url": "https://example.test/support",
                "handoff_label": "Gặp nhân viên",
                "created_at": now - timedelta(days=18 - index * 3),
                "updated_at": now - timedelta(hours=index + 2),
            },
        )
        _insert(
            bind,
            "widget_domains",
            {
                "workspace_id": DEMO_WORKSPACE_ID,
                "channel_id": channel_id,
                "normalized_origin": f"http://localhost:{3000 + index}",
                "created_at": now - timedelta(days=18 - index * 3),
            },
        )
        _insert(
            bind,
            "channel_agent_bindings",
            {
                "workspace_id": DEMO_WORKSPACE_ID,
                "connection_id": channel_id,
                "agent_id": agent_ids[index],
                "active_revision_id": revision_id,
                "enabled": True,
                "created_at": now - timedelta(days=18 - index * 3),
                "updated_at": now - timedelta(hours=index + 2),
            },
        )
    return channel_ids


def _seed_operations(
    bind: Connection,
    owner_member_id: int,
    agent_ids: list[int],
    revision_ids: list[int | None],
    channel_ids: list[int],
    product_ids: list[int],
    now: datetime,
) -> None:
    contact_specs = (
        (
            UUID("72000000-0000-4000-8000-000000000001"),
            "Mai Lan",
            "mai.lan@example.test",
            "+84901110001",
        ),
        (
            UUID("72000000-0000-4000-8000-000000000002"),
            "Thảo Vy",
            "thao.vy@example.test",
            "+84901110002",
        ),
        (
            UUID("72000000-0000-4000-8000-000000000003"),
            "Minh Anh",
            "minh.anh@example.test",
            "+84901110003",
        ),
    )
    contact_ids: list[int] = []
    for index, (public_id, name, email, phone) in enumerate(contact_specs):
        contact_id = _insert_id(
            bind,
            "contacts",
            {
                "public_id": public_id,
                "workspace_id": DEMO_WORKSPACE_ID,
                "display_name": name,
                "assigned_member_id": owner_member_id if index == 1 else None,
                "lifecycle_state": "active",
                "state_version": 1,
                "retention_until": now + timedelta(days=365),
                "created_at": now - timedelta(days=12 - index * 2),
                "updated_at": now - timedelta(hours=index * 8 + 1),
            },
        )
        contact_ids.append(contact_id)
        for identity_type, value in (("email", email), ("phone", phone)):
            _insert(
                bind,
                "contact_identities",
                {
                    "workspace_id": DEMO_WORKSPACE_ID,
                    "contact_id": contact_id,
                    "connection_id": None,
                    "provider": "website",
                    "identity_type": identity_type,
                    "normalized_value": value,
                    "verification_state": "consented",
                    "consent_at": now - timedelta(days=12 - index * 2),
                    "consent_text_version": "demo-contact-v1",
                    "retention_until": now + timedelta(days=365),
                    "created_at": now - timedelta(days=12 - index * 2),
                },
            )
        _insert(
            bind,
            "contact_notes",
            {
                "workspace_id": DEMO_WORKSPACE_ID,
                "contact_id": contact_id,
                "author_member_id": owner_member_id,
                "body": (
                    "Quan tâm chất liệu tự nhiên và ưu tiên giao hàng buổi tối."
                    if index == 0
                    else "Cần hỗ trợ nhanh khi có thay đổi về đơn hoặc kích thước."
                ),
                "created_at": now - timedelta(days=5 - index),
            },
        )
        _insert(
            bind,
            "contact_audit_events",
            {
                "workspace_id": DEMO_WORKSPACE_ID,
                "contact_id": contact_id,
                "actor_member_id": owner_member_id,
                "event_type": "profile_reviewed",
                "details_json": {"source": "demo_seed"},
                "created_at": now - timedelta(days=4 - index),
            },
            jsonb_columns=frozenset({"details_json"}),
        )

    tag_ids = [
        _insert_id(
            bind,
            "workspace_tags",
            {
                "workspace_id": DEMO_WORKSPACE_ID,
                "name": name,
                "normalized_name": normalized_name,
                "created_at": now - timedelta(days=30 - index),
            },
        )
        for index, (name, normalized_name) in enumerate(
            (("Khách tiềm năng", "khach-tiem-nang"), ("Cần theo dõi", "can-theo-doi"), ("VIP", "vip"))
        )
    ]
    for contact_id, tag_id in zip(contact_ids, tag_ids, strict=True):
        _insert(
            bind,
            "contact_tag_links",
            {
                "workspace_id": DEMO_WORKSPACE_ID,
                "contact_id": contact_id,
                "tag_id": tag_id,
                "created_at": now - timedelta(days=3),
            },
        )

    conversation_specs = (
        (
            UUID("73000000-0000-4000-8000-000000000001"),
            0,
            0,
            "open",
            "ai",
            None,
            (
                ("visitor", "inbound", "Mình cao 1m60, cần một set đi làm thanh lịch nhưng không quá cứng.", 0, 0),
                ("assistant", "outbound", "Bạn có thể phối blazer Ban Mai với quần suông cạp cao Hạ và áo thun Mộc.", 420, 96),
                ("visitor", "inbound", "Cửa hàng Quận 1 còn size M không?", 0, 0),
                ("assistant", "outbound", "Size M hiện còn tại Nguyễn Trãi. Mình có thể hướng dẫn bạn chọn size chi tiết hơn.", 510, 84),
            ),
        ),
        (
            UUID("73000000-0000-4000-8000-000000000002"),
            1,
            1,
            "pending",
            "human",
            owner_member_id,
            (
                ("visitor", "inbound", "Mình muốn đổi đầm size M sang size L thì cần làm gì?", 0, 0),
                ("assistant", "outbound", "Bạn có thể đổi trong 14 ngày nếu sản phẩm còn tem và chưa qua sử dụng.", 360, 72),
                ("visitor", "inbound", "Mình cần nhân viên kiểm tra giúp mã đơn DEMO-1042.", 0, 0),
                ("human", "outbound", "Mình đã tiếp nhận và sẽ kiểm tra tồn size L trước khi xác nhận đổi cho bạn.", 0, 0),
            ),
        ),
        (
            UUID("73000000-0000-4000-8000-000000000003"),
            0,
            0,
            "resolved",
            "ai",
            None,
            (
                ("visitor", "inbound", "Khăn lụa có phù hợp làm quà tặng không?", 0, 0),
                ("assistant", "outbound", "Khăn lụa Vườn Sớm là lựa chọn gọn nhẹ; bạn có thể chọn xanh rêu hoặc cam đất.", 330, 68),
                ("visitor", "inbound", "Mình chọn màu xanh rêu, cảm ơn nhé.", 0, 0),
                ("assistant", "outbound", "Rất vui được hỗ trợ bạn. Màu xanh rêu hiện còn ở cả cửa hàng và kho trực tuyến.", 290, 61),
            ),
        ),
    )
    conversation_ids: list[int] = []
    assistant_message_ids: list[int] = []
    session_ids: list[int] = []
    for conversation_index, (
        public_id,
        agent_index,
        channel_index,
        workflow_status,
        handling_mode,
        assigned_member_id,
        messages,
    ) in enumerate(conversation_specs):
        revision_id = revision_ids[agent_index]
        if revision_id is None:
            raise RuntimeError("Conversation demo agent is missing its revision")
        session_id = _insert_id(
            bind,
            "widget_sessions",
            {
                "workspace_id": DEMO_WORKSPACE_ID,
                "agent_id": agent_ids[agent_index],
                "channel_id": channel_ids[channel_index],
                "revision_id": revision_id,
                "token_hash": _sha256_text(f"moc-may-demo-session-{conversation_index}"),
                "normalized_origin": f"http://localhost:{3000 + channel_index}",
                "expires_at": now + timedelta(days=180),
                "created_at": now - timedelta(days=8 - conversation_index * 2),
            },
        )
        session_ids.append(session_id)
        last_message_at = now - timedelta(hours=conversation_index * 18 + 1)
        conversation_id = _insert_id(
            bind,
            "conversations",
            {
                "public_id": public_id,
                "workspace_id": DEMO_WORKSPACE_ID,
                "agent_id": agent_ids[agent_index],
                "revision_id": revision_id,
                "channel_connection_id": channel_ids[channel_index],
                "session_id": session_id,
                "lifecycle_state": "active",
                "workflow_status": workflow_status,
                "handling_mode": handling_mode,
                "assigned_member_id": assigned_member_id,
                "contact_id": contact_ids[conversation_index],
                "state_version": 2 if assigned_member_id is not None else 1,
                "last_message_at": last_message_at,
                "retention_until": now + timedelta(days=180),
                "created_at": now - timedelta(days=8 - conversation_index * 2),
            },
        )
        conversation_ids.append(conversation_id)
        for message_index, (actor, direction, body, input_tokens, output_tokens) in enumerate(messages):
            created_at = last_message_at - timedelta(minutes=(len(messages) - message_index) * 7)
            message_id = _insert_id(
                bind,
                "conversation_messages",
                {
                    "workspace_id": DEMO_WORKSPACE_ID,
                    "conversation_id": conversation_id,
                    "sequence_no": message_index + 1,
                    "actor": actor,
                    "direction": direction,
                    "text": body,
                    "status": "completed",
                    "request_key": f"demo-{conversation_index + 1}-{message_index + 1}",
                    "request_hash": _sha256_text(body),
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                    "created_at": created_at,
                    "completed_at": created_at + timedelta(seconds=2),
                },
            )
            if actor == "assistant":
                assistant_message_ids.append(message_id)
        _insert(
            bind,
            "conversation_read_states",
            {
                "workspace_id": DEMO_WORKSPACE_ID,
                "conversation_id": conversation_id,
                "member_id": owner_member_id,
                "last_read_sequence": 2 if workflow_status != "resolved" else 4,
                "updated_at": now - timedelta(hours=conversation_index + 1),
            },
        )
        _insert(
            bind,
            "conversation_tag_links",
            {
                "workspace_id": DEMO_WORKSPACE_ID,
                "conversation_id": conversation_id,
                "tag_id": tag_ids[conversation_index],
                "created_at": now - timedelta(days=2),
            },
        )
        _insert(
            bind,
            "conversation_audit_events",
            {
                "workspace_id": DEMO_WORKSPACE_ID,
                "conversation_id": conversation_id,
                "actor_member_id": owner_member_id,
                "event_type": "status_changed",
                "details_json": {"to": workflow_status, "source": "demo_seed"},
                "created_at": now - timedelta(hours=conversation_index + 3),
            },
            jsonb_columns=frozenset({"details_json"}),
        )
        if assigned_member_id is not None:
            _insert(
                bind,
                "conversation_notes",
                {
                    "workspace_id": DEMO_WORKSPACE_ID,
                    "conversation_id": conversation_id,
                    "author_member_id": owner_member_id,
                    "body": "Đã nhận mã đơn mẫu; cần xác nhận tồn size L trước khi phản hồi khách.",
                    "created_at": now - timedelta(hours=4),
                },
            )

    for index in (0, 1):
        email = contact_specs[index][2]
        phone = contact_specs[index][3]
        _insert(
            bind,
            "leads",
            {
                "workspace_id": DEMO_WORKSPACE_ID,
                "conversation_id": conversation_ids[index],
                "session_id": session_ids[index],
                "agent_id": agent_ids[index],
                "contact_id": contact_ids[index],
                "name": contact_specs[index][1],
                "normalized_email": email,
                "phone": phone,
                "consent_at": now - timedelta(days=6 - index * 2),
                "consent_text_version": "demo-lead-v1",
                "idempotency_key": f"demo-lead-{index + 1}",
                "request_hash": _sha256_text(f"{email}|{phone}"),
                "followup_status": "contacted" if index == 1 else "new",
                "retention_until": now + timedelta(days=180),
                "created_at": now - timedelta(days=6 - index * 2),
                "updated_at": now - timedelta(hours=index + 2),
            },
        )

    for index, message_id in enumerate(assistant_message_ids[:5]):
        _insert(
            bind,
            "analytics_events",
            {
                "workspace_id": DEMO_WORKSPACE_ID,
                "agent_id": agent_ids[1 if index in (2, 3) else 0],
                "conversation_id": conversation_ids[min(index // 2, 2)],
                "message_id": message_id,
                "product_id": product_ids[index],
                "channel": "web",
                "event_type": "product_impression",
                "occurred_at": now - timedelta(days=index, hours=2),
            },
        )

    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    _insert(
        bind,
        "workspace_usage_months",
        {
            "workspace_id": DEMO_WORKSPACE_ID,
            "period_started_at": period_start,
            "generated_turns": 38,
            "created_at": period_start,
            "updated_at": now - timedelta(hours=1),
        },
    )
    for index, conversation_id in enumerate(conversation_ids):
        _insert(
            bind,
            "usage_events",
            {
                "workspace_id": DEMO_WORKSPACE_ID,
                "agent_id": agent_ids[0 if index != 1 else 1],
                "conversation_id": conversation_id,
                "surface": "widget",
                "kind": "generation",
                "status": "completed",
                "provider": "demo",
                "model": "local-fixture",
                "model_calls": 2,
                "tool_calls": 1 if index != 1 else 0,
                "input_tokens": 720 + index * 110,
                "output_tokens": 145 + index * 20,
                "total_tokens": 865 + index * 130,
                "occurred_at": now - timedelta(days=index * 2, hours=1),
            },
        )


def upgrade() -> None:
    if os.getenv("APP_ENV") != "local":
        return

    bind = op.get_bind()
    existing_rows = list(
        bind.execute(
            sa.text("SELECT id, slug FROM workspaces WHERE id = :id OR slug = :slug"),
            {"id": DEMO_WORKSPACE_ID, "slug": DEMO_WORKSPACE_SLUG},
        ).mappings()
    )
    if existing_rows:
        if len(existing_rows) == 1 and existing_rows[0]["id"] == DEMO_WORKSPACE_ID:
            return
        raise RuntimeError("The local demo workspace slug or ID is already in use")

    owner_ids = list(
        bind.execute(
            sa.text(
                """
                SELECT DISTINCT wm.user_id
                FROM workspace_members wm
                JOIN workspaces w ON w.id = wm.workspace_id
                JOIN users u ON u.id = wm.user_id
                WHERE wm.role = 'owner' AND w.status = 'active' AND u.status = 'active'
                """
            )
        ).scalars()
    )
    if len(owner_ids) != 1:
        raise RuntimeError(
            "Local demo seeding requires exactly one active workspace owner; "
            f"found {len(owner_ids)}"
        )
    owner_user_id = cast(UUID, owner_ids[0])
    now = datetime.now(UTC)

    _insert(
        bind,
        "workspaces",
        {
            "id": DEMO_WORKSPACE_ID,
            "slug": DEMO_WORKSPACE_SLUG,
            "display_name": "Mộc & Mây Studio",
            "timezone": "Asia/Ho_Chi_Minh",
            "status": "active",
            "created_at": now - timedelta(days=240),
            "updated_at": now,
        },
    )
    owner_member_id = _insert_id(
        bind,
        "workspace_members",
        {
            "workspace_id": DEMO_WORKSPACE_ID,
            "user_id": owner_user_id,
            "role": "owner",
            "created_at": now - timedelta(days=240),
        },
    )
    location_ids, collection_ids, product_ids = _seed_catalog(bind, now)
    knowledge_base_ids, _ = _seed_knowledge(bind, owner_user_id, now)
    agent_ids, revision_ids = _seed_agents(
        bind,
        owner_user_id,
        knowledge_base_ids,
        location_ids,
        collection_ids,
        now,
    )
    channel_ids = _seed_channels(bind, agent_ids, revision_ids, now)
    _seed_operations(
        bind,
        owner_member_id,
        agent_ids,
        revision_ids,
        channel_ids,
        product_ids,
        now,
    )


def downgrade() -> None:
    if os.getenv("APP_ENV") != "local":
        return

    bind = op.get_bind()
    tables = (
        "analytics_events",
        "usage_events",
        "workspace_usage_months",
        "leads",
        "conversation_audit_events",
        "conversation_tag_links",
        "conversation_notes",
        "conversation_read_states",
        "conversation_messages",
        "conversations",
        "widget_sessions",
        "contact_audit_events",
        "contact_tag_links",
        "contact_notes",
        "contact_identities",
        "contacts",
        "workspace_tags",
        "widget_domains",
        "website_channel_configs",
        "channel_agent_bindings",
        "channel_connections",
        "agent_knowledge_bases",
        "knowledge_document_versions",
        "knowledge_documents",
        "knowledge_bases",
        "agent_locations",
        "agent_catalog_collections",
        "variant_option_values",
        "product_option_values",
        "product_option_definitions",
        "inventory_levels",
        "location_variants",
        "size_guides",
        "catalog_collection_products",
        "product_variants",
        "products",
        "catalog_collections",
        "locations",
        "agent_revisions",
        "agents",
        "workspace_members",
    )
    for table in tables:
        bind.execute(
            sa.text(f"DELETE FROM {table} WHERE workspace_id = :workspace_id"),
            {"workspace_id": DEMO_WORKSPACE_ID},
        )
    bind.execute(
        sa.text("DELETE FROM workspaces WHERE id = :workspace_id"),
        {"workspace_id": DEMO_WORKSPACE_ID},
    )
