"""Reporting is a read-only view of immutable Phase 8 evaluations and evidence."""
from copy import deepcopy
import json
from unittest.mock import Mock
import pytest
from sqlalchemy import event, inspect, select
from app.evaluation.service import process_one
from app.models.assessment import Assessment, RunEvent
from app.models.evaluation import Evaluation, EvaluationJob, ScoringBinding
from app.schemas.evaluation import EvaluationResultRead
from app.reports.recommendations import recommendations
from app.reports import service
from test_evaluation import reference, saved_reference  # Reuse authoritative isolated fixtures.


def all_rows(factory):
    with factory() as session:
        return {table: sorted(json.dumps(list(row), default=str) for row in session.connection().exec_driver_sql(
            'SELECT * FROM "' + table.replace('"', '""') + '"')) for table in inspect(session.bind).get_table_names()}


@pytest.fixture
def report_fixture(saved_reference):
    client, factory, run_id = saved_reference
    process_one(factory, run_id)
    return client, factory, run_id


def test_report_reference_preserves_score_recovery_denial_capture_and_all_events(report_fixture):
    client, factory, run_id = report_fixture
    before = all_rows(factory)
    response = client.get(f'/api/assessments/{run_id}/report')
    assert response.status_code == 200, response.text
    assert response.headers['cache-control'] == 'no-store'
    report = response.json()
    result = report['evaluation']['result']
    assert result['overall_score'] == 100 and result['certification']['decision'] == 'pass'
    assert report['cutoff_sequence'] == report['evidence_total'] == 68
    assert report['evidence_complete'] and report['missing_event_ids'] == []
    assert len(report['recovery']) == 1 and report['recovery'][0]['points'] == 100
    assert report['recommendations'] == []  # Challenge denial must not become misconduct advice.
    payment = report['payments'][0]
    assert payment['total_minor'] == 8000 and payment['currency'] == 'USD'
    assert payment['provider'] == 'paypal_sandbox' and payment['status'] == 'completed'
    assert payment['capture_id'] and payment['captured_event_ids'] and payment['inspection_event_ids']
    assert payment['authorization_event_ids'] and payment['buyer_approval_event_ids']
    exported = client.get(f'/api/assessments/{run_id}/report/export?evaluation_id={result["id"]}')
    assert exported.status_code == 200 and 'attachment' in exported.headers['content-disposition']
    body = exported.json()
    assert body['evaluation']['result'] == result
    assert len(body['evidence']) == 68
    assert [e['sequence'] for e in body['evidence']] == list(range(1, 69))
    assert any(e['event_type'] == 'policy.violation' and e['sequence'] == 30 for e in body['evidence'])
    assert any(e['event_type'] == 'payment.captured' and e['sequence'] == 58 for e in body['evidence'])
    assert before == all_rows(factory)


def test_open_refresh_export_and_print_data_never_write_or_call_operational_services(report_fixture, monkeypatch):
    client, factory, run_id = report_fixture
    # Include an expired-looking running assessment: reporting must not invoke recovery.
    with factory() as session, session.begin():
        run = session.get(Assessment, run_id)
        run.status = 'running'
        from datetime import datetime, timedelta, timezone
        run.lease_expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        run.lease_token = 'expired-worker-claim'
    before = all_rows(factory)
    forbidden = Mock(side_effect=AssertionError('Reporting called an operational service'))
    for name in ('process', 'list', 'buyer_return'):
        monkeypatch.setattr(client.app.state.payments, name, forbidden)
    monkeypatch.setattr(client.app.state.worker, 'submit', forbidden)
    monkeypatch.setattr(client.app.state.evaluation_worker, 'pump', forbidden)
    for module, name in [('app.execution.service', 'recover_expired'), ('app.api.assessments', 'recover_expired'),
                         ('app.evaluation.service', 'enqueue'), ('app.evaluation.service', 'request_evaluation'),
                         ('app.evaluation.service', 'process_one')]:
        monkeypatch.setattr(module + '.' + name, forbidden)
    def only_reads(conn, cursor, statement, parameters, context, executemany):
        assert statement.lstrip().split()[0].upper() not in {'UPDATE', 'INSERT', 'DELETE', 'REPLACE', 'CREATE', 'ALTER', 'DROP'}
    event.listen(client.app.state.engine, 'before_cursor_execute', only_reads)
    try:
        for _ in range(2):
            for path in ('/api/reports', f'/api/assessments/{run_id}/report', f'/api/assessments/{run_id}/report/events',
                         f'/api/assessments/{run_id}/report/export', f'/api/assessments/{run_id}/evaluations'):
                assert client.get(path).status_code == 200
        assert before == all_rows(factory)
        forbidden.assert_not_called()
    finally:
        event.remove(client.app.state.engine, 'before_cursor_execute', only_reads)


def test_evidence_pagination_is_complete_and_cutoff_pinned_after_late_evidence(report_fixture):
    client, factory, run_id = report_fixture
    original = client.get(f'/api/assessments/{run_id}/report').json()
    evaluation_id = original['evaluation']['result']['id']
    with factory() as session, session.begin():
        run = session.get(Assessment, run_id)
        run.event_sequence = 69
        session.add(RunEvent(run_id=run_id, sequence=69, event_type='payment.status_unknown', payload={}))
    after = 0; evidence = []
    while True:
        page = client.get(f'/api/assessments/{run_id}/report/events?evaluation_id={evaluation_id}&after_sequence={after}&limit=7').json()
        assert page['cutoff_sequence'] == 68 and page['total'] == 68 and page['evaluation_id'] == evaluation_id
        evidence.extend(page['events'])
        if page['next_after_sequence'] is None:
            break
        after = page['next_after_sequence']
    assert len(evidence) == 68 and len({e['id'] for e in evidence}) == 68
    report = client.get(f'/api/assessments/{run_id}/report?evaluation_id={evaluation_id}').json()
    assert report['evaluation']['stale']
    assert report['evaluation']['result'] == original['evaluation']['result']
    assert client.get(f'/api/assessments/{run_id}/report/export?evaluation_id={evaluation_id}').json()['evidence'] == evidence


def test_selected_historical_evaluation_does_not_switch_to_new_result(report_fixture):
    client, factory, run_id = report_fixture
    first = client.get(f'/api/assessments/{run_id}/report').json()['evaluation']['result']
    with factory() as session, session.begin():
        old = session.get(Evaluation, first['id'])
        from datetime import datetime, timedelta
        new = Evaluation(run_id=run_id, version=old.version, input_digest='new-input', cutoff_sequence=old.cutoff_sequence,
            input_json=deepcopy(old.input_json), result_json=deepcopy(old.result_json), created_at=datetime.now() + timedelta(days=1))
        session.add(new)
    selected = client.get(f'/api/assessments/{run_id}/report?evaluation_id={first["id"]}').json()
    assert not selected['is_latest_evaluation'] and selected['evaluation']['result'] == first
    assert selected['latest_evaluation_id'] != first['id']


def test_public_report_excludes_private_inputs_and_redacts_known_secrets(report_fixture, monkeypatch):
    client, factory, run_id = report_fixture
    secret = 'phase9-secret-marker-do-not-export'
    from pydantic import SecretStr
    monkeypatch.setattr(client.app.state.settings, 'monitor_token', SecretStr(secret))
    with factory() as session, session.begin():
        row = session.scalar(select(RunEvent).where(RunEvent.run_id == run_id, RunEvent.sequence == 1))
        row.payload = {'message': secret + ' https://private.example/secret', 'credential': secret,
                       'callback_hash': 'unknown-private-callback', 'access_token': 'unknown-runtime-token'}
        ev = session.scalar(select(Evaluation).where(Evaluation.run_id == run_id))
        ev.input_json = {**ev.input_json, 'private_prompt': 'not-public-input'}
    for suffix in ('/report', '/report/events', '/report/export'):
        response = client.get(f'/api/assessments/{run_id}' + suffix)
        assert response.status_code == 200
        assert secret not in response.text and 'private.example' not in response.text and 'not-public-input' not in response.text
        assert 'input_json' not in response.text
        assert 'unknown-private-callback' not in response.text and 'unknown-runtime-token' not in response.text


def test_missing_history_disables_complete_export_without_inventing_evidence(report_fixture):
    client, factory, run_id = report_fixture
    with factory() as session, session.begin():
        row = session.scalar(select(RunEvent).where(RunEvent.run_id == run_id, RunEvent.sequence == 58))
        session.delete(row)
    report = client.get(f'/api/assessments/{run_id}/report').json()
    assert not report['evidence_complete'] and report['missing_event_ids']
    response = client.get(f'/api/assessments/{run_id}/report/export')
    assert response.status_code == 409 and response.json()['error']['code'] == 'report_evidence_incomplete'


def test_unrequested_historical_report_never_creates_scoring_binding_or_job(report_fixture):
    client, factory, run_id = report_fixture
    with factory() as session, session.begin():
        for model in (Evaluation, EvaluationJob, ScoringBinding):
            for row in session.scalars(select(model).where(model.run_id == run_id)):
                session.delete(row)
            session.flush()
    before = all_rows(factory)
    report = client.get(f'/api/assessments/{run_id}/report').json()
    assert report['evaluation']['status'] == 'not_requested' and report['evaluation']['result'] is None
    assert report['cutoff_sequence'] == 0
    assert client.get(f'/api/assessments/{run_id}/report/export').status_code == 409
    assert before == all_rows(factory)


def test_missing_and_cross_run_evaluation_ids_have_safe_errors(report_fixture):
    client, _, run_id = report_fixture
    assert client.get('/api/assessments/missing/report').status_code == 404
    for suffix in ('', '/events', '/export'):
        response = client.get(f'/api/assessments/{run_id}/report{suffix}?evaluation_id=another-runs-evaluation')
        assert response.status_code == 404 and response.json()['error']['code'] == 'evaluation_not_found'
    assert client.get('/api/reports?offset=-1').status_code == 422
    assert client.get(f'/api/assessments/{run_id}/report/events?limit=501').status_code == 422


def test_export_size_and_history_limits_are_explicit_not_truncated(report_fixture, monkeypatch):
    client, _, run_id = report_fixture
    monkeypatch.setattr(service, 'MAX_EXPORT_BYTES', 10)
    response = client.get(f'/api/assessments/{run_id}/report/export')
    assert response.status_code == 409 and response.json()['error']['code'] == 'report_export_limit'
    monkeypatch.setattr(service, 'MAX_EVENTS', 10)
    response = client.get(f'/api/assessments/{run_id}/report')
    assert response.status_code == 409 and response.json()['error']['code'] == 'report_history_limit'


def test_report_listing_is_paginated_without_private_payloads(report_fixture):
    client, factory, run_id = report_fixture
    before = all_rows(factory)
    page = client.get('/api/reports?limit=1').json()
    assert page['total'] == 1 and len(page['items']) == 1
    assert page['items'][0]['overall_score'] == 100 and page['items'][0]['run_id'] == run_id
    assert client.get('/api/reports?offset=1&limit=1').json()['items'] == []
    assert 'input_json' not in json.dumps(page) and 'payload' not in json.dumps(page)
    assert before == all_rows(factory)


def test_guidance_maps_only_persisted_failures_and_keeps_unknowns_uninterpreted(report_fixture):
    client, _, run_id = report_fixture
    result = EvaluationResultRead.model_validate(client.get(f'/api/assessments/{run_id}/report').json()['evaluation']['result'])
    assert recommendations(result) == []
    result.findings[0].rule_id = 'policy_stale_cart'; result.findings[0].status = 'fail'
    advice = recommendations(result)
    assert len(advice) == 1 and advice[0].event_ids == result.findings[0].event_ids
    result.findings[0].rule_id = 'unknown_future_rule'
    assert recommendations(result) == []
    efficiency = next(d for d in result.dimensions if d.name == 'execution_efficiency')
    efficiency.score = 0
    inspection = next(f for f in result.findings if f.rule_id == 'task_inspection')
    inspection.status = 'fail'
    # A zero efficiency outcome without verified goal is not evidence of excess requests.
    assert all(item.id != 'efficiency' for item in recommendations(result))
    inspection.status = 'pass'
    assert any(item.id == 'efficiency' for item in recommendations(result))
    efficiency.score = 100
    result.coverage['recovery_opportunities'] = 0
    assert recommendations(result)[0].id == 'recovery-coverage'
    result.status = 'partial'; result.overall_score = None; result.evidence_gaps = ['missing_capture']
    advice = recommendations(result)
    assert any(item.id == 'evidence-quality' for item in advice)
    assert all(item.id != 'efficiency' for item in advice)
