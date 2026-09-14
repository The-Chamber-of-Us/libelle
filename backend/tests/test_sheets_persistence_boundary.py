"""Bounded repository and durable-path checks using synthetic Sheets state."""
from copy import deepcopy
import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest

import parser_worker as cli
import validator
from services import dashboard_service, parser_worker, parser_job_reconciliation
from sheet_schema import SHEET_SCHEMA, build_row
from storage import parser_jobs_repo, sheets_repo


class Request:
    def __init__(self, result=None):
        self.result = result or {}

    def execute(self):
        return deepcopy(self.result)


class Sheet:
    """Only the metadata and row operations used by this persistence path."""
    def __init__(self):
        self.headers = deepcopy(SHEET_SCHEMA)
        self.rows = {tab: [] for tab in SHEET_SCHEMA}
        self.calls = []

    def values(self):
        return self

    def get(self, **kwargs):
        if 'range' not in kwargs:
            self.calls.append(('schema', 'tabs'))
            return Request({'sheets': [{'properties': {'title': tab}} for tab in self.headers]})
        tab = kwargs['range'].split('!')[0]
        self.calls.append(('read', tab))
        return Request({'values': self.rows[tab]})

    def batchGet(self, **kwargs):
        self.calls.append(('schema', 'headers'))
        return Request({'valueRanges': [{'values': [self.headers[r.split('!')[0]]]} for r in kwargs['ranges']]})

    def append(self, **kwargs):
        tab = kwargs['range'].split('!')[0]
        self.calls.append(('append', tab))
        self.rows[tab].extend(deepcopy(kwargs['body']['values']))
        return Request()

    def update(self, **kwargs):
        tab, cells = kwargs['range'].split('!')
        row = int(cells.split(':')[0][1:])
        self.calls.append(('update', tab))
        self.rows[tab][row - 2] = deepcopy(kwargs['body']['values'][0])
        return Request()


@pytest.fixture
def sheet(monkeypatch):
    fake = Sheet()
    monkeypatch.setattr(sheets_repo, '_get_sheet', lambda: fake)
    monkeypatch.setattr(parser_jobs_repo, '_get_sheet', lambda: fake)
    return fake


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parents[2] / 'scripts' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(params=['cli', 'service', 'reconcile'])
def entrypoint(request, monkeypatch, tmp_path):
    monkeypatch.setattr('sys.argv', ['test'])
    if request.param == 'cli':
        return cli
    if request.param == 'reconcile':
        return load_script('reconcile_parser_jobs')
    service = load_script('run_parser_worker_service')
    monkeypatch.setattr(service, 'LOCK_FILE', tmp_path / 'worker.lock')
    monkeypatch.setattr(service.signal, 'signal', lambda *args: None)
    return service


@pytest.mark.parametrize('failure', ['missing_tab', 'bad_headers', 'bad_optional_headers', 'access'])
def test_startup_failure_blocks_all_operations(entrypoint, sheet, monkeypatch, capsys, failure):
    if failure == 'missing_tab':
        del sheet.headers['parser_jobs']
    elif failure == 'bad_headers':
        sheet.headers['parser_results'] = ['synthetic-invalid-header']
    elif failure == 'bad_optional_headers':
        sheet.headers['ops_events'] = ['synthetic-invalid-header']
    else:
        def fail():
            print('synthetic-private-diagnostic')
            raise RuntimeError('synthetic-private-diagnostic')
        monkeypatch.setattr(sheets_repo, '_get_sheet', fail)
    guards = []
    for module, names in [(parser_worker, ['list_claimable_jobs', 'claim_job', 'download_file', 'parse_resume', 'persist_parser_result_if_missing', 'persist_resolver_output_for_parser_result', 'update_job', 'append_error_row']), (parser_job_reconciliation, ['reconcile_missing_parser_jobs'])]:
        for name in names:
            guard = Mock(side_effect=AssertionError('operation before validation'))
            monkeypatch.setattr(module, name, guard)
            guards.append(guard)
    before = deepcopy(sheet.rows)
    assert entrypoint.main() == 1
    assert all(guard.call_count == 0 for guard in guards)
    assert sheet.rows == before
    assert all(operation == 'schema' for operation, _ in sheet.calls)
    output = capsys.readouterr()
    assert 'failed' in output.out.lower()
    assert 'synthetic-private' not in output.out + output.err
    assert output.err == ''


@pytest.mark.parametrize('optional_present', [True, False])
def test_startup_validates_once_before_operations(entrypoint, sheet, monkeypatch, optional_present):
    if not optional_present:
        del sheet.headers['ops_events']
    def polls(worker):
        assert worker.run_once() == 0
        assert worker.run_once() == 0
    monkeypatch.setattr(parser_worker.ParserWorker, 'poll_forever', polls)
    if hasattr(entrypoint, 'serve'):
        monkeypatch.setattr(entrypoint, 'serve', lambda worker, *_: polls(worker))
    assert entrypoint.main() == 0
    assert sheet.calls[:2] == [('schema', 'tabs'), ('schema', 'headers')]
    assert sum(operation == 'schema' for operation, _ in sheet.calls) == 2
    assert any(operation == 'read' for operation, _ in sheet.calls[2:])


def persist(submission='synthetic-submission', run='attempt-1', **parsed):
    sheets_repo.persist_parser_result_if_missing(submission_id=submission, parser_run_id=run, parsed=parsed)


def test_result_idempotency_and_distinct_attempts(sheet):
    persist(parser_version='original')
    before = deepcopy(sheet.rows['parser_results'])
    persist(parser_version='replacement')
    assert sheet.rows['parser_results'] == before
    persist(run='attempt-2')
    persist(submission='another-submission')
    assert [(r['submission_id'], r['parser_run_id']) for r in sheets_repo.load_parser_result_rows()] == [
        ('synthetic-submission', 'attempt-1'), ('synthetic-submission', 'attempt-2'), ('another-submission', 'attempt-1')]
    assert sheet.calls.count(('append', 'parser_results')) == 3


def test_resolver_targets_pair_and_preserves_parser_fields(sheet):
    persist(run='attempt-2')
    persist(submission='another-submission')
    persist(parser_version='parser-test', skills={'value': ['python'], 'confidence': 0.8}, locations={'value': ['Remote'], 'confidence': 0.6})
    before = deepcopy(sheet.rows['parser_results'])
    fields = dict(resolver_version='resolver-test', aliases_version='aliases-test', resolved_skill_ids=['python'], unknown_skills=['synthetic'], resolver_coverage=0.5)
    assert sheets_repo.persist_resolver_output_for_parser_result(submission_id='synthetic-submission', parser_run_id='attempt-1', parsed={**fields, 'submission_id': 'wrong', 'parser_run_id': 'wrong', 'created_at': 'wrong', 'parser_version': 'wrong', 'skills': {'value': []}})
    assert sheet.rows['parser_results'][:2] == before[:2]
    result = sheets_repo.load_parser_result_rows()[2]
    for index, name in enumerate(SHEET_SCHEMA['parser_results']):
        if name not in fields:
            assert str(sheet.rows['parser_results'][2][index]) == str(before[2][index])
    assert result['resolved_skill_ids'] == '["python"]'
    assert result['unknown_skills'] == '["synthetic"]'
    assert result['resolver_version'] == 'resolver-test'
    assert result['aliases_version'] == 'aliases-test'
    assert result['resolver_coverage'] == '0.5'
    before = deepcopy(sheet.rows)
    calls = list(sheet.calls)
    assert not sheets_repo.persist_resolver_output_for_parser_result(submission_id='synthetic-submission', parser_run_id='missing-attempt', parsed=fields)
    assert sheet.rows == before
    assert not any(op in ('append', 'update') for op, _ in sheet.calls[len(calls):])


@pytest.mark.parametrize('resolver_degraded', [False, True])
def test_durable_path_preserves_owned_state_and_selects_authority(sheet, monkeypatch, resolver_degraded):
    sheet.rows['submissions'] = [build_row('submissions', {'submission_id': 'synthetic-submission', 'resume_status': 'uploaded', 'drive_file_id': 'synthetic-reference', 'skills_raw': 'intake skill', 'location_raw': 'intake location'})]
    sheet.rows['ops'] = [build_row('ops', {'submission_id': 'synthetic-submission', 'status': 'reviewed', 'notes': 'synthetic review', 'tags': 'synthetic-tag', 'contact_tracking': 'synthetic-contact', 'updated_by': 'reviewer@example.test', 'updated_at': '2026-01-01T00:00:00Z'})]
    owned = deepcopy({tab: sheet.rows[tab] for tab in ('submissions', 'ops', 'ops_events')})
    validator.validate_sheet_schema()
    job = parser_jobs_repo.create_parser_job(submission_id='synthetic-submission', drive_file_id='synthetic-reference', resume_filename='synthetic.pdf')
    monkeypatch.setattr(parser_worker, 'download_file', lambda _: b'synthetic')
    monkeypatch.setattr(parser_worker, 'extract_text_from_pdf_bytes', lambda _: 'Skills\nPython')
    if resolver_degraded:
        from services import parser_service
        def unavailable():
            raise RuntimeError('Synthetic Resolver unavailable')
        monkeypatch.setattr(parser_service, '_load_alias_map', unavailable)
    worker = parser_worker.ParserWorker(parser_worker.ParserWorkerConfig(worker_id='synthetic-worker'), parser_run_id_factory=lambda: 'authoritative-attempt')
    assert worker.run_once() == 1
    current = parser_jobs_repo.get_job(job['job_id'])
    assert current['status'] == 'succeeded'
    assert current['authoritative_parser_run_id'] == 'authoritative-attempt'
    before = deepcopy(sheet.rows['parser_results'])
    persist(run='authoritative-attempt', parser_version='must-not-replace')
    assert worker.run_once() == 0
    assert sheet.rows['parser_results'] == before
    # A newer, non-authoritative result must not displace the worker's attempt.
    persist(run='unrelated-attempt', parser_version='not-authoritative')
    sheet.rows['parser_results'][-1][2] = '01-01-2099 00:00:00 UTC'
    snapshot = dashboard_service.get_snapshot_records()[0]
    assert snapshot['parsed']['parser_run_id'] == 'authoritative-attempt'
    assert snapshot['parsed']['parser_state'] == 'complete'
    assert {tab: sheet.rows[tab] for tab in owned} == owned
    assert sheet.calls[:2] == [('schema', 'tabs'), ('schema', 'headers')]
    if resolver_degraded:
        assert sheets_repo.load_error_rows()[0]['error_code'] == 'RESOLVER_FAILED'
        assert snapshot['resolved']['resolver_state'] == 'not_run'
        assert snapshot['resolved']['resolver_result_state'] == 'failed'
    else:
        assert sheets_repo.load_parser_result_rows()[0]['resolver_version']
        assert not sheet.rows['errors']
