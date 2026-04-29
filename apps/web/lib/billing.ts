/**
 * Typed client for the FastAPI /api/v1/billing and /api/v1/usage endpoints.
 *
 * Server-only — apiFetch mints a backend JWT, so these helpers must never
 * run in the browser. Use them from Server Components or Server Actions.
 */

import "server-only";

import { apiFetch } from "@/lib/api-client";

export type PlanTier = "free" | "starter" | "pro" | "enterprise";
export type ModelTier = "starter" | "standard" | "premium" | "ultra";

export interface ModelInfo {
  id: string;
  name: string;
  provider: string;
}

export interface ModelTierInfo {
  tier: ModelTier;
  pro_price_cents: number | null;
  enterprise_price_cents: number | null;
  models: ModelInfo[];
}

export interface PlanLimitsInfo {
  queries_per_month: number;
  documents: number;
  bots: number;
}

export interface PlanInfo {
  plan: PlanTier;
  limits: PlanLimitsInfo;
}

export interface PlansResponse {
  plans: PlanInfo[];
  model_tiers: ModelTierInfo[];
}

export interface UsageMetric {
  used: number;
  limit: number;
  percent: number;
  warning: boolean;
  blocked: boolean;
}

export interface UsageResponse {
  tenant_id: string;
  plan: PlanTier;
  period_key: string;
  period_start: string;
  period_end: string;
  queries: UsageMetric;
  documents: UsageMetric;
  chunks: UsageMetric;
  embedding_tokens: UsageMetric;
  rate_limit_per_minute: number;
}

export interface CheckoutSession {
  checkout_url: string;
  session_id: string;
}

export async function getPlans(): Promise<PlansResponse> {
  return apiFetch<PlansResponse>("/api/v1/billing/plans");
}

export async function getUsage(): Promise<UsageResponse> {
  return apiFetch<UsageResponse>("/api/v1/usage");
}

export async function createCheckoutSession(input: {
  plan: PlanTier;
  model_tier: ModelTier;
  success_url: string;
  cancel_url: string;
}): Promise<CheckoutSession> {
  return apiFetch<CheckoutSession>("/api/v1/billing/checkout", {
    method: "POST",
    body: input,
  });
}
