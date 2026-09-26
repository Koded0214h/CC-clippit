import { api } from "./client";

export interface CreatorWalletOut {
  role: "creator";
  held: number;
  available: number;
  processing: number;
  paid_all_time: number;
  min_withdrawal: number;
  withdrawal_fee_rate: number;
}

export interface UploadOut {
  id: string;
  kind: string;
  url: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
}

export interface TicketOut {
  id: string;
  category: string;
  subject: string;
  status: "open" | "closed";
  priority: "low" | "normal" | "high" | "urgent";
  resource_type: string | null;
  resource_id: string | null;
  unread_count: number;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
}

export interface ThreadMessageOut {
  id: string;
  author_id: string;
  from_admin: boolean;
  body: string;
  created_at: string;
  attachment_upload_ids?: string[];
  evidence_upload_ids?: string[];
}

export interface TicketDetailOut extends TicketOut {
  messages: ThreadMessageOut[];
}

export type DisputeType = "submission_verdict" | "earning_entry" | "payout" | "funding_order" | "refund";

export interface DisputeOut {
  id: string;
  type: DisputeType;
  resource_id: string;
  reason: string;
  status: "open" | "awaiting_customer" | "resolved" | "withdrawn";
  amount_at_risk: number | null;
  deadline_at: string;
  resolution: "upheld" | "denied" | "partial" | null;
  resolution_note: string | null;
  unread_count: number;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
}

export interface DisputeDetailOut extends DisputeOut {
  messages: ThreadMessageOut[];
}

export interface LegalDocumentOut {
  slug: string;
  version: string;
  title: string;
  effective_date: string;
  body: string;
}

export interface MyAcceptancesOut {
  accepted: { slug: string; version: string; action: string; accepted_at: string }[];
  newly_required: string[];
}

export interface ReceiptVerifyOut {
  reference: string;
  type: "funding" | "payout" | "refund" | string;
  amount: number;
  status: string;
  issuer: string;
  date: string;
  digest: string;
}

export interface ProductConfigOut {
  country_code: string;
  currency: string;
  hold_days: number;
  min_withdrawal_naira: number;
  funding_fee_rate: number;
  platforms: { platform: string; connectable: boolean }[];
  legal: { slug: string; version: string; effective_date: string }[];
}

export interface PublicCreatorWork {
  campaign_title: string;
  campaign_slug: string;
  brand_name: string | null;
  platform: string;
  submitted_at: string;
}

export interface PublicCreatorProfileOut {
  handle: string;
  display_name: string;
  photo_url: string | null;
  bio: string | null;
  interests: string[];
  stats: { approved_clips: number; verified_views: number };
  recent_work: PublicCreatorWork[];
}

async function uploadFile(path: string, file: Blob, name = "upload") {
  const form = new FormData();
  form.append("file", file, file instanceof File ? file.name : name);
  return api.upload<UploadOut>(path, form);
}

export const walletApi = {
  get: () => api.get<CreatorWalletOut>("/wallet"),
};

export const uploadsApi = {
  image: (file: Blob) => uploadFile("/uploads/images", file, "image.jpg"),
  evidence: (file: Blob) => uploadFile("/uploads/evidence", file, "evidence"),
  supportAttachment: (file: Blob) => uploadFile("/uploads/support-attachments", file, "attachment"),
  imageFromDataUrl: async (dataUrl: string) => uploadFile("/uploads/images", await (await fetch(dataUrl)).blob(), "profile.jpg"),
};

export const supportApi = {
  list: (status?: "open" | "closed") => api.get<TicketOut[]>(`/support/tickets${status ? `?status=${status}` : ""}`),
  get: (id: string) => api.get<TicketDetailOut>(`/support/tickets/${id}`),
  create: (payload: { category: string; subject: string; message: string; resource_type?: string | null; resource_id?: string | null; attachment_upload_ids?: string[] }) =>
    api.post<TicketDetailOut>("/support/tickets", payload),
  reply: (id: string, body: string, attachmentUploadIds: string[] = []) =>
    api.post<TicketDetailOut>(`/support/tickets/${id}/messages`, { body, attachment_upload_ids: attachmentUploadIds }),
  close: (id: string) => api.post<TicketOut>(`/support/tickets/${id}/close`, {}),
  reopen: (id: string) => api.post<TicketOut>(`/support/tickets/${id}/reopen`, {}),
};

export const disputesApi = {
  list: () => api.get<DisputeOut[]>("/disputes"),
  get: (id: string) => api.get<DisputeDetailOut>(`/disputes/${id}`),
  create: (payload: { type: DisputeType; resource_id: string; reason: string }) => api.post<DisputeDetailOut>("/disputes", payload),
  reply: (id: string, body: string, evidenceUploadIds: string[] = []) =>
    api.post<DisputeDetailOut>(`/disputes/${id}/messages`, { body, evidence_upload_ids: evidenceUploadIds }),
  withdraw: (id: string) => api.post<DisputeOut>(`/disputes/${id}/withdraw`, {}),
};

export const legalApi = {
  document: (slug: string) => api.get<LegalDocumentOut>(`/legal/documents/${slug}`),
  myAcceptances: () => api.get<MyAcceptancesOut>("/legal/acceptances/me"),
  accept: (slug: string, version: string, action = "accepted_update") => api.post("/legal/acceptances", { slug, version, action }),
};

export const receiptsApi = {
  verify: (reference: string) => api.get<ReceiptVerifyOut>(`/receipts/${encodeURIComponent(reference)}/verify`),
};

export const productConfigApi = {
  get: () => api.get<ProductConfigOut>("/product-config"),
};

export const publicProfilesApi = {
  creator: (handle: string) => api.get<PublicCreatorProfileOut>(`/profiles/creators/${encodeURIComponent(handle)}`),
  creatorClips: (handle: string, limit = 20, offset = 0) =>
    api.get<PublicCreatorWork[]>(`/profiles/creators/${encodeURIComponent(handle)}/clips?limit=${limit}&offset=${offset}`),
};
