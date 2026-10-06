# Website widget

The independent widget includes launcher, responsive panel, real agent greeting, transcript, structured product cards, image input, privacy notice and optional consented contact form. It is not a storefront clone and never ships reference-image products or prices.

The loader exposes only the public agent ID. Session creation validates active published revision, origin policy and abuse limits, then returns an opaque short-lived session. No workspace ID, privileged token, provider key or internal numeric ID appears in the loader/DOM/URL.

The widget supports streaming, stop, retry, transcript restore within retention, safe session reset, image upload and a clearly optional contact request. It distinguishes unavailable agent, invalid origin, rate/quota limit, expired session, network/provider failure and unknown product facts.

Styles are isolated from hostile host CSS. Mobile uses safe areas and an accessible close action; focus returns to the launcher. Product links/images use server-approved references only.
