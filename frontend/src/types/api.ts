export interface HealthResponse { status: 'ok'; service: string; database: 'connected'; }
export interface ApiErrorResponse { error: { code: string; message: string }; }
