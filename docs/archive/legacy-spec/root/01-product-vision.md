# 01 — Product vision

## Problem
Small fashion shops need a website assistant that accurately answers product/size/stock/policy questions, works when staff are away, showcases items with images and collects leads without requiring customers to log in. Most shops do not need a complex enterprise workflow editor at launch.

## Product
AgentHub manages workspace-scoped AI agents, shop data, knowledge sources, chat channels and conversations. First MVP = fashion shop owner configures one web assistant and embeds it on a shop website. Architectural interfaces permit future multi-agent and omnichannel use without shipping those UIs now.

## Personas
1. Shop owner: imports catalog, manages policies, configures chatbot and reviews conversations/leads.
2. Website visitor: asks in Vietnamese (and possibly other languages), sends a clothing image, sees relevant product cards, asks size/availability, may leave contact details.
3. Workspace staff (later UI): constrained access to data/agent configuration.

## MVP success signals (targets to be set after baseline)
- Owner can publish the widget without engineer intervention after initial integration.
- Relevant product suggestions reference existing catalog items with correct current price/variant/stock.
- The assistant abstains/escalates when size or stock information is missing.
- Visitors can chat anonymously and optionally opt into contact collection.
- No cross-workspace data disclosure in automated tests or logs.
- Shop can view chats, leads and basic usage.

## Explicit non-goals
Marketplace checkout, stock mutation, autonomous ordering, payments/refunds, drag-and-drop agent workflow designer, billing, live human inbox, social-channel integrations, scheduled crawling, enterprise analytics. See `00-decisions.md`.
