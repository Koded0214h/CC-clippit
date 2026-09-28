"use client";

import { usePathname } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  campaignDraftsApi,
  type CampaignDraftFinalizeOut,
  type CampaignDraftOut,
} from "@/lib/api/campaigns";
import { uploadsApi } from "@/lib/api/account";
import { errorMessage } from "@/lib/api/client";

export type BriefRule = { id: string; text: string; kind: "must" | "avoid" };
export type CampaignMetricKey = "view" | "comment" | "share" | "visit" | "signup" | "lead" | "purchase";
export type CampaignMetricDraft = { type: CampaignMetricKey; rate: number; unitSize: number; minimum: number };
export type CampaignAssetDraft = { id: string; name: string; url: string; kind: string };

export type BrandCampaignDraft = {
  title: string;
  description: string;
  sourceLink: string;
  coverImage: string;
  coverUploadId: string;
  platforms: string[];
  assets: CampaignAssetDraft[];
  niche: string;
  accessMode: "public" | "invite";
  rules: BriefRule[];
  minimumViews: number;
  videoCap: number;
  creatorCap: number;
  maxSubmissions: number;
  endCondition: "duration" | "budget";
  days: number;
  pot: number;
  rate: number;
  metrics: CampaignMetricDraft[];
  conversionMode: "website" | "whatsapp";
  storeUrl: string;
  whatsappNumber: string;
  attributionWindowDays: number;
  attributionModel: "first_touch" | "last_touch";
};

const initialDraft: BrandCampaignDraft = {
  title: "", description: "", sourceLink: "", coverImage: "", coverUploadId: "", platforms: [], assets: [], niche: "",
  accessMode: "public", rules: [], minimumViews: 1000, videoCap: 50000, creatorCap: 75000, maxSubmissions: 3,
  endCondition: "duration", days: 14, pot: 500000, rate: 500,
  metrics: [{ type: "view", rate: 500, unitSize: 1000, minimum: 1000 }], conversionMode: "website", storeUrl: "",
  whatsappNumber: "", attributionWindowDays: 30, attributionModel: "last_touch",
};

type BrandCampaignContextValue = {
  draft: BrandCampaignDraft;
  draftLoading: boolean;
  draftError: string;
  update: (next: Partial<BrandCampaignDraft>) => void;
  addRule: (kind: BriefRule["kind"], text: string) => void;
  removeRule: (id: string) => void;
  togglePlatform: (platform: string) => void;
  toggleMetric: (metric: CampaignMetricKey) => void;
  updateMetric: (metric: CampaignMetricKey, next: Partial<CampaignMetricDraft>) => void;
  finalize: () => Promise<CampaignDraftFinalizeOut>;
  reset: () => void;
};

const BrandCampaignContext = createContext<BrandCampaignContextValue | null>(null);

function numberValue(value: unknown, fallback: number) {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function fromServer(record: CampaignDraftOut): BrandCampaignDraft {
  const answers = record.answers;
  const payout = (answers.payout_rule && typeof answers.payout_rule === "object" ? answers.payout_rule : {}) as Record<string, unknown>;
  const conversion = (answers.conversion_setup && typeof answers.conversion_setup === "object" ? answers.conversion_setup : {}) as Record<string, unknown>;
  const rawRules = Array.isArray(answers.rules) ? answers.rules : [];
  const rawMetrics = Array.isArray(answers.performance_metrics) ? answers.performance_metrics : [];
  const rawAssets = Array.isArray(answers.assets) ? answers.assets : [];
  return {
    ...initialDraft,
    title: typeof answers.title === "string" ? answers.title : "",
    description: typeof answers.description === "string" ? answers.description : "",
    sourceLink: typeof answers.source_link === "string" ? answers.source_link : "",
    coverUploadId: typeof answers.cover_image_upload_id === "string" ? answers.cover_image_upload_id : "",
    platforms: Array.isArray(answers.platforms) ? answers.platforms.filter((item): item is string => typeof item === "string").map((item) => item.charAt(0).toUpperCase() + item.slice(1)) : [],
    assets: rawAssets.flatMap((item, index) => {
      if (!item || typeof item !== "object") return [];
      const asset = item as Record<string, unknown>;
      if (typeof asset.url !== "string" || typeof asset.name !== "string") return [];
      return [{ id: `saved-${index}-${asset.name}`, name: asset.name, url: asset.url, kind: typeof asset.kind === "string" ? asset.kind : "asset" }];
    }),
    niche: typeof answers.category === "string" ? answers.category : "",
    accessMode: answers.access_mode === "invite" ? "invite" : "public",
    rules: rawRules.flatMap((item, index) => {
      if (!item || typeof item !== "object") return [];
      const rule = item as Record<string, unknown>;
      if (typeof rule.text !== "string") return [];
      return [{ id: `saved-rule-${index}`, text: rule.text, kind: rule.kind === "avoid" ? "avoid" as const : "must" as const }];
    }),
    minimumViews: numberValue(payout.min_views_threshold, initialDraft.minimumViews),
    videoCap: numberValue(payout.video_cap_amount, initialDraft.videoCap),
    creatorCap: numberValue(payout.cap_amount, initialDraft.creatorCap),
    maxSubmissions: numberValue(payout.max_submissions, initialDraft.maxSubmissions),
    endCondition: answers.end_condition === "budget" ? "budget" : "duration",
    days: numberValue(answers.duration_days, initialDraft.days),
    pot: numberValue(answers.pot, initialDraft.pot),
    rate: numberValue(payout.rate_per_1000_views, initialDraft.rate),
    metrics: rawMetrics.length ? rawMetrics.flatMap((item) => {
      if (!item || typeof item !== "object") return [];
      const metric = item as Record<string, unknown>;
      const type = metric.metric_type;
      if (!["view", "comment", "share", "visit", "signup", "lead", "purchase"].includes(String(type))) return [];
      return [{ type: type as CampaignMetricKey, rate: numberValue(metric.rate_amount, 1), unitSize: numberValue(metric.unit_size, type === "view" ? 1000 : 1), minimum: numberValue(metric.min_threshold, 0) }];
    }) : initialDraft.metrics,
    conversionMode: conversion.destination_type === "whatsapp" ? "whatsapp" : "website",
    storeUrl: typeof conversion.destination_url === "string" ? conversion.destination_url : "",
    whatsappNumber: typeof conversion.whatsapp_number === "string" ? conversion.whatsapp_number : "",
    attributionWindowDays: numberValue(conversion.attribution_window_days, initialDraft.attributionWindowDays),
    attributionModel: conversion.attribution_model === "first_touch" ? "first_touch" : "last_touch",
  };
}

function toServer(draft: BrandCampaignDraft) {
  const viewMetric = draft.metrics.find((metric) => metric.type === "view");
  const hasConversion = draft.metrics.some((metric) => ["visit", "signup", "lead", "purchase"].includes(metric.type));
  return {
    title: draft.title,
    description: draft.description,
    category: draft.niche || null,
    source_link: draft.sourceLink || null,
    platforms: draft.platforms.map((platform) => platform.toLowerCase()),
    pot: draft.pot,
    payout_rule: {
      rate_per_1000_views: viewMetric?.rate ?? draft.rate,
      cap_amount: draft.creatorCap,
      video_cap_amount: draft.videoCap,
      max_submissions: draft.maxSubmissions,
      min_views_threshold: viewMetric?.minimum ?? 0,
    },
    duration_days: draft.endCondition === "duration" ? draft.days : null,
    rules: draft.rules.map(({ kind, text }) => ({ kind, text })),
    access_mode: draft.accessMode,
    assets: draft.assets.map(({ name, url, kind }) => ({ name, url, kind })),
    end_condition: draft.endCondition,
    performance_metrics: draft.metrics.map((metric) => ({ metric_type: metric.type, rate_amount: metric.rate, unit_size: metric.unitSize, min_threshold: metric.minimum })),
    conversion_setup: hasConversion ? {
      destination_type: draft.conversionMode,
      destination_url: draft.conversionMode === "website" ? draft.storeUrl : null,
      whatsapp_number: draft.conversionMode === "whatsapp" ? draft.whatsappNumber : null,
      attribution_window_days: draft.attributionWindowDays,
      attribution_model: draft.attributionModel,
    } : null,
  };
}

export function BrandCampaignProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const inBuilder = pathname.startsWith("/brand/campaigns/new");
  const [draft, setDraft] = useState(initialDraft);
  const [draftLoading, setDraftLoading] = useState(false);
  const [draftError, setDraftError] = useState("");
  const draftId = useRef("");
  const revision = useRef(0);
  const serverReady = useRef(false);
  const lastSaved = useRef("");
  const queue = useRef<Promise<unknown>>(Promise.resolve());

  useEffect(() => {
    if (!inBuilder || serverReady.current) return;
    let cancelled = false;
    setDraftLoading(true);
    setDraftError("");
    campaignDraftsApi.list()
      .then(async (records) => records[0] ?? campaignDraftsApi.create())
      .then(async (record) => {
        const uploadId = typeof record.answers.cover_image_upload_id === "string" ? record.answers.cover_image_upload_id : "";
        const cover = uploadId ? await uploadsApi.status(uploadId).catch(() => null) : null;
        return { record, coverUrl: cover?.url ?? "" };
      })
      .then(({ record, coverUrl }) => {
        if (cancelled) return;
        const hydrated = { ...fromServer(record), coverImage: coverUrl };
        draftId.current = record.id;
        revision.current = record.revision;
        lastSaved.current = JSON.stringify(toServer(hydrated));
        setDraft(hydrated);
        serverReady.current = true;
      })
      .catch((reason) => { if (!cancelled) setDraftError(errorMessage(reason, "Your campaign draft could not be loaded.")); })
      .finally(() => { if (!cancelled) setDraftLoading(false); });
    return () => { cancelled = true; };
  }, [inBuilder]);

  const persist = useCallback(async (snapshot: BrandCampaignDraft, extras: Record<string, unknown> = {}) => {
    if (!draftId.current) throw new Error("Campaign draft is not ready.");
    const payload = { ...toServer(snapshot), ...extras };
    const record = await campaignDraftsApi.update(draftId.current, { revision: revision.current, step: pathname.split("/").at(-1) || "details", ...payload });
    revision.current = record.revision;
    lastSaved.current = JSON.stringify(toServer(snapshot));
    setDraftError("");
    return record;
  }, [pathname]);

  useEffect(() => {
    if (!inBuilder || !serverReady.current || !draftId.current) return;
    const signature = JSON.stringify(toServer(draft));
    if (signature === lastSaved.current) return;
    const timer = window.setTimeout(() => {
      if (!serverReady.current) return;
      const snapshot = draft;
      queue.current = queue.current.then(() => persist(snapshot)).catch((reason) => {
        setDraftError(errorMessage(reason, "Your campaign draft could not be saved."));
      });
    }, 600);
    return () => window.clearTimeout(timer);
  }, [draft, inBuilder, persist]);

  const finalize = useCallback(async () => {
    const snapshot = draft;
    serverReady.current = false;
    const operation = async () => {
      const extras: Record<string, unknown> = {};
      if (snapshot.coverImage.startsWith("data:")) {
        const upload = await uploadsApi.imageFromDataUrl(snapshot.coverImage);
        extras.cover_image_upload_id = upload.id;
        setDraft((current) => ({ ...current, coverUploadId: upload.id, coverImage: upload.url }));
      } else if (snapshot.coverUploadId) {
        extras.cover_image_upload_id = snapshot.coverUploadId;
      }
      await persist(snapshot, extras);
      return campaignDraftsApi.finalize(draftId.current);
    };
    const result = queue.current.then(operation, operation);
    queue.current = result.then(() => undefined, () => undefined);
    try {
      return await result;
    } catch (reason) {
      serverReady.current = true;
      throw reason;
    }
  }, [draft, persist]);

  const value = useMemo<BrandCampaignContextValue>(() => ({
    draft, draftLoading, draftError,
    update: (next) => setDraft((current) => ({ ...current, ...next })),
    addRule: (kind, text) => setDraft((current) => ({ ...current, rules: [...current.rules, { id: crypto.randomUUID(), kind, text }] })),
    removeRule: (id) => setDraft((current) => ({ ...current, rules: current.rules.filter((rule) => rule.id !== id) })),
    togglePlatform: (platform) => setDraft((current) => ({ ...current, platforms: current.platforms.includes(platform) ? current.platforms.filter((item) => item !== platform) : [...current.platforms, platform] })),
    toggleMetric: (metric) => setDraft((current) => {
      const selected = current.metrics.some((item) => item.type === metric);
      if (selected && current.metrics.length === 1) return current;
      const defaults: Record<CampaignMetricKey, CampaignMetricDraft> = {
        view: { type: "view", rate: 500, unitSize: 1000, minimum: 1000 }, comment: { type: "comment", rate: 25, unitSize: 1, minimum: 0 },
        share: { type: "share", rate: 40, unitSize: 1, minimum: 0 }, visit: { type: "visit", rate: 15, unitSize: 1, minimum: 0 },
        signup: { type: "signup", rate: 250, unitSize: 1, minimum: 0 }, lead: { type: "lead", rate: 350, unitSize: 1, minimum: 0 },
        purchase: { type: "purchase", rate: 1000, unitSize: 1, minimum: 0 },
      };
      return { ...current, metrics: selected ? current.metrics.filter((item) => item.type !== metric) : [...current.metrics, defaults[metric]] };
    }),
    updateMetric: (metric, next) => setDraft((current) => ({
      ...current,
      metrics: current.metrics.map((item) => item.type === metric ? { ...item, ...next } : item),
      ...(metric === "view" && typeof next.rate === "number" ? { rate: next.rate } : {}),
      ...(metric === "view" && typeof next.minimum === "number" ? { minimumViews: next.minimum } : {}),
    })),
    finalize,
    reset: () => setDraft(initialDraft),
  }), [draft, draftError, draftLoading, finalize]);

  return <BrandCampaignContext.Provider value={value}>{children}</BrandCampaignContext.Provider>;
}

export function useBrandCampaign() {
  const value = useContext(BrandCampaignContext);
  if (!value) throw new Error("useBrandCampaign must be used inside BrandCampaignProvider");
  return value;
}
