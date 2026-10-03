"use client";

import { LoaderCircle, Sparkles, Store } from "lucide-react";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { FeedbackBanner } from "@/components/feedback-banner";
import { api } from "@/lib/api";
import { toUiError, type UiFeedback } from "@/lib/errors";

function suggestSlug(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/đ/g, "d")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 63);
}

export function CreateShopForm() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugEdited, setSlugEdited] = useState(false);
  const [formFeedback, setFormFeedback] = useState<UiFeedback>();
  const [checking, setChecking] = useState(true);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    api.getMe().then((me) => {
      if (me.workspaces[0]) router.replace(`/app/${encodeURIComponent(me.workspaces[0].slug)}/overview`);
      else setChecking(false);
    }).catch(() => router.replace("/login?next=/onboarding/create-shop"));
  }, [router]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setFormFeedback(undefined);
    try {
      const workspace = await api.createWorkspace({ display_name: name, slug });
      router.replace(`/app/${encodeURIComponent(workspace.slug)}/overview`);
      router.refresh();
    } catch (caught) {
      setFormFeedback(toUiError(caught, {
        operation: "workspaces.create",
        fallback: "Không thể tạo cửa hàng. Thông tin bạn đã nhập vẫn được giữ lại.",
      }));
    } finally {
      setPending(false);
    }
  }

  if (checking) return <main className="center-state">Đang kiểm tra tài khoản…</main>;
  return (
    <main className="onboarding-page">
      <section className="onboarding-card">
        <span className="brand-mark"><Sparkles aria-hidden="true" size={21} /></span>
        <div><p className="eyebrow">Bước đầu tiên</p><h1>Tạo cửa hàng của bạn</h1><p>Mỗi cửa hàng là một workspace riêng với dữ liệu và quyền truy cập độc lập.</p></div>
        <form onSubmit={submit}>
          <label htmlFor="shop-name">
            Tên cửa hàng
            <input
              autoFocus
              id="shop-name"
              maxLength={120}
              minLength={2}
              onChange={(event) => { setName(event.target.value); if (!slugEdited) setSlug(suggestSlug(event.target.value)); }}
              required
              value={name}
            />
          </label>
          <label htmlFor="shop-slug">
            Đường dẫn cửa hàng
            <span className="slug-field"><span>agenthub.local/app/</span><input id="shop-slug" maxLength={63} minLength={2} onChange={(event) => { setSlugEdited(true); setSlug(suggestSlug(event.target.value)); }} pattern="[a-z0-9]+(?:-[a-z0-9]+)*" required value={slug} /></span>
            <small>Chỉ gồm chữ thường, số và dấu gạch ngang.</small>
          </label>
          {formFeedback && <FeedbackBanner feedback={formFeedback} />}
          <button className="primary-button" disabled={pending} type="submit">
            {pending ? <LoaderCircle className="spinner" aria-hidden="true" size={18} /> : <Store aria-hidden="true" size={18} />}
            {pending ? "Đang tạo…" : "Tạo cửa hàng"}
          </button>
        </form>
      </section>
    </main>
  );
}
