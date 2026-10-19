"""Expand the local demo workspace with high-volume realistic data.

Revision ID: 20261019_0023
Revises: 20261019_0022
"""

from collections.abc import Sequence
import os

import sqlalchemy as sa
from alembic import op

revision: str = "20261019_0023"
down_revision: str | None = "20261019_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEMO_WORKSPACE_ID = "70000000-0000-4000-8000-000000000001"


def upgrade() -> None:
    if os.getenv("APP_ENV") != "local":
        return

    bind = op.get_bind()
    workspace_count = bind.execute(
        sa.text(
            """
            SELECT count(*)
            FROM workspaces
            WHERE id = CAST(:workspace_id AS uuid)
              AND slug = 'moc-may-studio'
              AND status = 'active'
            """
        ),
        {"workspace_id": DEMO_WORKSPACE_ID},
    ).scalar_one()
    if workspace_count != 1:
        raise RuntimeError("The base local demo workspace is missing or inactive")

    owner_count = bind.execute(
        sa.text(
            """
            SELECT count(*)
            FROM workspace_members
            WHERE workspace_id = CAST(:workspace_id AS uuid)
              AND role = 'owner'
            """
        ),
        {"workspace_id": DEMO_WORKSPACE_ID},
    ).scalar_one()
    if owner_count != 1:
        raise RuntimeError("Expanded demo seeding requires exactly one demo workspace owner")

    marker_count = bind.execute(
        sa.text(
            """
            SELECT
                (SELECT count(*) FROM products
                 WHERE workspace_id = CAST(:workspace_id AS uuid)
                   AND product_sku LIKE 'MM-DEMO-%')
              + (SELECT count(*) FROM agents
                 WHERE workspace_id = CAST(:workspace_id AS uuid)
                   AND public_id::text LIKE '74000000-0000-4000-8000-%')
            """
        ),
        {"workspace_id": DEMO_WORKSPACE_ID},
    ).scalar_one()
    if marker_count != 0:
        raise RuntimeError("Expanded local demo data already exists")

    bind.execute(sa.text(_EXPANSION_SQL))


def downgrade() -> None:
    if os.getenv("APP_ENV") != "local":
        return
    op.get_bind().execute(sa.text(_DOWNGRADE_SQL))


_EXPANSION_SQL = f"""
DO $demo$
DECLARE
    v_workspace_id uuid := '{DEMO_WORKSPACE_ID}'::uuid;
    v_owner_user_id uuid;
    v_owner_member_id bigint;
    v_now timestamptz := now();
    v_location_id bigint;
    v_collection_id bigint;
    v_product_id bigint;
    v_variant_id bigint;
    v_color_definition_id bigint;
    v_size_definition_id bigint;
    v_color_value_id bigint;
    v_size_value_id bigint;
    v_base_id bigint;
    v_document_id bigint;
    v_agent_id bigint;
    v_revision_id bigint;
    v_channel_id bigint;
    v_contact_id bigint;
    v_session_id bigint;
    v_conversation_id bigint;
    v_bound_agent_id bigint;
    v_bound_revision_id bigint;
    v_bound_channel_id bigint;
    v_contact_email text;
    v_contact_phone text;
    v_status text;
    v_mode text;
    v_message_id bigint;
    v_product_name text;
    v_category text;
    v_color text;
    v_size text;
    v_agent_name text;
    v_agent_status text;
    v_all_scope boolean;
    v_knowledge_ids jsonb;
    v_catalog_scope jsonb;
    v_widget_config jsonb;
    v_config_source text;
    v_first_message_id bigint;
    v_second_product_id bigint;
    i integer;
    j integer;
    k integer;
BEGIN
    SELECT wm.user_id, wm.id
      INTO STRICT v_owner_user_id, v_owner_member_id
      FROM workspace_members wm
     WHERE wm.workspace_id = v_workspace_id
       AND wm.role = 'owner';

    INSERT INTO locations (
        workspace_id, name, code, type, address_json, metadata_json,
        is_active, created_at, updated_at
    ) VALUES
        (
            v_workspace_id,
            'Showroom Hồ Tây',
            'DEMO-HN-HT',
            'showroom',
            '{{"line1":"18 Xuân Diệu","district":"Tây Hồ","city":"Hà Nội"}}'::jsonb,
            '{{"seed_revision":"20261019_0023"}}'::jsonb,
            true,
            v_now - interval '170 days',
            v_now - interval '3 hours'
        ),
        (
            v_workspace_id,
            'Cửa hàng Đà Nẵng',
            'DEMO-DN-HC',
            'store',
            '{{"line1":"64 Lê Duẩn","district":"Hải Châu","city":"Đà Nẵng"}}'::jsonb,
            '{{"seed_revision":"20261019_0023"}}'::jsonb,
            true,
            v_now - interval '130 days',
            v_now - interval '5 hours'
        ),
        (
            v_workspace_id,
            'Kho Bình Tân',
            'DEMO-HCM-BT',
            'warehouse',
            '{{"line1":"220 Hồ Học Lãm","district":"Bình Tân","city":"TP.HCM"}}'::jsonb,
            '{{"seed_revision":"20261019_0023"}}'::jsonb,
            true,
            v_now - interval '110 days',
            v_now - interval '2 hours'
        );

    INSERT INTO catalog_collections (
        workspace_id, name, description, is_active, created_at, updated_at
    ) VALUES
        (v_workspace_id, 'Demo: Hàng mới', 'Thiết kế vừa cập nhật trong mùa hiện tại.', true, v_now - interval '90 days', v_now),
        (v_workspace_id, 'Demo: Dạo phố', 'Trang phục linh hoạt cho lịch trình thường ngày.', true, v_now - interval '85 days', v_now),
        (v_workspace_id, 'Demo: Tối giản', 'Phom dáng gọn và bảng màu dễ phối.', true, v_now - interval '80 days', v_now),
        (v_workspace_id, 'Demo: Dịp lễ', 'Lựa chọn nổi bật cho tiệc và sự kiện.', true, v_now - interval '75 days', v_now),
        (v_workspace_id, 'Demo: Quà tặng', 'Phụ kiện và sản phẩm phù hợp làm quà.', true, v_now - interval '70 days', v_now),
        (v_workspace_id, 'Demo: Du lịch', 'Chất liệu nhẹ và dễ sắp xếp hành lý.', true, v_now - interval '65 days', v_now),
        (v_workspace_id, 'Demo: Cuối tuần', 'Trang phục thoải mái cho thời gian nghỉ.', true, v_now - interval '60 days', v_now);

    FOR i IN 1..32 LOOP
        v_product_name := (ARRAY[
            'Áo blouse Mưa Nhẹ',
            'Chân váy midi Nhịp Sống',
            'Quần linen Dòng Chảy',
            'Cardigan Mềm',
            'Đầm cổ vuông Trăng Non',
            'Túi đeo vai Nếp',
            'Sandal Quai Mảnh',
            'Áo khoác Gió Sớm'
        ])[((i - 1) % 8) + 1] || ' ' || lpad((((i - 1) / 8) + 1)::text, 2, '0');
        v_category := (ARRAY[
            'Áo nữ', 'Chân váy', 'Quần nữ', 'Áo khoác',
            'Đầm', 'Túi xách', 'Giày', 'Áo khoác'
        ])[((i - 1) % 8) + 1];

        INSERT INTO products (
            workspace_id, product_sku, name, slug, brand, description,
            description_text, category, currency, price, compare_at_price,
            inventory_policy, attributes_json, status, created_at, updated_at
        ) VALUES (
            v_workspace_id,
            'MM-DEMO-' || lpad((1000 + i)::text, 4, '0'),
            v_product_name,
            'demo-san-pham-' || lpad(i::text, 2, '0'),
            'Mộc & Mây',
            'Thiết kế mẫu có thông tin chất liệu, biến thể và tồn kho theo từng địa điểm.',
            'Thiết kế mẫu có thông tin chất liệu, biến thể và tồn kho theo từng địa điểm.',
            v_category,
            'VND',
            390000 + i * 45000,
            CASE WHEN i % 3 = 0 THEN 490000 + i * 50000 ELSE NULL END,
            'tracked',
            jsonb_build_object(
                'seed_revision', '20261019_0023',
                'material', (ARRAY['cotton','linen','viscose','lụa pha'])[((i - 1) % 4) + 1],
                'season', (ARRAY['xuân hè','quanh năm','thu đông'])[((i - 1) % 3) + 1]
            ),
            'active',
            v_now - make_interval(days => 100 - i * 2),
            v_now - make_interval(hours => i)
        ) RETURNING id INTO v_product_id;

        INSERT INTO product_option_definitions (
            workspace_id, product_id, name, normalized_name, position
        ) VALUES (v_workspace_id, v_product_id, 'Màu sắc', 'color', 0)
        RETURNING id INTO v_color_definition_id;

        INSERT INTO product_option_definitions (
            workspace_id, product_id, name, normalized_name, position
        ) VALUES (v_workspace_id, v_product_id, 'Kích thước', 'size', 1)
        RETURNING id INTO v_size_definition_id;

        FOR j IN 1..4 LOOP
            v_color := (ARRAY['Trắng kem','Đen','Be cát','Xanh rêu'])[j];
            v_size := (ARRAY['S','M','L','XL'])[j];

            INSERT INTO product_option_values (
                workspace_id, option_definition_id, value, normalized_value, position
            ) VALUES (
                v_workspace_id, v_color_definition_id, v_color, lower(v_color), j - 1
            ) RETURNING id INTO v_color_value_id;

            INSERT INTO product_option_values (
                workspace_id, option_definition_id, value, normalized_value, position
            ) VALUES (
                v_workspace_id, v_size_definition_id, v_size, lower(v_size), j - 1
            ) RETURNING id INTO v_size_value_id;

            INSERT INTO product_variants (
                workspace_id, product_id, variant_sku, name, color, size,
                inventory_policy, option_signature, attributes_json, status,
                created_at, updated_at
            ) VALUES (
                v_workspace_id,
                v_product_id,
                'MM-DEMO-' || lpad((1000 + i)::text, 4, '0') || '-V' || j,
                v_color || ' / ' || v_size,
                v_color,
                v_size,
                'tracked',
                'color=' || lower(v_color) || '|size=' || lower(v_size),
                jsonb_build_object('seed_revision', '20261019_0023'),
                'active',
                v_now - make_interval(days => 95 - i * 2),
                v_now - make_interval(hours => i + j)
            ) RETURNING id INTO v_variant_id;

            INSERT INTO variant_option_values (
                workspace_id, variant_id, option_value_id, option_definition_id
            ) VALUES
                (v_workspace_id, v_variant_id, v_color_value_id, v_color_definition_id),
                (v_workspace_id, v_variant_id, v_size_value_id, v_size_definition_id);

            FOR v_location_id IN
                SELECT id
                  FROM locations
                 WHERE workspace_id = v_workspace_id
                   AND is_active = true
                 ORDER BY id
            LOOP
                INSERT INTO location_variants (
                    workspace_id, location_id, variant_id, is_active,
                    metadata_json, created_at, updated_at
                ) VALUES (
                    v_workspace_id,
                    v_location_id,
                    v_variant_id,
                    true,
                    jsonb_build_object('seed_revision', '20261019_0023'),
                    v_now - interval '50 days',
                    v_now - make_interval(hours => ((i + j) % 12) + 1)
                );

                INSERT INTO inventory_levels (
                    workspace_id, location_id, variant_id, quantity, updated_at
                ) VALUES (
                    v_workspace_id,
                    v_location_id,
                    v_variant_id,
                    2 + ((i * j + v_location_id) % 29),
                    v_now - make_interval(hours => ((i + j) % 12) + 1)
                );
            END LOOP;
        END LOOP;

        FOR v_collection_id IN
            SELECT id
              FROM catalog_collections
             WHERE workspace_id = v_workspace_id
               AND name LIKE 'Demo: %'
             ORDER BY id
             OFFSET ((i - 1) % 7)
             LIMIT 1
        LOOP
            INSERT INTO catalog_collection_products (
                workspace_id, collection_id, product_id
            ) VALUES (v_workspace_id, v_collection_id, v_product_id);
        END LOOP;

        FOR v_collection_id IN
            SELECT id
              FROM catalog_collections
             WHERE workspace_id = v_workspace_id
               AND name LIKE 'Demo: %'
             ORDER BY id
             OFFSET (i % 7)
             LIMIT 1
        LOOP
            INSERT INTO catalog_collection_products (
                workspace_id, collection_id, product_id
            ) VALUES (v_workspace_id, v_collection_id, v_product_id)
            ON CONFLICT DO NOTHING;
        END LOOP;

        IF v_category IN ('Áo nữ', 'Chân váy', 'Quần nữ', 'Áo khoác', 'Đầm') THEN
            INSERT INTO size_guides (
                workspace_id, product_id, title, content, created_at, updated_at
            ) VALUES (
                v_workspace_id,
                v_product_id,
                'Bảng kích thước tham khảo',
                '{{"unit":"cm","columns":["Size","Ngực","Eo","Mông"],"rows":[["S","82-86","64-68","88-92"],["M","87-91","69-73","93-97"],["L","92-96","74-78","98-102"],["XL","97-101","79-83","103-107"]]}}'::json,
                v_now - interval '45 days',
                v_now - interval '2 days'
            );
        END IF;
    END LOOP;

    INSERT INTO knowledge_bases (
        workspace_id, name, kind, status, created_at, updated_at
    ) VALUES
        (v_workspace_id, 'Demo: Phong cách & chất liệu', 'general', 'active', v_now - interval '88 days', v_now),
        (v_workspace_id, 'Demo: Vận hành cửa hàng', 'faq', 'active', v_now - interval '82 days', v_now),
        (v_workspace_id, 'Demo: Giao nhận & thành viên', 'policy', 'active', v_now - interval '76 days', v_now);

    FOR v_base_id IN
        SELECT id
          FROM knowledge_bases
         WHERE workspace_id = v_workspace_id
           AND name LIKE 'Demo: %'
         ORDER BY id
    LOOP
        FOR j IN 1..6 LOOP
            INSERT INTO knowledge_documents (
                workspace_id, knowledge_base_id, title, kind, status,
                created_at, updated_at
            ) VALUES (
                v_workspace_id,
                v_base_id,
                'Tài liệu vận hành mẫu ' || j || ' — ' ||
                    (SELECT name FROM knowledge_bases WHERE id = v_base_id),
                CASE WHEN j % 3 = 0 THEN 'policy' WHEN j % 2 = 0 THEN 'faq' ELSE 'document' END,
                'active',
                v_now - make_interval(days => 70 - j * 3),
                v_now - make_interval(days => j)
            ) RETURNING id INTO v_document_id;

            INSERT INTO knowledge_document_versions (
                workspace_id, document_id, version_no, source_kind, source_text,
                content_sha256, mime_type, byte_size, created_by_user_id,
                reviewed_at, review_due_at, reviewed_by_user_id, created_at
            ) VALUES (
                v_workspace_id,
                v_document_id,
                1,
                'manual',
                'Nội dung mẫu số ' || j ||
                    ' mô tả quy trình, điều kiện áp dụng, trường hợp ngoại lệ và cách chuyển tiếp cho nhân viên. ' ||
                    'Thông tin chỉ dùng trong workspace demo và chưa được lập chỉ mục vector.',
                md5(v_document_id::text || '-demo') || md5('knowledge-' || v_document_id::text),
                'text/plain',
                220 + j * 17,
                v_owner_user_id,
                CASE WHEN j <= 4 THEN v_now - make_interval(days => 20 - j) ELSE NULL END,
                CASE
                    WHEN j <= 2 THEN v_now - make_interval(days => j)
                    WHEN j <= 4 THEN v_now + make_interval(days => 45 + j * 5)
                    ELSE NULL
                END,
                CASE WHEN j <= 4 THEN v_owner_user_id ELSE NULL END,
                v_now - make_interval(days => 65 - j * 3)
            );
        END LOOP;
    END LOOP;

    SELECT jsonb_agg(id ORDER BY id)
      INTO v_knowledge_ids
      FROM knowledge_bases
     WHERE workspace_id = v_workspace_id
       AND name LIKE 'Demo: %';

    FOR i IN 1..7 LOOP
        v_agent_name := (ARRAY[
            'Tư vấn bộ sưu tập',
            'Hỗ trợ đổi trả',
            'Điều phối cửa hàng',
            'Chăm sóc thành viên',
            'Gợi ý quà tặng',
            'Trợ lý sự kiện',
            'Tư vấn chất liệu'
        ])[i];
        v_agent_status := CASE WHEN i <= 2 THEN 'published' WHEN i <= 4 THEN 'paused' ELSE 'draft' END;
        v_all_scope := i % 2 = 1;

        INSERT INTO agents (
            public_id, workspace_id, name, greeting, safe_instructions,
            default_locale, status, all_locations, all_collections,
            created_by_user_id, created_at, updated_at
        ) VALUES (
            ('74000000-0000-4000-8000-' || lpad(i::text, 12, '0'))::uuid,
            v_workspace_id,
            v_agent_name,
            'Xin chào! Tôi là ' || lower(v_agent_name) || ' của Mộc & Mây Studio.',
            'Chỉ sử dụng dữ liệu được cấp trong workspace. Chuyển nhân viên khi cần xác minh giao dịch hoặc danh tính.',
            'vi',
            v_agent_status,
            v_all_scope,
            v_all_scope,
            v_owner_user_id,
            v_now - make_interval(days => 55 - i * 4),
            v_now - make_interval(hours => i * 3)
        ) RETURNING id INTO v_agent_id;

        FOR v_base_id IN
            SELECT id
              FROM knowledge_bases
             WHERE workspace_id = v_workspace_id
               AND name LIKE 'Demo: %'
             ORDER BY id
             OFFSET ((i - 1) % 3)
             LIMIT 2
        LOOP
            INSERT INTO agent_knowledge_bases (
                workspace_id, agent_id, knowledge_base_id
            ) VALUES (v_workspace_id, v_agent_id, v_base_id);
        END LOOP;

        IF NOT v_all_scope THEN
            INSERT INTO agent_locations (workspace_id, agent_id, location_id)
            SELECT v_workspace_id, v_agent_id, id
              FROM locations
             WHERE workspace_id = v_workspace_id
               AND is_active = true
             ORDER BY id
             LIMIT 3;

            INSERT INTO agent_catalog_collections (workspace_id, agent_id, collection_id)
            SELECT v_workspace_id, v_agent_id, id
              FROM catalog_collections
             WHERE workspace_id = v_workspace_id
               AND name LIKE 'Demo: %'
             ORDER BY id
             LIMIT 3;
        END IF;

        IF v_agent_status IN ('published', 'paused') THEN
            IF v_all_scope THEN
                v_catalog_scope := jsonb_build_object('location_ids', NULL, 'collection_ids', NULL);
            ELSE
                v_catalog_scope := jsonb_build_object(
                    'location_ids', (
                        SELECT jsonb_agg(id ORDER BY id)
                          FROM (
                              SELECT id FROM locations
                               WHERE workspace_id = v_workspace_id AND is_active = true
                               ORDER BY id LIMIT 3
                          ) scoped_locations
                    ),
                    'collection_ids', (
                        SELECT jsonb_agg(id ORDER BY id)
                          FROM (
                              SELECT id FROM catalog_collections
                               WHERE workspace_id = v_workspace_id AND name LIKE 'Demo: %'
                               ORDER BY id LIMIT 3
                          ) scoped_collections
                    )
                );
            END IF;
            v_widget_config := jsonb_build_object(
                'brand_color', CASE WHEN i % 2 = 0 THEN '#315D8A' ELSE '#0F8F87' END,
                'launcher_position', 'right',
                'handoff_url', 'https://example.test/support',
                'handoff_label', 'Gặp nhân viên'
            );
            v_config_source := v_agent_name || v_catalog_scope::text || v_knowledge_ids::text;

            INSERT INTO agent_revisions (
                workspace_id, agent_id, revision_no, name, greeting,
                safe_instructions, default_locale, catalog_scope_json,
                knowledge_base_ids_json, widget_config_json, config_hash,
                created_by_user_id, published_at
            ) VALUES (
                v_workspace_id,
                v_agent_id,
                1,
                v_agent_name,
                'Xin chào! Tôi là ' || lower(v_agent_name) || ' của Mộc & Mây Studio.',
                'Chỉ sử dụng dữ liệu được cấp trong workspace. Chuyển nhân viên khi cần xác minh giao dịch hoặc danh tính.',
                'vi',
                v_catalog_scope,
                v_knowledge_ids,
                v_widget_config,
                md5(v_config_source) || md5('revision-' || v_config_source),
                v_owner_user_id,
                v_now - make_interval(days => 25 - i * 3)
            ) RETURNING id INTO v_revision_id;
        END IF;
    END LOOP;

    FOR i IN 1..3 LOOP
        SELECT a.id, r.id
          INTO STRICT v_agent_id, v_revision_id
          FROM agents a
          JOIN agent_revisions r
            ON r.workspace_id = a.workspace_id AND r.agent_id = a.id
         WHERE a.workspace_id = v_workspace_id
           AND a.public_id = ('74000000-0000-4000-8000-' || lpad(i::text, 12, '0'))::uuid;

        INSERT INTO channel_connections (
            workspace_id, provider, display_name, lifecycle_state, health_state,
            created_at, updated_at
        ) VALUES (
            v_workspace_id,
            'web',
            'Demo: Website chuyên đề ' || i,
            'active',
            'unknown',
            v_now - make_interval(days => 24 - i * 3),
            v_now - make_interval(hours => i)
        ) RETURNING id INTO v_channel_id;

        INSERT INTO website_channel_configs (
            connection_id, workspace_id, brand_color, launcher_position,
            handoff_url, handoff_label, created_at, updated_at
        ) VALUES (
            v_channel_id,
            v_workspace_id,
            CASE WHEN i % 2 = 0 THEN '#315D8A' ELSE '#0F8F87' END,
            'right',
            'https://example.test/support',
            'Gặp nhân viên',
            v_now - make_interval(days => 24 - i * 3),
            v_now - make_interval(hours => i)
        );

        INSERT INTO widget_domains (
            workspace_id, channel_id, normalized_origin, created_at
        ) VALUES (
            v_workspace_id,
            v_channel_id,
            'http://localhost:' || (3100 + i),
            v_now - make_interval(days => 24 - i * 3)
        );

        INSERT INTO channel_agent_bindings (
            workspace_id, connection_id, agent_id, active_revision_id,
            enabled, created_at, updated_at
        ) VALUES (
            v_workspace_id,
            v_channel_id,
            v_agent_id,
            v_revision_id,
            i <= 2,
            v_now - make_interval(days => 24 - i * 3),
            v_now - make_interval(hours => i)
        );
    END LOOP;

    INSERT INTO workspace_tags (workspace_id, name, normalized_name, created_at)
    VALUES
        (v_workspace_id, 'Demo Quan tâm sản phẩm', 'demo-quan-tam-san-pham', v_now - interval '40 days'),
        (v_workspace_id, 'Demo Chờ phản hồi', 'demo-cho-phan-hoi', v_now - interval '38 days'),
        (v_workspace_id, 'Demo Đã tư vấn', 'demo-da-tu-van', v_now - interval '36 days'),
        (v_workspace_id, 'Demo Cần nhân viên', 'demo-can-nhan-vien', v_now - interval '34 days'),
        (v_workspace_id, 'Demo Khách quay lại', 'demo-khach-quay-lai', v_now - interval '32 days');

    FOR i IN 1..57 LOOP
        v_contact_email := 'demo.contact.' || lpad(i::text, 3, '0') || '@example.test';
        v_contact_phone := '+8492' || lpad((1000000 + i)::text, 7, '0');

        INSERT INTO contacts (
            public_id, workspace_id, display_name, assigned_member_id,
            lifecycle_state, state_version, retention_until, created_at, updated_at
        ) VALUES (
            ('75000000-0000-4000-8000-' || lpad(i::text, 12, '0'))::uuid,
            v_workspace_id,
            (ARRAY['An','Bình','Chi','Dũng','Giang','Hà','Khánh','Linh','Minh','Ngọc'])[((i - 1) % 10) + 1]
                || ' '
                || (ARRAY['Nguyễn','Trần','Lê','Phạm','Võ','Đặng','Bùi','Đỗ'])[((i - 1) % 8) + 1]
                || ' ' || lpad(i::text, 2, '0'),
            CASE WHEN i % 4 = 0 THEN v_owner_member_id ELSE NULL END,
            'active',
            CASE WHEN i % 4 = 0 THEN 2 ELSE 1 END,
            v_now + interval '365 days',
            v_now - make_interval(days => 90 - (i % 70)),
            v_now - make_interval(hours => i % 72)
        ) RETURNING id INTO v_contact_id;

        INSERT INTO contact_identities (
            workspace_id, contact_id, connection_id, provider, identity_type,
            normalized_value, verification_state, consent_at,
            consent_text_version, retention_until, created_at
        ) VALUES
            (
                v_workspace_id, v_contact_id, NULL, 'website', 'email',
                v_contact_email, 'consented', v_now - make_interval(days => 60 - (i % 50)),
                'demo-contact-v2', v_now + interval '365 days',
                v_now - make_interval(days => 60 - (i % 50))
            ),
            (
                v_workspace_id, v_contact_id, NULL, 'website', 'phone',
                v_contact_phone, 'consented', v_now - make_interval(days => 60 - (i % 50)),
                'demo-contact-v2', v_now + interval '365 days',
                v_now - make_interval(days => 60 - (i % 50))
            );

        IF i % 3 = 0 THEN
            INSERT INTO contact_notes (
                workspace_id, contact_id, author_member_id, body, created_at
            ) VALUES (
                v_workspace_id,
                v_contact_id,
                v_owner_member_id,
                CASE
                    WHEN i % 2 = 0 THEN 'Quan tâm dòng linen và thường chọn màu trung tính.'
                    ELSE 'Ưu tiên nhận thông tin qua email và giao hàng ngoài giờ hành chính.'
                END,
                v_now - make_interval(days => i % 20)
            );
        END IF;

        INSERT INTO contact_audit_events (
            workspace_id, contact_id, actor_member_id, event_type,
            details_json, created_at
        ) VALUES (
            v_workspace_id,
            v_contact_id,
            v_owner_member_id,
            'profile_reviewed',
            jsonb_build_object('source', 'expanded_demo_seed'),
            v_now - make_interval(days => i % 30)
        );

        SELECT id
          INTO v_collection_id
          FROM workspace_tags
         WHERE workspace_id = v_workspace_id
           AND normalized_name LIKE 'demo-%'
         ORDER BY id
         OFFSET ((i - 1) % 5)
         LIMIT 1;

        INSERT INTO contact_tag_links (
            workspace_id, contact_id, tag_id, created_at
        ) VALUES (
            v_workspace_id, v_contact_id, v_collection_id,
            v_now - make_interval(days => i % 25)
        );
    END LOOP;

    FOR i IN 1..97 LOOP
        SELECT cc.id, cab.agent_id, cab.active_revision_id
          INTO STRICT v_bound_channel_id, v_bound_agent_id, v_bound_revision_id
          FROM channel_connections cc
          JOIN channel_agent_bindings cab
            ON cab.workspace_id = cc.workspace_id AND cab.connection_id = cc.id
         WHERE cc.workspace_id = v_workspace_id
           AND cc.display_name LIKE 'Demo: Website chuyên đề %'
         ORDER BY cc.id
         OFFSET ((i - 1) % 3)
         LIMIT 1;

        SELECT id
          INTO STRICT v_contact_id
          FROM contacts
         WHERE workspace_id = v_workspace_id
           AND public_id::text LIKE '75000000-0000-4000-8000-%'
         ORDER BY public_id
         OFFSET ((i - 1) % 57)
         LIMIT 1;

        v_status := CASE WHEN i % 10 < 4 THEN 'open' WHEN i % 10 < 7 THEN 'pending' ELSE 'resolved' END;
        v_mode := CASE WHEN i % 7 = 0 THEN 'human' WHEN i % 11 = 0 THEN 'paused' ELSE 'ai' END;

        INSERT INTO widget_sessions (
            workspace_id, agent_id, channel_id, revision_id, token_hash,
            normalized_origin, expires_at, created_at
        ) VALUES (
            v_workspace_id,
            v_bound_agent_id,
            v_bound_channel_id,
            v_bound_revision_id,
            md5('expanded-demo-session-' || i) || md5('token-' || i),
            'http://localhost:' || (3101 + ((i - 1) % 3)),
            v_now + interval '180 days',
            v_now - make_interval(days => 90 - (i % 89))
        ) RETURNING id INTO v_session_id;

        INSERT INTO conversations (
            public_id, workspace_id, agent_id, revision_id,
            channel_connection_id, session_id, lifecycle_state,
            workflow_status, handling_mode, assigned_member_id,
            contact_id, state_version, last_message_at,
            retention_until, created_at
        ) VALUES (
            ('76000000-0000-4000-8000-' || lpad(i::text, 12, '0'))::uuid,
            v_workspace_id,
            v_bound_agent_id,
            v_bound_revision_id,
            v_bound_channel_id,
            v_session_id,
            'active',
            v_status,
            v_mode,
            CASE WHEN v_mode = 'human' THEN v_owner_member_id ELSE NULL END,
            v_contact_id,
            CASE WHEN v_mode = 'human' THEN 2 ELSE 1 END,
            v_now - make_interval(hours => i % 96),
            v_now + interval '180 days',
            v_now - make_interval(days => 90 - (i % 89))
        ) RETURNING id INTO v_conversation_id;

        FOR j IN 1..4 LOOP
            INSERT INTO conversation_messages (
                workspace_id, conversation_id, sequence_no, actor, direction,
                text, status, request_key, request_hash,
                input_tokens, output_tokens, total_tokens,
                created_at, completed_at
            ) VALUES (
                v_workspace_id,
                v_conversation_id,
                j,
                CASE
                    WHEN j % 2 = 1 THEN 'visitor'
                    WHEN v_mode = 'human' AND j = 4 THEN 'human'
                    ELSE 'assistant'
                END,
                CASE WHEN j % 2 = 1 THEN 'inbound' ELSE 'outbound' END,
                CASE j
                    WHEN 1 THEN 'Mình cần tư vấn sản phẩm phù hợp cho lịch làm việc và cuối tuần.'
                    WHEN 2 THEN 'Bạn có thể bắt đầu với thiết kế phom gọn, màu trung tính và chất liệu thoáng.'
                    WHEN 3 THEN 'Mẫu này còn kích thước phù hợp tại cửa hàng gần nhất không?'
                    ELSE CASE
                        WHEN v_mode = 'human' THEN 'Mình đã tiếp nhận và sẽ kiểm tra tồn kho chi tiết cho bạn.'
                        ELSE 'Hiện có nhiều biến thể tại các địa điểm; bạn cho mình biết kích thước mong muốn nhé.'
                    END
                END,
                'completed',
                'expanded-demo-' || i || '-' || j,
                md5('expanded-demo-' || i || '-' || j) || md5('message-' || i || '-' || j),
                CASE WHEN j % 2 = 0 AND v_mode <> 'human' THEN 360 + i * 3 ELSE 0 END,
                CASE WHEN j % 2 = 0 AND v_mode <> 'human' THEN 72 + (i % 30) ELSE 0 END,
                CASE WHEN j % 2 = 0 AND v_mode <> 'human' THEN 432 + i * 3 + (i % 30) ELSE 0 END,
                v_now - make_interval(hours => i % 96, mins => (5 - j) * 6),
                v_now - make_interval(hours => i % 96, mins => (5 - j) * 6) + interval '2 seconds'
            ) RETURNING id INTO v_message_id;
        END LOOP;

        INSERT INTO conversation_read_states (
            workspace_id, conversation_id, member_id,
            last_read_sequence, updated_at
        ) VALUES (
            v_workspace_id,
            v_conversation_id,
            v_owner_member_id,
            CASE WHEN v_status = 'resolved' THEN 4 ELSE 2 END,
            v_now - make_interval(hours => i % 48)
        );

        SELECT id
          INTO v_collection_id
          FROM workspace_tags
         WHERE workspace_id = v_workspace_id
           AND normalized_name LIKE 'demo-%'
         ORDER BY id
         OFFSET ((i - 1) % 5)
         LIMIT 1;

        INSERT INTO conversation_tag_links (
            workspace_id, conversation_id, tag_id, created_at
        ) VALUES (
            v_workspace_id,
            v_conversation_id,
            v_collection_id,
            v_now - make_interval(days => i % 30)
        );

        INSERT INTO conversation_audit_events (
            workspace_id, conversation_id, actor_member_id,
            event_type, details_json, created_at
        ) VALUES (
            v_workspace_id,
            v_conversation_id,
            v_owner_member_id,
            'status_changed',
            jsonb_build_object('to', v_status, 'source', 'expanded_demo_seed'),
            v_now - make_interval(hours => (i % 96) + 1)
        );

        IF v_mode = 'human' THEN
            INSERT INTO conversation_notes (
                workspace_id, conversation_id, author_member_id, body, created_at
            ) VALUES (
                v_workspace_id,
                v_conversation_id,
                v_owner_member_id,
                'Cần xác nhận tồn kho và thời gian giao trước khi phản hồi khách.',
                v_now - make_interval(hours => (i % 96) + 1)
            );
        END IF;

        IF i <= 28 THEN
            SELECT normalized_value
              INTO STRICT v_contact_email
              FROM contact_identities
             WHERE workspace_id = v_workspace_id
               AND contact_id = v_contact_id
               AND identity_type = 'email';
            SELECT normalized_value
              INTO STRICT v_contact_phone
              FROM contact_identities
             WHERE workspace_id = v_workspace_id
               AND contact_id = v_contact_id
               AND identity_type = 'phone';

            INSERT INTO leads (
                workspace_id, conversation_id, session_id, agent_id,
                contact_id, name, normalized_email, phone, consent_at,
                consent_text_version, idempotency_key, request_hash,
                followup_status, retention_until, created_at, updated_at
            ) VALUES (
                v_workspace_id,
                v_conversation_id,
                v_session_id,
                v_bound_agent_id,
                v_contact_id,
                (SELECT display_name FROM contacts WHERE id = v_contact_id),
                v_contact_email,
                v_contact_phone,
                v_now - make_interval(days => i % 25),
                'expanded-demo-lead-v1',
                'expanded-demo-lead-' || i,
                md5(v_contact_email) || md5(v_contact_phone),
                (ARRAY['new','contacted','closed'])[((i - 1) % 3) + 1],
                v_now + interval '180 days',
                v_now - make_interval(days => i % 25),
                v_now - make_interval(hours => i % 48)
            );
        END IF;

        INSERT INTO usage_events (
            workspace_id, agent_id, conversation_id, surface, kind, status,
            provider, model, model_calls, tool_calls,
            input_tokens, output_tokens, total_tokens, occurred_at
        ) VALUES (
            v_workspace_id,
            v_bound_agent_id,
            v_conversation_id,
            'widget',
            'generation',
            CASE WHEN i % 23 = 0 THEN 'failed' ELSE 'completed' END,
            'demo',
            'local-fixture-expanded',
            CASE WHEN i % 23 = 0 THEN 1 ELSE 2 END,
            i % 3,
            620 + i * 4,
            CASE WHEN i % 23 = 0 THEN 0 ELSE 110 + (i % 45) END,
            CASE WHEN i % 23 = 0 THEN 620 + i * 4 ELSE 730 + i * 4 + (i % 45) END,
            v_now - make_interval(days => i % 90, hours => i % 24)
        );
    END LOOP;

    WITH demo_products AS (
        SELECT id, row_number() OVER (ORDER BY id) AS rn
          FROM products
         WHERE workspace_id = v_workspace_id
           AND product_sku LIKE 'MM-DEMO-%'
    ),
    demo_messages AS (
        SELECT
            m.id AS message_id,
            c.id AS conversation_id,
            c.agent_id,
            row_number() OVER (ORDER BY m.id) AS rn,
            m.completed_at
          FROM conversation_messages m
          JOIN conversations c
            ON c.workspace_id = m.workspace_id AND c.id = m.conversation_id
         WHERE m.workspace_id = v_workspace_id
           AND c.public_id::text LIKE '76000000-0000-4000-8000-%'
           AND m.actor IN ('assistant', 'human')
    )
    INSERT INTO analytics_events (
        workspace_id, agent_id, conversation_id, message_id,
        product_id, channel, event_type, occurred_at
    )
    SELECT
        v_workspace_id,
        dm.agent_id,
        dm.conversation_id,
        dm.message_id,
        dp.id,
        'web',
        'product_impression',
        dm.completed_at
      FROM demo_messages dm
      JOIN demo_products dp ON dp.rn = ((dm.rn - 1) % 32) + 1;

    SELECT m.id
      INTO STRICT v_first_message_id
      FROM conversation_messages m
      JOIN conversations c
        ON c.workspace_id = m.workspace_id AND c.id = m.conversation_id
     WHERE m.workspace_id = v_workspace_id
       AND c.public_id = '76000000-0000-4000-8000-000000000001'::uuid
       AND m.actor = 'assistant'
     ORDER BY m.id
     LIMIT 1;

    SELECT id
      INTO STRICT v_second_product_id
      FROM products
     WHERE workspace_id = v_workspace_id
       AND product_sku LIKE 'MM-DEMO-%'
     ORDER BY id
     OFFSET 1
     LIMIT 1;

    INSERT INTO analytics_events (
        workspace_id, agent_id, conversation_id, message_id,
        product_id, channel, event_type, occurred_at
    )
    SELECT
        v_workspace_id,
        c.agent_id,
        c.id,
        v_first_message_id,
        v_second_product_id,
        'web',
        'product_impression',
        m.completed_at
      FROM conversation_messages m
      JOIN conversations c
        ON c.workspace_id = m.workspace_id AND c.id = m.conversation_id
     WHERE m.workspace_id = v_workspace_id
       AND m.id = v_first_message_id;

    UPDATE workspace_usage_months
       SET generated_turns = generated_turns + 97,
           updated_at = v_now
     WHERE workspace_id = v_workspace_id
       AND period_started_at = date_trunc('month', v_now);
END
$demo$;
"""


_DOWNGRADE_SQL = f"""
DO $demo$
DECLARE
    v_workspace_id uuid := '{DEMO_WORKSPACE_ID}'::uuid;
BEGIN
    DELETE FROM analytics_events ae
     USING conversation_messages m, conversations c
     WHERE ae.workspace_id = v_workspace_id
       AND ae.workspace_id = m.workspace_id
       AND ae.message_id = m.id
       AND m.workspace_id = c.workspace_id
       AND m.conversation_id = c.id
       AND c.public_id::text LIKE '76000000-0000-4000-8000-%';

    DELETE FROM usage_events
     WHERE workspace_id = v_workspace_id
       AND model = 'local-fixture-expanded';
    DELETE FROM leads
     WHERE workspace_id = v_workspace_id
       AND idempotency_key LIKE 'expanded-demo-lead-%';
    DELETE FROM conversation_audit_events cae
     USING conversations c
     WHERE cae.workspace_id = v_workspace_id
       AND cae.workspace_id = c.workspace_id
       AND cae.conversation_id = c.id
       AND c.public_id::text LIKE '76000000-0000-4000-8000-%';
    DELETE FROM conversation_tag_links ctl
     USING conversations c
     WHERE ctl.workspace_id = v_workspace_id
       AND ctl.workspace_id = c.workspace_id
       AND ctl.conversation_id = c.id
       AND c.public_id::text LIKE '76000000-0000-4000-8000-%';
    DELETE FROM conversation_notes cn
     USING conversations c
     WHERE cn.workspace_id = v_workspace_id
       AND cn.workspace_id = c.workspace_id
       AND cn.conversation_id = c.id
       AND c.public_id::text LIKE '76000000-0000-4000-8000-%';
    DELETE FROM conversation_read_states crs
     USING conversations c
     WHERE crs.workspace_id = v_workspace_id
       AND crs.workspace_id = c.workspace_id
       AND crs.conversation_id = c.id
       AND c.public_id::text LIKE '76000000-0000-4000-8000-%';
    DELETE FROM conversation_messages m
     USING conversations c
     WHERE m.workspace_id = v_workspace_id
       AND m.workspace_id = c.workspace_id
       AND m.conversation_id = c.id
       AND c.public_id::text LIKE '76000000-0000-4000-8000-%';
    DELETE FROM conversations
     WHERE workspace_id = v_workspace_id
       AND public_id::text LIKE '76000000-0000-4000-8000-%';
    DELETE FROM widget_sessions
     WHERE workspace_id = v_workspace_id
       AND normalized_origin LIKE 'http://localhost:310%';

    DELETE FROM contact_audit_events cae
     USING contacts c
     WHERE cae.workspace_id = v_workspace_id
       AND cae.workspace_id = c.workspace_id
       AND cae.contact_id = c.id
       AND c.public_id::text LIKE '75000000-0000-4000-8000-%';
    DELETE FROM contact_tag_links ctl
     USING contacts c
     WHERE ctl.workspace_id = v_workspace_id
       AND ctl.workspace_id = c.workspace_id
       AND ctl.contact_id = c.id
       AND c.public_id::text LIKE '75000000-0000-4000-8000-%';
    DELETE FROM contact_notes cn
     USING contacts c
     WHERE cn.workspace_id = v_workspace_id
       AND cn.workspace_id = c.workspace_id
       AND cn.contact_id = c.id
       AND c.public_id::text LIKE '75000000-0000-4000-8000-%';
    DELETE FROM contact_identities ci
     USING contacts c
     WHERE ci.workspace_id = v_workspace_id
       AND ci.workspace_id = c.workspace_id
       AND ci.contact_id = c.id
       AND c.public_id::text LIKE '75000000-0000-4000-8000-%';
    DELETE FROM contacts
     WHERE workspace_id = v_workspace_id
       AND public_id::text LIKE '75000000-0000-4000-8000-%';
    DELETE FROM workspace_tags
     WHERE workspace_id = v_workspace_id
       AND normalized_name LIKE 'demo-%';

    DELETE FROM widget_domains wd
     USING channel_connections cc
     WHERE wd.workspace_id = v_workspace_id
       AND wd.workspace_id = cc.workspace_id
       AND wd.channel_id = cc.id
       AND cc.display_name LIKE 'Demo: Website chuyên đề %';
    DELETE FROM website_channel_configs wc
     USING channel_connections cc
     WHERE wc.workspace_id = v_workspace_id
       AND wc.workspace_id = cc.workspace_id
       AND wc.connection_id = cc.id
       AND cc.display_name LIKE 'Demo: Website chuyên đề %';
    DELETE FROM channel_agent_bindings cab
     USING channel_connections cc
     WHERE cab.workspace_id = v_workspace_id
       AND cab.workspace_id = cc.workspace_id
       AND cab.connection_id = cc.id
       AND cc.display_name LIKE 'Demo: Website chuyên đề %';
    DELETE FROM channel_connections
     WHERE workspace_id = v_workspace_id
       AND display_name LIKE 'Demo: Website chuyên đề %';

    DELETE FROM agent_knowledge_bases akb
     USING agents a
     WHERE akb.workspace_id = v_workspace_id
       AND akb.workspace_id = a.workspace_id
       AND akb.agent_id = a.id
       AND a.public_id::text LIKE '74000000-0000-4000-8000-%';
    DELETE FROM agent_locations al
     USING agents a
     WHERE al.workspace_id = v_workspace_id
       AND al.workspace_id = a.workspace_id
       AND al.agent_id = a.id
       AND a.public_id::text LIKE '74000000-0000-4000-8000-%';
    DELETE FROM agent_catalog_collections acc
     USING agents a
     WHERE acc.workspace_id = v_workspace_id
       AND acc.workspace_id = a.workspace_id
       AND acc.agent_id = a.id
       AND a.public_id::text LIKE '74000000-0000-4000-8000-%';
    DELETE FROM agent_revisions ar
     USING agents a
     WHERE ar.workspace_id = v_workspace_id
       AND ar.workspace_id = a.workspace_id
       AND ar.agent_id = a.id
       AND a.public_id::text LIKE '74000000-0000-4000-8000-%';
    DELETE FROM agents
     WHERE workspace_id = v_workspace_id
       AND public_id::text LIKE '74000000-0000-4000-8000-%';

    DELETE FROM knowledge_document_versions kv
     USING knowledge_documents kd, knowledge_bases kb
     WHERE kv.workspace_id = v_workspace_id
       AND kv.workspace_id = kd.workspace_id
       AND kv.document_id = kd.id
       AND kd.workspace_id = kb.workspace_id
       AND kd.knowledge_base_id = kb.id
       AND kb.name LIKE 'Demo: %';
    DELETE FROM knowledge_documents kd
     USING knowledge_bases kb
     WHERE kd.workspace_id = v_workspace_id
       AND kd.workspace_id = kb.workspace_id
       AND kd.knowledge_base_id = kb.id
       AND kb.name LIKE 'Demo: %';
    DELETE FROM knowledge_bases
     WHERE workspace_id = v_workspace_id
       AND name LIKE 'Demo: %';

    DELETE FROM variant_option_values vov
     USING product_variants pv, products p
     WHERE vov.workspace_id = v_workspace_id
       AND vov.workspace_id = pv.workspace_id
       AND vov.variant_id = pv.id
       AND pv.workspace_id = p.workspace_id
       AND pv.product_id = p.id
       AND p.product_sku LIKE 'MM-DEMO-%';
    DELETE FROM product_option_values pov
     USING product_option_definitions pod, products p
     WHERE pov.workspace_id = v_workspace_id
       AND pov.workspace_id = pod.workspace_id
       AND pov.option_definition_id = pod.id
       AND pod.workspace_id = p.workspace_id
       AND pod.product_id = p.id
       AND p.product_sku LIKE 'MM-DEMO-%';
    DELETE FROM product_option_definitions pod
     USING products p
     WHERE pod.workspace_id = v_workspace_id
       AND pod.workspace_id = p.workspace_id
       AND pod.product_id = p.id
       AND p.product_sku LIKE 'MM-DEMO-%';
    DELETE FROM inventory_levels il
     USING product_variants pv, products p
     WHERE il.workspace_id = v_workspace_id
       AND il.workspace_id = pv.workspace_id
       AND il.variant_id = pv.id
       AND pv.workspace_id = p.workspace_id
       AND pv.product_id = p.id
       AND p.product_sku LIKE 'MM-DEMO-%';
    DELETE FROM location_variants lv
     USING product_variants pv, products p
     WHERE lv.workspace_id = v_workspace_id
       AND lv.workspace_id = pv.workspace_id
       AND lv.variant_id = pv.id
       AND pv.workspace_id = p.workspace_id
       AND pv.product_id = p.id
       AND p.product_sku LIKE 'MM-DEMO-%';
    DELETE FROM size_guides sg
     USING products p
     WHERE sg.workspace_id = v_workspace_id
       AND sg.workspace_id = p.workspace_id
       AND sg.product_id = p.id
       AND p.product_sku LIKE 'MM-DEMO-%';
    DELETE FROM catalog_collection_products ccp
     USING products p
     WHERE ccp.workspace_id = v_workspace_id
       AND ccp.workspace_id = p.workspace_id
       AND ccp.product_id = p.id
       AND p.product_sku LIKE 'MM-DEMO-%';
    DELETE FROM product_variants pv
     USING products p
     WHERE pv.workspace_id = v_workspace_id
       AND pv.workspace_id = p.workspace_id
       AND pv.product_id = p.id
       AND p.product_sku LIKE 'MM-DEMO-%';
    DELETE FROM products
     WHERE workspace_id = v_workspace_id
       AND product_sku LIKE 'MM-DEMO-%';
    DELETE FROM catalog_collections
     WHERE workspace_id = v_workspace_id
       AND name LIKE 'Demo: %';
    DELETE FROM locations
     WHERE workspace_id = v_workspace_id
       AND code LIKE 'DEMO-%';

    UPDATE workspace_usage_months
       SET generated_turns = greatest(generated_turns - 97, 0),
           updated_at = now()
     WHERE workspace_id = v_workspace_id
       AND period_started_at = date_trunc('month', now());
END
$demo$;
"""
