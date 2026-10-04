export const widgetStyles = `
:host {
  --ah-brand: #0f8f87;
  --ah-text: #10212b;
  --ah-muted: #667680;
  --ah-border: #dce5e7;
  --ah-surface: #ffffff;
  --ah-soft: #f2f8f7;
  position: fixed;
  z-index: 2147483000;
  right: 18px;
  bottom: 18px;
  color: var(--ah-text);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-size: 14px;
  line-height: 1.45;
  color-scheme: light;
}
:host([data-position="left"]) { right: auto; left: 18px; }
* { box-sizing: border-box; }
button, textarea, input { font: inherit; }
button:focus-visible, textarea:focus-visible, input:focus-visible, a:focus-visible, summary:focus-visible {
  outline: 3px solid color-mix(in srgb, var(--ah-brand) 34%, transparent);
  outline-offset: 2px;
}
.ah-launcher {
  width: 58px;
  height: 58px;
  display: grid;
  place-items: center;
  margin-left: auto;
  border: 0;
  border-radius: 19px;
  color: white;
  background: var(--ah-brand);
  box-shadow: 0 14px 34px color-mix(in srgb, var(--ah-brand) 38%, transparent);
  cursor: pointer;
  transition: transform .18s ease, box-shadow .18s ease;
}
:host([data-position="left"]) .ah-launcher { margin-left: 0; margin-right: auto; }
.ah-launcher:hover { transform: translateY(-2px); box-shadow: 0 17px 38px color-mix(in srgb, var(--ah-brand) 44%, transparent); }
.ah-launcher-mark { position: relative; width: 25px; height: 21px; border: 2px solid currentColor; border-radius: 8px; }
.ah-launcher-mark::after { position: absolute; left: 3px; bottom: -5px; width: 7px; height: 7px; border-left: 2px solid currentColor; transform: skew(-24deg); content: ""; }
.ah-launcher-mark::before { position: absolute; inset: 6px 5px auto; height: 2px; border-radius: 9px; background: currentColor; box-shadow: 0 5px 0 currentColor; content: ""; }
.ah-panel {
  width: min(390px, calc(100vw - 24px));
  height: min(650px, calc(100dvh - 96px));
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto auto;
  margin-bottom: 12px;
  overflow: hidden;
  border: 1px solid var(--ah-border);
  border-radius: 20px;
  background: var(--ah-surface);
  box-shadow: 0 24px 72px rgb(18 45 52 / 24%);
  transform-origin: bottom right;
  animation: ah-in .2s ease-out;
}
:host([data-position="left"]) .ah-panel { transform-origin: bottom left; }
.ah-panel[hidden] { display: none; }
@keyframes ah-in { from { opacity: 0; transform: translateY(8px) scale(.98); } }
.ah-header { min-height: 72px; display: flex; align-items: center; gap: 10px; padding: 12px 12px 12px 14px; color: white; background: var(--ah-brand); }
.ah-avatar { width: 39px; height: 39px; flex: 0 0 auto; display: grid; place-items: center; border-radius: 13px; color: var(--ah-brand); background: white; font-size: 17px; font-weight: 800; }
.ah-header-copy { min-width: 0; flex: 1; }
.ah-header-copy strong, .ah-header-copy span { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ah-header-copy strong { font-size: 14px; }
.ah-header-copy span { margin-top: 2px; opacity: .78; font-size: 10px; }
.ah-header-actions { display: flex; gap: 3px; }
.ah-icon-button { width: 34px; height: 34px; display: grid; place-items: center; border: 0; border-radius: 10px; color: inherit; background: transparent; cursor: pointer; }
.ah-icon-button:hover { background: rgb(255 255 255 / 14%); }
.ah-transcript { min-height: 0; display: flex; flex-direction: column; gap: 13px; padding: 16px 13px; overflow-y: auto; overscroll-behavior: contain; background: linear-gradient(180deg, var(--ah-soft), #fbfdfd); scrollbar-width: thin; }
.ah-loading, .ah-empty-error { min-height: 100%; display: grid; place-content: center; justify-items: center; gap: 8px; padding: 24px; color: var(--ah-muted); text-align: center; }
.ah-loading-dot { width: 9px; height: 9px; border-radius: 50%; background: var(--ah-brand); animation: ah-pulse 1s infinite ease-in-out; }
@keyframes ah-pulse { 50% { opacity: .32; transform: scale(.8); } }
.ah-message { max-width: 86%; display: grid; gap: 6px; align-self: flex-start; }
.ah-message.user { align-self: flex-end; }
.ah-bubble { padding: 10px 11px; border: 1px solid var(--ah-border); border-radius: 5px 14px 14px; background: white; box-shadow: 0 4px 13px rgb(18 45 52 / 4%); white-space: pre-wrap; overflow-wrap: anywhere; }
.ah-message.user .ah-bubble { border-color: var(--ah-brand); border-radius: 14px 5px 14px 14px; color: white; background: var(--ah-brand); }
.ah-message.cancelled .ah-bubble { opacity: .72; }
.ah-message-image { width: min(210px, 100%); max-height: 180px; display: block; margin-bottom: 7px; border-radius: 9px; object-fit: cover; }
.ah-typing { min-width: 46px; display: flex; gap: 4px; padding: 4px 2px; }
.ah-typing i { width: 6px; height: 6px; border-radius: 50%; background: #839399; animation: ah-typing 1.2s infinite ease-in-out; }
.ah-typing i:nth-child(2) { animation-delay: .15s; }
.ah-typing i:nth-child(3) { animation-delay: .3s; }
@keyframes ah-typing { 0%, 60%, 100% { opacity: .4; transform: translateY(0); } 30% { opacity: 1; transform: translateY(-3px); } }
.ah-products { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(218px, 82%); gap: 8px; overflow-x: auto; scroll-snap-type: x mandatory; padding: 1px 1px 5px; }
.ah-product { min-width: 0; overflow: hidden; border: 1px solid var(--ah-border); border-radius: 13px; background: white; scroll-snap-align: start; }
.ah-product-image { height: 112px; display: grid; place-items: center; overflow: hidden; color: var(--ah-brand); background: linear-gradient(145deg, var(--ah-soft), #e8f1f0); font-size: 23px; }
.ah-product-image img { width: 100%; height: 100%; object-fit: cover; }
.ah-product-copy { display: grid; gap: 5px; padding: 10px; }
.ah-product-copy small { color: var(--ah-muted); font-size: 9px; }
.ah-product-copy strong { overflow: hidden; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.ah-price { color: var(--ah-brand); font-size: 12px; font-weight: 800; }
.ah-stock { color: #917019; font-size: 9px; font-weight: 700; }
.ah-stock.available { color: #21854f; }
.ah-options { margin: 0; color: var(--ah-muted); font-size: 9px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ah-product-copy a { justify-self: start; color: var(--ah-brand); font-size: 10px; font-weight: 750; text-decoration: none; }
.ah-sources { padding: 7px 8px; border: 1px solid var(--ah-border); border-radius: 9px; color: var(--ah-muted); background: white; font-size: 9px; }
.ah-sources summary { color: var(--ah-brand); font-weight: 750; cursor: pointer; }
.ah-sources ul { display: grid; gap: 5px; margin: 7px 0 0; padding-left: 15px; }
.ah-suggestions { display: flex; gap: 6px; padding: 0 12px 10px; overflow-x: auto; background: white; }
.ah-suggestions[hidden] { display: none; }
.ah-suggestions button { flex: 0 0 auto; min-height: 31px; padding: 0 9px; border: 1px solid color-mix(in srgb, var(--ah-brand) 28%, var(--ah-border)); border-radius: 999px; color: var(--ah-brand); background: white; font-size: 9px; font-weight: 700; cursor: pointer; }
.ah-attachment { display: flex; align-items: center; gap: 8px; margin: 0 11px 8px; padding: 7px; border: 1px solid var(--ah-border); border-radius: 10px; background: var(--ah-soft); }
.ah-attachment[hidden] { display: none; }
.ah-attachment img { width: 42px; height: 42px; border-radius: 8px; object-fit: cover; }
.ah-attachment span { min-width: 0; flex: 1; overflow: hidden; color: var(--ah-muted); font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
.ah-attachment button { width: 30px; height: 30px; border: 0; border-radius: 8px; color: var(--ah-muted); background: transparent; cursor: pointer; }
.ah-composer { padding: 10px; border-top: 1px solid var(--ah-border); background: white; }
.ah-composer-row { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: end; gap: 6px; }
.ah-upload { width: 38px; height: 38px; display: grid; place-items: center; border: 0; border-radius: 10px; color: var(--ah-muted); background: var(--ah-soft); cursor: pointer; }
.ah-upload[hidden] { display: none; }
.ah-composer textarea { width: 100%; max-height: 92px; min-height: 38px; resize: none; padding: 9px 10px; border: 1px solid var(--ah-border); border-radius: 11px; color: var(--ah-text); background: white; line-height: 1.4; }
.ah-send { width: 38px; height: 38px; display: grid; place-items: center; border: 0; border-radius: 11px; color: white; background: var(--ah-brand); cursor: pointer; }
.ah-send:disabled, .ah-upload:disabled { opacity: .5; cursor: not-allowed; }
.ah-stop { display: none; width: auto; padding: 0 10px; font-size: 10px; font-weight: 750; }
.ah-composer.streaming .ah-send { display: none; }
.ah-composer.streaming .ah-stop { display: block; }
.ah-note { margin: 6px 4px 0; color: var(--ah-muted); font-size: 8px; text-align: center; }
.ah-error { margin: 0 10px 8px; color: #a03d3d; font-size: 10px; }
.ah-error[hidden] { display: none; }
.ah-retry { min-height: 34px; padding: 0 12px; border: 0; border-radius: 9px; color: white; background: var(--ah-brand); font-weight: 750; cursor: pointer; }
.ah-sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
@media (max-width: 480px) {
  :host, :host([data-position="left"]) { right: 10px; bottom: 10px; left: 10px; }
  .ah-panel { width: 100%; height: min(690px, calc(100dvh - 78px)); border-radius: 18px; }
  .ah-launcher, :host([data-position="left"]) .ah-launcher { margin-left: auto; margin-right: 0; }
}
@media (prefers-reduced-motion: reduce) {
  .ah-panel, .ah-launcher, .ah-loading-dot, .ah-typing i { animation: none; transition: none; }
}
`;
