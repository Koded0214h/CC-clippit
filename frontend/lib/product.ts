export type CampaignStatus = "Open" | "Closing soon" | "Joined";

export interface Campaign {
  slug: string;
  brand: string;
  title: string;
  line: string;
  image: string;
  rate: number;
  pot: number;
  remaining: number;
  daysLeft: number;
  hoursLeft: number;
  platforms: string[];
  category: string;
  status: CampaignStatus;
  minimumViews: number;
  creatorCap: number;
  videoCap: number;
  maxSubmissions: number;
  accessMode: "public" | "invite";
  assets: Array<{ name: string; url: string; kind: string }>;
  endCondition: string;
  brief: string;
  mustDo: string[];
  mustAvoid: string[];
}

export const campaigns: Campaign[] = [
  {
    slug: "indomie-no-long-thing",
    brand: "Indomie",
    title: "No long thing",
    line: "Turn the quickest meal in the room into the clip nobody scrolls past.",
    image: "/assets/video/creator-reaction-poster.jpg",
    rate: 500,
    pot: 500000,
    remaining: 312500,
    daysLeft: 4,
    hoursLeft: 18,
    platforms: ["TikTok", "Instagram"],
    category: "Comedy",
    status: "Closing soon",
    minimumViews: 1000,
    creatorCap: 75000,
    videoCap: 50000,
    maxSubmissions: 3,
    accessMode: "public",
    assets: [{ name: "Official campaign sound", url: "#campaign-sound", kind: "sound" }, { name: "Product pack reference", url: "#product-reference", kind: "reference" }],
    endCondition: "Ends in 4 days or when the pot is empty",
    brief:
      "Make a short, funny skit about the moment hunger interrupts everything. Indomie should feel like the quick save, not a scripted advert.",
    mustDo: [
      "Show the prepared noodles clearly on screen.",
      "Say or display: No long thing.",
      "Tag @indomie_nigeria and use #NoLongThing.",
      "Keep the finished clip between 15 and 45 seconds.",
    ],
    mustAvoid: [
      "Do not compare Indomie negatively with another food brand.",
      "Do not make health or nutrition claims.",
    ],
  },
  {
    slug: "palmpay-send-am-sharp",
    brand: "PalmPay",
    title: "Send am sharp",
    line: "Show the tiny everyday emergency that a fast transfer can fix.",
    image: "/assets/photos/street-style.jpg",
    rate: 650,
    pot: 750000,
    remaining: 604500,
    daysLeft: 9,
    hoursLeft: 6,
    platforms: ["TikTok", "YouTube"],
    category: "Lifestyle",
    status: "Open",
    minimumViews: 1000,
    creatorCap: 90000,
    videoCap: 60000,
    maxSubmissions: 2,
    accessMode: "public",
    assets: [{ name: "PalmPay product reference", url: "#product-reference", kind: "reference" }],
    endCondition: "Ends in 9 days or when the pot is empty",
    brief:
      "Tell a recognisable Nigerian story where a quick transfer changes the mood. Keep it human, useful and rooted in your own style.",
    mustDo: [
      "Show the transfer confirmation moment.",
      "Mention that PalmPay transfers are fast.",
      "Tag @palmpayappng and use #SendAmSharp.",
      "Use only your own footage and audio you have permission to use.",
    ],
    mustAvoid: [
      "Do not claim transfers can never fail.",
      "Do not show a real account balance or private bank details.",
    ],
  },
  {
    slug: "gbedu-main-character",
    brand: "Gbedu Records",
    title: "Main character sound",
    line: "Give a new Lagos anthem the entrance it deserves.",
    image: "/assets/photos/headphones.jpg",
    rate: 400,
    pot: 300000,
    remaining: 128800,
    daysLeft: 2,
    hoursLeft: 11,
    platforms: ["TikTok", "Instagram"],
    category: "Music",
    status: "Joined",
    minimumViews: 1000,
    creatorCap: 45000,
    videoCap: 30000,
    maxSubmissions: 3,
    accessMode: "invite",
    assets: [{ name: "Official campaign sound", url: "#campaign-sound", kind: "sound" }, { name: "Visual direction", url: "#visual-direction", kind: "reference" }],
    endCondition: "Ends in 2 days or when the pot is empty",
    brief:
      "Use the official sound to build a transformation, entrance or reveal. The first two seconds need a clear visual hook.",
    mustDo: [
      "Use at least 12 seconds of the official campaign sound.",
      "Reveal the transformation before the beat drops.",
      "Tag @gbedurecords and use #MainCharacterSound.",
      "Keep the campaign sound audible throughout the reveal.",
    ],
    mustAvoid: [
      "Do not remix or speed up the supplied audio.",
      "Do not include violent or unsafe stunt footage.",
    ],
  },
  {
    slug: "tara-face-card",
    brand: "House of Tara",
    title: "Face card stays",
    line: "Build a beauty transition around the look that survives the whole day.",
    image: "/assets/photos/fashion.jpg",
    rate: 800,
    pot: 420000,
    remaining: 389600,
    daysLeft: 12,
    hoursLeft: 2,
    platforms: ["Instagram", "YouTube"],
    category: "Beauty",
    status: "Open",
    minimumViews: 1500,
    creatorCap: 70000,
    videoCap: 50000,
    maxSubmissions: 2,
    accessMode: "public",
    assets: [{ name: "Product pack shots", url: "#product-reference", kind: "reference" }, { name: "Lighting reference", url: "#lighting-reference", kind: "reference" }],
    endCondition: "Ends in 12 days or when the pot is empty",
    brief:
      "Create a before-and-after beauty story with a clear product moment and a finished look that still feels like you.",
    mustDo: [
      "Show the product packaging for at least two seconds.",
      "Include a clear before-and-after transition.",
      "Tag @houseoftara_intl and use #FaceCardStays.",
      "Film in bright, natural or studio lighting.",
    ],
    mustAvoid: [
      "Do not use a beauty filter on the final look.",
      "Do not make medical or skin treatment claims.",
    ],
  },
];

export const leaderboard = [
  { rank: 1, name: "Zara Makes", handle: "@zaramakes", views: 184200, earned: 42600 },
  { rank: 2, name: "Tobi On Cam", handle: "@tobioncam", views: 156800, earned: 38200 },
  { rank: 3, name: "Nana Edits", handle: "@nanaedits", views: 121400, earned: 31100 },
  { rank: 4, name: "Kenny Frames", handle: "@kennyframes", views: 98700, earned: 24700 },
  { rank: 5, name: "Amaka Daily", handle: "@amakadaily", views: 82600, earned: 20600 },
  { rank: 6, name: "Deji Does It", handle: "@dejidoesit", views: 71400, earned: 17800 },
];

export const money = (value: number) =>
  new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency: "NGN",
    maximumFractionDigits: 0,
  }).format(value);

export const compactNumber = (value: number) =>
  new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(value);
