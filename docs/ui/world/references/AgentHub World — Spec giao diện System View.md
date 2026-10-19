# AgentHub World — Spec giao diện System View

*Dành cho AI/dev triển khai · 19/10/2026 · Prototype tham chiếu hình thức: https://claude.ai/artifact/EsNSHxtZLKqofQuiNrJt3a (SVG cố định 1440×1000; chỉ để xem hình, KHÔNG sao chép cách dựng tọa độ tuyệt đối — bản thật phải là DOM + CSS Grid + SVG nhỏ, responsive).*

## 1. Mục tiêu và phạm vi

World là màn hình tổng quan mặc định của một workspace. Người dùng nhìn một lần phải trả lời được: có bao nhiêu Agent, Agent nào đang bận, kênh nào vào Agent nào, Agent biết gì, làm được gì, được dùng dữ liệu kinh doanh nào, chỗ nào đang lỗi.

World là lớp hiểu hệ thống và điều hướng. Không nhét CRUD vào đây.

**Trong phạm vi v1:** System View trên desktop, tablet, mobile (recompose, không thu nhỏ); highlight quan hệ khi hover/focus; điều hướng sang màn chuyên dụng; trạng thái loading/empty/error.

**Ngoài phạm vi:** Agent View chi tiết, luồng tạo/cấu hình Agent, CRUD catalog/địa điểm, kênh realtime mới, 3D, kéo thả, pan/zoom, minimap, graph/node editor.

## 2. Nguyên tắc bắt buộc

1. **Không có connector line** giữa các object. Quan hệ thể hiện bằng vị trí, gắn kèm (attachment), nhóm, trạng thái, và highlight khi hover/focus.
2. **Mỗi thông tin xuất hiện một lần.** Số hội thoại đang chạy chỉ nằm trên Agent; lỗi chỉ nằm đúng nơi xảy ra. Không có banner lặp lại lỗi đã hiện trên object (trừ lỗi toàn cục thật sự, ví dụ không tải được snapshot).
3. **Không dữ liệu giả.** Rỗng thì hiện rỗng. Mock chỉ bật bằng cờ cấu hình và phải có badge 'Dữ liệu minh họa'.
4. **Bố cục ổn định để hình thành spatial memory.** Thứ tự Agent theo `position` (người dùng đặt; mặc định created\_at). Không bao giờ sắp lại theo mức bận hay trạng thái.
5. **Mỗi domain có ngữ pháp hình riêng** (mục 5). Không dùng một component hình chữ nhật cho mọi thứ; không có card đóng khung.
6. **Ngôn ngữ việc làm, không ngôn ngữ kỹ thuật.** UI nói 'Đặt lịch', 'Tạo đơn', 'Gửi CV'; không nói tool, schema, webhook, capability registry.
7. **Không animation liên tục.** Chỉ transition ngắn (250ms) khi highlight/recompose.
8. **Không hardcode ngành.** Nhãn loại mục, bộ sưu tập, địa điểm lấy từ dữ liệu.

## 3. Mô hình khái niệm UI phải phản ánh

- **Workspace** là ranh giới dữ liệu và quyền. Một người dùng thuộc nhiều workspace; có bộ chuyển workspace ở header.
- **Agent** có: danh tính, trạng thái (draft | published | paused), kênh, tri thức, việc làm được, phạm vi dữ liệu kinh doanh, hội thoại. Agent làm nhiều việc là bình thường.
- **Kênh**: một kết nối kênh (một Fanpage, một Zalo OA, một domain widget) thuộc workspace và gán cho đúng một Agent trả lời. Vì vậy cổng kênh hiển thị gắn ngay trên từng Agent.
- **Tri thức**: nguồn thuộc workspace, gán cho nhiều Agent, có đối tượng public | internal.
- **Catalog**: một Catalog mỗi workspace. Mục có `kind`: v1 chỉ goods (hàng hóa) và service (dịch vụ). Bộ sưu tập là nhóm tự do. Biến thể/tùy chọn là generic option, không chỉ màu/size.
- **Địa điểm**: một thực thể có nhiều vai trò (phục vụ khách, giữ hàng). Tồn kho là quan hệ biến thể–địa điểm. **stock = null nghĩa là chưa biết/không quản lý; stock = 0 nghĩa là hết hàng. Không được đánh đồng.**
- **Phạm vi dữ liệu của Agent** = quyền (permission) + bộ lọc bộ sưu tập + bộ lọc địa điểm (mode all | selected). Agent không vượt quyền workspace.
- Agent không có quan hệ trực tiếp với nhau. Chỉ chia sẻ tài nguyên (Catalog, địa điểm, nguồn tri thức); sự chia sẻ chỉ hiện qua highlight, không qua đường nối.

## 4. Bố cục

### 4.1 Desktop ≥ 1280px

**Header (cao \~100px):**

- Trái: tiêu đề 'AgentHub World'; dưới là **Workspace switcher** dạng pill trắng viền (avatar chữ cái, tên, caret, meta '10 Agent · 4 địa điểm').
- Phải: segmented control 'Hệ thống | Agent' ('Agent' chỉ bật khi có Agent đang được chọn; bấm là điều hướng sang Agent View). Badge 'Dữ liệu minh họa' khi bật mock.

**Body:** CSS Grid hai vùng, gap 30px:

- `AgentField` (co giãn, tối thiểu 1000px). Nền chấm (lưới chấm 22px, chấm 1.1px) bo 26px, padding 20px.
- `BusinessRail` (rộng 290px, sticky top 24px). Nền xanh nhạt có lưới chấm, bo 26px.

**AgentField:** grid cột `repeat(N, minmax(340px, 1fr))`, N = số cột vừa chiều rộng, giới hạn 2–4 (mặc định 3 ở 1440px). Mỗi ô Agent có chiều cao cố định 200px, khoảng cách hàng 15px. **Thẳng hàng tuyệt đối, không so le.** Điền theo hàng, trái sang phải, trên xuống dưới, theo `position`. Ô cuối là ô ghost 'Tạo Agent mới' (vòng nét đứt, dấu +, dòng 'Thêm một nhân viên AI'); đây là hành động, không phải dữ liệu.

### 4.2 Tablet 768–1279px

- AgentField 2 cột.
- BusinessRail chuyển xuống dưới AgentField, toàn chiều rộng, các khối (Catalog | Địa điểm | Giao dịch) xếp 2–3 cột.
- Không có hover: chạm lần đầu vào Agent = focus và highlight quan hệ; nút 'Mở' nhỏ xuất hiện trên Agent đang focus để điều hướng. Chạm ra ngoài để bỏ focus.

### 4.3 Mobile < 768px

**Recompose thành các section dọc, không phải desktop thu nhỏ:**

1. Header gọn: workspace switcher.
2. Danh sách Agent một cột. Mỗi Agent: hàng 1 = ring + tên/vai trò/hoạt động; hàng 2 = cổng kênh (xếp ngang, cuộn nếu nhiều); hàng 3 = bong bóng tri thức; hàng 4 = chip việc làm được (tối đa 2 dòng, còn lại '+N'); hàng 5 = quyền + bộ lọc phạm vi.
3. Section 'Dữ liệu kinh doanh' gập/mở được: Catalog, Địa điểm, Giao dịch với đúng ngữ pháp hình như desktop.
4. Chạm Agent = focus. Khi có focus, thanh nhỏ cố định phía dưới 'Đang xem phạm vi: {Agent}' kèm nút 'Mở Agent' và 'Bỏ chọn'; các mục dữ liệu kinh doanh ngoài phạm vi bị mờ.

## 5. Ngữ pháp hình ảnh theo domain

| Domain | Hình | Trạng thái | Hoạt động |
| --- | --- | --- | --- |
| Agent | Pad tròn + ring tải + core màu + glyph | màu core theo kind; chấm trạng thái; draft = nét đứt, mờ | độ dài các cung ring (đang chat / chờ / cần nhân viên) |
| Kênh | Thẻ hình mũi tên chỉ vào Agent, gắn bên trái Agent | lỗi = viền đỏ nét đứt + chữ 'mất kết nối' | không |
| Tri thức | Bong bóng 'nghĩ' phía trên Agent, glyph chồng lớp | đỏ = lỗi, vàng = đang xử lý, xám nét đứt = rỗng | không |
| Việc làm được | Chip viên thuốc dưới Agent | đỏ nhạt = cần cài đặt/lỗi, kèm lý do ngắn | không |
| Phạm vi dữ liệu | Pill đen (quyền) + pill viền (bộ lọc) ở hàng cuối Agent | 'mọi …' khi lấy hết | không |
| Catalog | Nhóm theo kind; mỗi bộ sưu tập là hộp có chùm chấm (mục) + vạch (biến thể) | chấm vàng = tồn thấp | không |
| Địa điểm | Ghim + nhãn vai trò + thanh tồn | đỏ = 0 (hết); khung nét đứt = null (chưa theo dõi) | không |
| Hội thoại | Không vẽ từng hội thoại; gộp thành cung ring. Chỉ hiện dòng chữ cho hội thoại cần người thật | đỏ | số lượng |

## 6. Agent Unit — giải phẫu chi tiết

Hộp 340×200, không viền, không nền. Gốc tọa độ (0,0) = tâm ring. Có thể dựng bằng CSS Grid/absolute trong hộp; ring, glyph, mũi tên là SVG nội tuyến.

| Phần | Quy tắc |
| --- | --- |
| Pad | Vòng tròn r=50, tô màu kind 9% (idle/draft 4%). |
| Ring | r = 28 + min(total, 35) × 0.4 (px), với total = active + waiting + needs\_human. Nét 5px. Track #DDE1E8 (idle/draft: #B8BFCC nét đứt 3/5). Cung bắt đầu từ 12 giờ, chiều kim đồng hồ, thứ tự: active (màu kind) → waiting (vàng) → needs\_human (đỏ). Độ dài mỗi cung = count / 40 × chu vi; tổng không vượt 100%. Hằng số 40 dùng chung mọi Agent để so sánh tải. |
| Core | r = ring − 8, tô màu kind (draft 55% mờ), glyph trắng nét 2.2px theo kind: túi (sales), lịch (service), bong bóng chat (support/lead), hình thoi (internal), dấu + (draft). |
| Chấm trạng thái | Góc 45° trên-phải ring, r=5, viền nền 2px. Xanh = published và đang có hoạt động; xám = rảnh/nháp/tạm dừng. |
| Khối chữ | Bắt đầu x=+58. Tên 15px/700. Vai trò 12px. Hoạt động 11px: 'N đang chat · M chờ'; rảnh: 'Rảnh · chưa có hội thoại'; nháp: 'Chưa xuất bản'. Dòng đỏ 11px/600 'N cần nhân viên' chỉ khi N>0. |
| Cổng kênh | Cột trái, canh phải tại x=−52, xếp dọc quanh tâm, mỗi thẻ cao 18, cách 4, rộng = chữ + 22. Thường: viền #14181F. Lỗi: viền đỏ nét đứt, chữ đỏ, dòng 'mất kết nối' đỏ bên dưới. Không có kênh: thẻ xám nét đứt 'Chưa có kênh'. |
| Bong bóng tri thức | Capsule cao 24 tại y=−82, x=−44, glyph chồng lớp + chữ 11px/600; một chấm tròn nhỏ nối với ring. Mặc định chỉ '{n} nguồn'. Chỉ thêm chi tiết khi có vấn đề ('64 nguồn · FAQ lỗi 3 ngày') hoặc nội bộ ('126 tài liệu · nội bộ'). Màu viền: đỏ lỗi, vàng đang xử lý, xám nét đứt rỗng. |
| Chip việc làm được | y=+60, một hàng, tối đa 270px. Thứ tự: chip có vấn đề trước. Chip vượt giới hạn gộp 'N+' — bấm mở popover liệt kê đủ. Chip lỗi: nền #FDF0EF, viền đỏ, chữ #B3261E, nhãn kèm lý do ngắn ('Thanh toán · chưa nối'). |
| Hàng phạm vi | y=+94, cao 19. Pill đen = quyền ('tạo đơn', 'chỉ đọc'). Pill viền = bộ lọc: bộ sưu tập ('mọi bộ sưu tập' khi mode=all; tên khi chọn đúng 1; 'N bộ sưu tập' khi nhiều) và địa điểm (tương tự). Agent không dùng dữ liệu kinh doanh: một dòng xám 'Không dùng dữ liệu kinh doanh'. |

**Tương tác trên Unit:** toàn bộ Unit focus được bằng bàn phím và bấm để vào Agent View. Phần tử con có đích riêng: cổng kênh → cài đặt kênh; bong bóng → tri thức; chip → việc làm được; pill phạm vi → tab dữ liệu của Agent. Bấm phần tử con không kích hoạt điều hướng của Unit (stopPropagation).

**Chế độ compact** (khi có >12 Agent): Unit thấp hơn, ẩn hàng phạm vi và chip (thay bằng 'N việc'), cổng kênh thu thành ký hiệu. >30 Agent: ảo hóa danh sách và thêm ô tìm kiếm (lọc hiển thị, không đổi vị trí).

## 7. Business Rail

Từ trên xuống:

1. **Đầu rail:** nhãn nhỏ 'DỮ LIỆU KINH DOANH'; tiêu đề 'Catalog' 17px/700; bên phải các chấm màu của Agent đang dùng (tối đa 8, rồi '+N'); dòng meta '{mục} mục · {biến thể} biến thể'.
2. **Nhóm theo kind:** 'DỊCH VỤ' (ghi chú: lịch trống · không tính tồn) và 'HÀNG HÓA' (ghi chú: tồn kho theo địa điểm). Mỗi bộ sưu tập là một hộp: tên · số lượng kèm đơn vị theo kind (dịch vụ/gói/khóa/sản phẩm), một hàng chấm (tối đa 22 chấm/hàng; số chấm quy đổi theo tỷ lệ với bộ sưu tập lớn nhất, tối thiểu 6), vạch biến thể (độ dài theo tỷ lệ, tối đa 230px), chấm vàng = tồn thấp. Mật độ: hiện tối đa 4 bộ sưu tập mỗi nhóm theo số mục giảm dần, phần còn lại là '+N bộ sưu tập' (bấm sang Catalog). **Không bao giờ render từng mục.**
3. **Địa điểm:** mỗi địa điểm hai dòng. Dòng 1: ghim + tên + nhãn vai trò ('phục vụ', 'giữ hàng'). Dòng 2: thanh tồn — còn hàng: thanh đen; =0: đoạn đỏ ngắn + 'hết N SKU'; null: khung nét đứt 'chưa theo dõi tồn'; địa điểm không giữ hàng: không có thanh. Tối đa 5, rồi '+N'. Ghim đỏ khi địa điểm có hàng hết.
4. **Giao dịch:** các số nhỏ — Lịch hẹn hôm nay; Đơn hàng hôm nay · chờ xử lý; Khách hàng tổng. Bấm sang màn tương ứng. Ẩn mục nào workspace chưa dùng.

**Progressive disclosure:** workspace chưa có catalog → rail chỉ hiện empty state 'Chưa có dữ liệu kinh doanh' + nút 'Thêm sản phẩm hoặc dịch vụ'. Chưa có địa điểm → ẩn mục Địa điểm.

## 8. Quan hệ và highlight (thay cho đường nối)

Trạng thái `focusAgentId` (hover trên desktop, focus bàn phím, chạm trên touch). Mỗi phần tử có tập `relatedAgentIds`. Khi có focus: phần tử thuộc tập giữ opacity 1, còn lại 0.2 (transition 250ms). Hết focus: về 1.

| Phần tử | Tập liên quan |
| --- | --- |
| Agent Unit | chính nó |
| Đầu Catalog, Giao dịch | mọi Agent có phạm vi dữ liệu kinh doanh |
| Bộ sưu tập | Agent có filter mode=all, hoặc danh sách chọn chứa bộ sưu tập đó |
| Địa điểm | tương tự theo filter địa điểm |

Focus vào Agent không dùng dữ liệu kinh doanh → toàn rail mờ. Triển khai bằng state React + thuộc tính `data-dim`, **không phụ thuộc CSS :has**. Hàm tính tập liên quan phải thuần và có unit test.

## 9. Dữ liệu (hợp đồng tối thiểu)

Một snapshot cho mỗi workspace (tên endpoint do backend quyết định, ví dụ `GET /workspaces/{id}/world`). Frontend không tự ghép nhiều API nếu có thể tránh.

| Nhóm | Trường |
| --- | --- |
| workspace | id, name, avatar\_text, meta (agent\_count, location\_count), thuộc về các workspace khác của user (cho switcher) |
| agent\[\] | id, name, role\_label, kind (sales/service/support\_lead/internal; thiếu → trung tính), status (draft/published/paused), position |
| agent.conversations | active, waiting, needs\_human (số nguyên) |
| agent.knowledge | source\_count, audience (public/internal), issues\[\] {severity: error/processing, short\_text} |
| agent.channels\[\] | type, label, status (ok/error) |
| agent.abilities\[\] | key, label, state (ready/needs\_setup/error), issue\_text |
| agent.business\_scope | null nếu không dùng; hoặc permission\_label, collections\_filter {mode: all/selected, ids\[\]}, locations\_filter {mode, ids\[\]} |
| catalog | item\_count, variant\_count, groups\[\] {kind, note, collections\[\] {id, name, unit\_label, item\_count, variant\_count, low\_stock\_count}} |
| locations\[\] | id, name, roles\[\] (serve\_customers, hold\_stock), stock {state: ok/zero/unknown/none, ratio, zero\_sku\_count} |
| transactions | appointments\_today, orders\_today, orders\_pending, customers\_total (trường vắng = ẩn) |

Quy tắc: **null và 0 là hai giá trị khác nhau**, giữ nguyên từ API đến UI. Trường tính phía client: total = active + waiting + needs\_human; bán kính ring; tập quan hệ.

**Làm mới:** tải ban đầu + làm mới định kỳ 15–30 giây khi tab đang hiển thị. Không phụ thuộc kênh realtime (SSE hiện tại chưa quyết định kiến trúc handover). Khi dữ liệu cũ hơn 2 phút hiện chỉ báo nhỏ 'cập nhật lúc HH:mm' cạnh workspace switcher.

## 10. Trạng thái giao diện

| Trạng thái | Hành vi |
| --- | --- |
| Loading | Khung vòng xám cho Unit và Rail; không số giả |
| 0 Agent | Ô ghost lớn 'Tạo Agent đầu tiên' + 2 dòng giải thích |
| Lỗi tải snapshot | Một banner toàn cục duy nhất, nói rõ nguyên nhân, nút 'Thử lại' |
| Lỗi từng phần | Section lỗi hiện lỗi tại chỗ, không chặn phần còn lại |
| Draft | Ring nét đứt, core mờ, 'Chưa xuất bản', không chấm xanh |
| Paused | Ring xám, nhãn 'Tạm dừng' |
| Kênh lỗi / tri thức lỗi / việc cần cài đặt | Đánh dấu tại đúng cổng/bong bóng/chip |

## 11. Design tokens

| Token | Giá trị |
| --- | --- |
| nền trang | #F4F5F2 |
| nền field (chấm) | #ECEEE8 nền, chấm #CDD2C8 |
| nền rail | #E9EEFB; chấm #CBD3EC; hộp #F7F9FE viền #CBD3EC |
| chữ chính | #14181F |
| chữ phụ | #4B5563 (12px), #5B6472 (11px) |
| chữ mờ | #8A93A3 |
| viền/track | #B8BFCC; track ring #DDE1E8 |
| kind | sales #2F5BEA; service #7A4FD6; support/lead #0E8A8C; internal #4B5563; draft #9AA3B2 |
| đang chờ | #E0A100 (chữ trên nền sáng dùng #7A5600) |
| nguy hiểm | #C62828 (chữ #B3261E, nền #FDF0EF) |
| thành công | #1E9E5A |
| font | Be Vietnam Pro 400/600/700 (hỗ trợ tiếng Việt), fallback sans-serif |
| cỡ chữ | tiêu đề 22/700; tên Agent 15/700; vai trò 12; meta và chip 11/600; nhãn vùng 11/600 hoa, letter-spacing 1.4px |
| bo góc | vùng 26px; chip/pill tròn hết cỡ; hộp bộ sưu tập 10px |

Không dùng glow, neon, nền không gian, 3D giả, thẻ nổi.

## 12. Truy cập, i18n, chuyển động

- Tab order theo thứ tự đọc: switcher → Agent theo `position` → Rail.
- Focus ring rõ trên Unit; Enter/Space mở Agent. Phần tử con có `aria-label` đầy đủ ('Kênh Facebook, mất kết nối').
- Màu không phải tín hiệu duy nhất: mọi lỗi/cảnh báo có chữ.
- Tương phản chữ AA; chữ vàng trên nền sáng phải dùng #7A5600.
- Mỗi Unit có tóm tắt cho trình đọc màn hình: tên, trạng thái, số hội thoại, vấn đề.
- Mọi chuỗi UI qua lớp i18n (mặc định vi); không ghép chuỗi bằng nối.
- `prefers-reduced-motion`: tắt transition highlight và animation ring lúc tải.

## 13. Kiến trúc frontend

- Next.js (App Router) + TypeScript theo codebase hiện có; **tái sử dụng** design system, i18n, data-fetching đã có; không thêm thư viện graph/canvas/WebGL.
- Route: `/w/[workspaceSlug]/world`.
- Cây component gợi ý: WorldPage → WorkspaceSwitcher, ViewToggle, AgentField (AgentUnit → AgentRing, ChannelGates, MemoryBubble, AbilityChips, ScopeRow; CreateAgentSlot), BusinessRail (CatalogBlock → ItemKindGroup → CollectionBox; LocationList → LocationRow; TransactionCounts).
- Quan hệ: hook `useWorldFocus` + hàm thuần `relatedAgents(element, snapshot)`; AgentRing nhận số đếm và trả SVG, không nhận style tự do.
- Không đặt logic domain trong component trình bày; không hardcode ngành.

## 14. Điều hướng đích

| Hành động | Đích |
| --- | --- |
| Bấm Agent Unit | Agent View của Agent đó |
| Cổng kênh | cài đặt kênh của Agent |
| Bong bóng tri thức | tri thức của Agent |
| Chip việc làm được / '+N' | việc làm được của Agent |
| Pill phạm vi | dữ liệu kinh doanh của Agent |
| Bộ sưu tập / '+N bộ sưu tập' | Catalog workspace, lọc theo bộ sưu tập |
| Địa điểm | quản lý địa điểm |
| Giao dịch | màn lịch hẹn / đơn hàng / khách hàng tương ứng |
| Ô 'Tạo Agent mới' | luồng tạo Agent |
| Workspace switcher | menu đổi workspace |

## 15. Dữ liệu mẫu (fixtures, workspace 'Lotus Beauty & Spa')

Dùng cho Storybook/test, bật qua cờ mock và hiện badge 'Dữ liệu minh họa'.

| # | Agent | kind | chat / chờ / cần người | Tri thức | Kênh | Việc làm được | Quyền | Bộ sưu tập | Địa điểm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | Tư vấn Spa | service | 14/4/1 | 86 nguồn | Facebook, Zalo, Website | Báo giá, Đặt lịch, Đổi/hủy lịch, Gửi xác nhận | tạo lịch hẹn | Liệu trình, Gói thẻ | Q.1, Q.7, Thủ Đức |
| 1 | Tư vấn Mỹ phẩm | sales | 6/1/0 | 28 nguồn | Website, Zalo | Tìm sản phẩm, Tạo đơn, Kiểm tra tồn kho, Thanh toán (lỗi: chưa nối) | tạo đơn | Mỹ phẩm | Q.1, Q.7, Kho trung tâm |
| 2 | Khóa đào tạo | service | 4/0/0 | 17 nguồn · 1 đang xử lý | Facebook, Website | Gửi lộ trình, Nhận đăng ký, Đặt lịch học thử | nhận đăng ký | Khóa đào tạo | Thủ Đức |
| 3 | Đặt lịch | service | 5/0/0 | 32 nguồn | Zalo, Widget | Kiểm tra lịch trống, Đặt lịch, Đổi/hủy lịch, Nhắc lịch (lỗi gửi) | đặt & đổi lịch | Liệu trình | Q.1, Q.7, Thủ Đức |
| 4 | Lễ tân Q.7 | service | 3/1/0 | 21 nguồn | Widget | Báo giá, Đặt lịch | tạo lịch hẹn | Liệu trình, Gói thẻ | Q.7 |
| 5 | Chăm sóc khách | support\_lead | 22/9/2 | 64 nguồn · FAQ lỗi 3 ngày | Facebook, Zalo, Website | Tra cứu đơn, Đổi trả, Chuyển nhân viên | tạo đổi trả | Liệu trình, Gói thẻ, Mỹ phẩm | tất cả |
| 6 | Tuyển dụng | support\_lead | 2/0/0 | 9 nguồn | Website, Facebook (mất kết nối) | Nhận hồ sơ, Chuyển nhân viên, Hẹn phỏng vấn (lỗi: chưa nối lịch) | không dùng | — | — |
| 7 | Nhượng quyền | support\_lead | 8/2/1 | 21 nguồn | Website | Nhận liên hệ, Gửi tài liệu, Đặt lịch tư vấn, Chuyển nhân viên | không dùng | — | — |
| 8 | Trợ lý nội bộ | internal | 0/0/0 | 126 tài liệu · nội bộ | Playground | Tra tồn kho, Tra cứu đơn, Xem lịch | chỉ đọc | tất cả | tất cả |
| 9 | Agent mới | draft | 0/0/0 | Chưa có tri thức | Chưa có kênh | — | không dùng | — | — |

**Catalog:** 440 mục, 1.126 biến thể. Dịch vụ: Liệu trình (64 dịch vụ, 190 biến thể), Gói thẻ (12 gói, 24), Khóa đào tạo (8 khóa, 32). Hàng hóa: Mỹ phẩm (356 sản phẩm, 880 biến thể, 48 tồn thấp).

**Địa điểm:** Q.1 (phục vụ + giữ hàng, tồn ổn); Q.7 (phục vụ + giữ hàng, hết 6 SKU = 0); Thủ Đức (phục vụ + giữ hàng, tồn = null: chưa theo dõi); Kho trung tâm (chỉ giữ hàng, tồn ổn).

**Giao dịch:** 21 lịch hẹn hôm nay; 38 đơn hôm nay, 3 chờ xử lý; 2.140 khách hàng.

## 16. Tiêu chí nghiệm thu

1. **Đọc nhanh:** với fixtures, một người lạ trả lời đúng trong ≤ 60 giây: có bao nhiêu Agent; Agent nào bận nhất; kênh nào lỗi; tri thức nào lỗi; Agent nào cần nhân viên; địa điểm nào hết hàng; Agent nào dùng Mỹ phẩm; Agent nào không dùng dữ liệu kinh doanh.
2. **Không connector:** không có phần tử nào dùng làm đường nối giữa các object (kiểm tra DOM/SVG); ring, mũi tên cổng, glyph là hình, không phải connector.
3. **Highlight đúng:** test thuần cho `relatedAgents`; hover Agent X làm sáng đúng bộ sưu tập/địa điểm trong phạm vi và làm mờ phần còn lại.
4. **Thẳng hàng:** mọi Unit cùng hàng có cùng tọa độ y (±0.5px), cùng cột có cùng x.
5. **Ổn định:** đổi số hội thoại/trạng thái không làm đổi vị trí Agent.
6. **Một nguồn thông tin:** số hội thoại chỉ xuất hiện trên Unit; lỗi chỉ xuất hiện tại object lỗi.
7. **Responsive:** ở 1440, 1024, 768, 390px không có cuộn ngang; ở 390px bố cục khác desktop (section dọc), không phải bản thu nhỏ.
8. **Trạng thái:** loading, 0 Agent, lỗi toàn cục, lỗi từng phần, draft, paused đều có và đúng mô tả mục 10.
9. **Không dữ liệu giả:** API trả rỗng → UI rỗng; mock chỉ bật bằng cờ và luôn có badge.
10. **Truy cập:** thao tác trọn vẹn bằng bàn phím; axe không lỗi mức nghiêm trọng; tương phản AA.
11. **Hiệu năng:** 12 Agent render lần đầu < 200ms trên máy trung bình; 30 Agent ở chế độ compact cuộn mượt.
12. **Chuyển động:** không animation lặp; `prefers-reduced-motion` được tôn trọng.
13. **Không phụ thuộc thêm:** không thư viện graph/canvas/WebGL mới.

## 17. Ngoài phạm vi (non-goals)

- Kéo/thả, sắp xếp lại bằng tay trên World, pan, zoom, camera, minimap.
- Vẽ từng hội thoại hay từng sản phẩm.
- Form/CRUD trong World.
- Đa Catalog, giá theo chi nhánh/kênh, định tuyến kênh theo ý định, loại mục ngoài goods/service (để sau, khi có use case thật).
- Định tuyến kênh tới nhiều Agent cho một kết nối.
- Kiến trúc realtime/handover mới (chỉ hiển thị số liệu từ snapshot).
- Agent View, luồng tạo/cấu hình/kiểm thử/xuất bản Agent (spec riêng).

## 18. Giả định cần xác nhận với backend

- Có endpoint snapshot tổng hợp, hoặc backend chấp nhận bổ sung trường mục 9; nếu không, frontend cần một lớp tổng hợp ở server, không ghép phía client.
- `kind` của Agent là trường backend cung cấp; nếu chưa có, tạm suy ra từ việc làm được và cho phép ghi đè.
- Thứ tự `position` của Agent đã có hoặc sẽ được thêm.
- Số đếm hội thoại trong snapshot là số tại thời điểm tải; không cam kết realtime.
- Chưa có khái niệm 'tổ chức' trên workspace; switcher chỉ liệt kê workspace mà người dùng là thành viên.
