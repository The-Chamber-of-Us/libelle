from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from google_auth_oauthlib.flow import Flow

import bootstrap_google_oauth as bootstrap


@pytest.fixture
def session(tmp_path):
    flow = Flow.from_client_config(
        {'web': {'client_id': 'test-client', 'client_secret': 'test-secret',
                 'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                 'token_uri': 'https://oauth2.googleapis.com/token'}},
        scopes=bootstrap.DRIVE_SCOPES,
        redirect_uri='http://127.0.0.1:8765/oauth2callback',
        autogenerate_code_verifier=True,
    )
    # Exercise the real library's URL/state/PKCE generation without Google access.
    generated = bootstrap.BootstrapSession(flow, tmp_path / 'token.json')
    generated.flow = Mock(credentials=SimpleNamespace(
        valid=True, refresh_token='refresh', to_json=lambda: '{"token":"new"}',
    ))
    generated.token_file.write_text('existing credentials')
    return generated


def test_valid_state_exchanges_and_atomically_replaces_private_token(session):
    query = parse_qs(urlsplit(session.auth_url).query)
    assert query['state'] == [session.state]
    assert query['code_challenge_method'] == ['S256']
    assert query['access_type'] == ['offline']
    session.complete(f'/oauth2callback?state={session.state}&code=valid-code')
    session.flow.fetch_token.assert_called_once_with(code='valid-code')
    assert session.token_file.read_text() == '{"token":"new"}'
    assert session.token_file.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize('query', [
    'code=secret', 'state=&code=secret', 'state=wrong&code=secret',
    'state={state}&state={state}&code=secret', 'state={state}',
    'state={state}&code=', 'state={state}&code=a&code=b',
    'state={state}&error=access_denied&code=secret',
])
def test_bad_callback_never_exchanges_or_replaces(session, query):
    with pytest.raises(ValueError):
        session.complete('/oauth2callback?' + query.format(state=session.state))
    session.flow.fetch_token.assert_not_called()
    assert session.token_file.read_text() == 'existing credentials'


def test_stale_state_never_exchanges(session, monkeypatch):
    monkeypatch.setattr(bootstrap.time, 'monotonic', lambda: session.deadline)
    with pytest.raises(ValueError):
        session.complete(f'?state={session.state}&code=secret')
    session.flow.fetch_token.assert_not_called()
    assert session.token_file.read_text() == 'existing credentials'


def test_failed_exchange_preserves_token_and_consumes_session(session):
    session.flow.fetch_token.side_effect = RuntimeError('provider failure')
    with pytest.raises(RuntimeError):
        session.complete(f'?state={session.state}&code=secret')
    with pytest.raises(ValueError):
        session.complete(f'?state={session.state}&code=secret')
    assert session.flow.fetch_token.call_count == 1
    assert session.token_file.read_text() == 'existing credentials'


@pytest.mark.parametrize('attribute,value', [('valid', False), ('refresh_token', None)])
def test_unusable_credentials_preserve_token(session, attribute, value):
    setattr(session.flow.credentials, attribute, value)
    with pytest.raises(ValueError):
        session.complete(f'?state={session.state}&code=secret')
    assert session.token_file.read_text() == 'existing credentials'


def test_failed_replace_preserves_token_and_cleans_tempfile(session, monkeypatch):
    monkeypatch.setattr(bootstrap.os, 'replace', Mock(side_effect=OSError('disk error')))
    with pytest.raises(OSError):
        session.complete(f'?state={session.state}&code=secret')
    assert session.token_file.read_text() == 'existing credentials'
    assert list(session.token_file.parent.iterdir()) == [session.token_file]


def test_application_never_exposes_bootstrap(monkeypatch):
    monkeypatch.setenv('ENV', 'production')
    from main import app
    client = TestClient(app)
    for path in ('/authorize', '/oauth2callback'):
        assert client.get(path, params={'state': 'x', 'code': 'secret'}).status_code == 404
        assert path not in app.openapi()['paths']


@pytest.mark.parametrize('valid', [True, False])
def test_cli_listener_is_loopback_temporary_and_fail_closed(tmp_path, monkeypatch, valid):
    flow = Mock()
    flow.authorization_url.side_effect = lambda **kw: ('https://google.example/consent', kw['state'])
    flow.credentials = SimpleNamespace(valid=True, refresh_token='r', to_json=lambda: 'new')
    monkeypatch.setattr(bootstrap.Flow, 'from_client_secrets_file', Mock(return_value=flow))
    target = tmp_path / 'token.json'
    target.write_text('old')
    monkeypatch.setattr(bootstrap, 'TOKEN_FILE', target)
    server = Mock(server_port=8765)
    server.__enter__ = Mock(return_value=server)
    server.__exit__ = Mock(return_value=False)

    def make_server(host, port, callback, **kwargs):
        assert (host, port) == ('127.0.0.1', 8765)
        def handle():
            state = flow.authorization_url.call_args.kwargs['state'] if valid else 'wrong'
            start_response = Mock()
            callback({'REQUEST_METHOD': 'GET', 'PATH_INFO': '/oauth2callback',
                      'QUERY_STRING': f'state={state}&code=secret'}, start_response)
            assert start_response.call_args.args[0] == ('200 OK' if valid else '400 Bad Request')
        server.handle_request.side_effect = handle
        return server

    monkeypatch.setattr(bootstrap, 'make_server', make_server)
    if valid:
        bootstrap.bootstrap(8765)
        assert target.read_text() == 'new'
    else:
        with pytest.raises(RuntimeError):
            bootstrap.bootstrap(8765)
        flow.fetch_token.assert_not_called()
        assert target.read_text() == 'old'
    server.__exit__.assert_called_once()


def test_successful_callback_cannot_be_replayed(session):
    callback = f'?state={session.state}&code=secret'
    session.complete(callback)
    with pytest.raises(ValueError):
        session.complete(callback)
    session.flow.fetch_token.assert_called_once()


def test_cli_timeout_closes_listener_without_exchange(tmp_path, monkeypatch):
    flow = Mock()
    flow.authorization_url.side_effect = lambda **kw: ('https://google.example', kw['state'])
    monkeypatch.setattr(bootstrap.Flow, 'from_client_secrets_file', Mock(return_value=flow))
    target = tmp_path / 'token.json'
    target.write_text('old')
    monkeypatch.setattr(bootstrap, 'TOKEN_FILE', target)
    server = Mock(server_port=8765)
    server.__enter__ = Mock(return_value=server)
    server.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(bootstrap, 'make_server', Mock(return_value=server))
    monkeypatch.setattr(bootstrap.time, 'monotonic', Mock(side_effect=[0, 301]))
    with pytest.raises(RuntimeError):
        bootstrap.bootstrap(8765)
    server.__exit__.assert_called_once()
    flow.fetch_token.assert_not_called()
    assert target.read_text() == 'old'
