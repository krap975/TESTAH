"""One public event representation for REST history and persisted-event streaming."""
from app.core.config import Settings
from app.events.store import sanitize
from app.models.assessment import RunEvent
from app.rai.provider import secret_values
from app.schemas.assessments import EventRead


def monitoring_secrets(settings: Settings) -> list[str]:
    return [*secret_values(settings), settings.monitor_token.get_secret_value(),
            settings.paypal_client_id.get_secret_value(), settings.paypal_client_secret.get_secret_value(),
            settings.payment_operator_token.get_secret_value()]


def public_event(event: RunEvent, settings: Settings) -> EventRead:
    result = EventRead.model_validate(event)
    result.payload = sanitize(result.payload, monitoring_secrets(settings))
    result.correlation_id = sanitize(result.correlation_id, monitoring_secrets(settings))
    return result
