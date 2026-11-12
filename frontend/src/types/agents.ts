export interface Agent {
  id: string; name: string; description: string; endpoint_url: string;
  connection_mode: 'external' | 'local_sample'; authentication_configured: boolean;
  auth_header_name: string | null; created_at: string; updated_at: string;
  last_test_status: 'not_tested' | 'connected' | 'failed'; last_test_at: string | null;
  last_test_code: string | null; last_test_message: string | null;
}
export interface AgentInput {
  name: string; description: string; endpoint_url: string;
  connection_mode: 'external' | 'local_sample';
  authentication?: { header_name: 'Authorization' | 'X-API-Key'; secret_key: string } | null;
}
export interface ConnectionTest { status: 'connected'; request_id: string; response_type: 'message' | 'tool_call' | 'completed'; message: string; }

