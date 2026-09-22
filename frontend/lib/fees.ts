export const BRAND_CAMPAIGN_FEE_RATE = 0.15;
export const CREATOR_WITHDRAWAL_FEE_RATE = 0.07;

export function calculateFee(amount: number, rate: number) {
  return Math.round(Math.max(0, amount) * rate);
}

export function feePercentage(rate: number) {
  return Math.round(rate * 100);
}
