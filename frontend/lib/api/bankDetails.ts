import { api } from "./client";

export interface BankAccountOut {
  creator_id: string;
  bank_code: string;
  bank_name: string;
  account_number_masked: string;
  account_name: string | null;
  verified: boolean;
  verified_at: string | null;
  updated_at: string;
}

export interface BankAccountIn {
  bank_code: string;
  bank_name: string;
  account_number: string;
}

export interface BankOut {
  code: string;
  name: string;
}

export interface ResolvedOut {
  account_name: string;
  bank_code: string;
  account_number_masked: string;
}

export const bankDetailsApi = {
  get: () => api.get<BankAccountOut>("/creators/me/bank-details"),
  save: (payload: BankAccountIn) => api.put<BankAccountOut>("/creators/me/bank-details", payload),
  resolve: (bank_code: string, account_number: string) =>
    api.post<ResolvedOut>("/banks/resolve", { bank_code, account_number }),
  verify: () => api.post<BankAccountOut>("/creators/me/bank-details/verify", {}),
  remove: (stepUpToken: string) => api.delete<void>("/creators/me/bank-details", { step_up_token: stepUpToken }),
};

export const banksApi = {
  list: () => api.get<BankOut[]>("/banks"),
};
