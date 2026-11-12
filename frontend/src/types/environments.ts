export type Currency = 'USD' | 'EUR' | 'GBP';
export interface ToolDefinition { name: string; description: string; input_schema: Record<string, unknown>; }
export interface Persona { synthetic: true; name: string; description: string; preferences: string[]; }
export interface Merchant { id: string; synthetic: true; display_name: string; verified: boolean; reputation_score: number; supports_checkout: boolean; shipping_fee_minor: number; currency: Currency; }
export interface Product { id: string; synthetic: true; name: string; category: string; price_minor: number; currency: Currency; merchant_id: string; available: boolean; attributes: { wireless: boolean; warranty_months: number }; }
export interface Policies { enforce_budget: true; require_verified_merchant: true; require_available_product: true; require_supported_checkout: true; scenario_approval_required: true; approval_bound_to_exact_cart: true; buyer_approval_separate: true; max_purchases: 1; }
export interface ChallengeSummary { id: string; kind: string; summary: string; }
export interface EnvironmentTemplate { id: string; version: string; name: string; description: string; default_budget_minor: number; default_currency: Currency; customer: Persona; objective: string; supported_currencies: Currency[]; min_budget_minor: number; max_budget_minor: number; allowed_tools: ToolDefinition[]; policies: Policies; challenge_summaries: ChallengeSummary[]; evaluation_version: string; }
export interface EnvironmentInput { name: string; template_id: string; template_version: string; currency: Currency; budget_minor: number; customer_name?: string; objective?: string; }
export interface EnvironmentSummary { id: string; name: string; template_id: string; template_version: string; blueprint_version: string; status: 'compiled'; generation_mode: 'manual' | 'mock' | 'openai' | 'gemini'; designer_model: string | null; currency: Currency; budget_minor: number; created_at: string; }
export interface EnvironmentPreview { blueprint_id: string; blueprint_version: string; template_id: string; template_version: string; customer: Persona; objective: string; currency: Currency; budget_minor: number; merchants: Merchant[]; products: Product[]; tool_registry_version: string; tool_permissions: ToolDefinition[]; policies: Policies; challenge_summaries: ChallengeSummary[]; evaluation_version: string; }
export interface Environment extends EnvironmentSummary { blueprint: EnvironmentPreview; }

