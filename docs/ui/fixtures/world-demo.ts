export type DemoWorldFixture = typeof worldDemo;

export const worldDemo = {
  workspace: {
    id: "workspace-demo",
    name: "Zerotopro",
  },

  agents: [
    {
      id: "agent-sales",
      name: "Sales Agent",
      state: "active",
      channels: ["channel-website", "channel-facebook", "channel-zalo"],
      knowledge: ["knowledge-product", "knowledge-policy"],
      catalogScope: {
        collections: ["collection-women"],
        locations: ["location-q1", "location-q7"],
      },
      runtime: {
        activeConversations: 184,
        handling: {
          ai: 132,
          human: 21,
          waiting: 28,
          failed: 3,
        },
      },
    },
    {
      id: "agent-support",
      name: "Support Agent",
      state: "active",
      channels: ["channel-website"],
      knowledge: ["knowledge-faq"],
      catalogScope: {
        collections: [],
        locations: [],
      },
      runtime: {
        activeConversations: 48,
        handling: {
          ai: 39,
          human: 5,
          waiting: 4,
          failed: 0,
        },
      },
    },
    {
      id: "agent-cskh",
      name: "CSKH Agent",
      state: "paused",
      channels: ["channel-zalo"],
      knowledge: ["knowledge-policy"],
      catalogScope: {
        collections: [],
        locations: [],
      },
      runtime: {
        activeConversations: 0,
        handling: {
          ai: 0,
          human: 0,
          waiting: 0,
          failed: 0,
        },
      },
    },
  ],

  channels: [
    {
      id: "channel-website",
      name: "Website",
      provider: "website",
      state: "normal",
    },
    {
      id: "channel-facebook",
      name: "Facebook",
      provider: "facebook",
      state: "attention",
      attentionReason: "Reauthorization required",
    },
    {
      id: "channel-zalo",
      name: "Zalo",
      provider: "zalo",
      state: "normal",
    },
  ],

  knowledge: [
    {
      id: "knowledge-product",
      name: "Product Knowledge",
      state: "normal",
    },
    {
      id: "knowledge-policy",
      name: "Policy & Return",
      state: "normal",
    },
    {
      id: "knowledge-faq",
      name: "Support FAQ",
      state: "normal",
    },
  ],

  collections: [
    {
      id: "collection-women",
      name: "Women",
      productCount: 128,
    },
  ],

  locations: [
    {
      id: "location-q1",
      name: "HCM Q1",
      stockUnits: 423,
    },
    {
      id: "location-q7",
      name: "HCM Q7",
      stockUnits: 189,
    },
  ],

  projections: ["system", "agents", "catalog", "customers"],
} as const;
