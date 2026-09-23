export const BRAND_CAMPAIGN_FEE_RATE = 0.15;
export const BRAND_TOP_UP_FEE_RATE = 0.025;
export const BRAND_CANCELLATION_FEE_RATE = 0.025;
export const BRAND_WITHDRAWAL_FEE_RATE = 0;
export const CREATOR_WITHDRAWAL_FEE_RATE = 0.07;
export const MINIMUM_WALLET_WITHDRAWAL = 5000;

export function calculateFee(amount: number, rate: number) {
  return Math.round(Math.max(0, amount) * rate);
}

export function feePercentage(rate: number) {
  return Math.round(rate * 100);
}
