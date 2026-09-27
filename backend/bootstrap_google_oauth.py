"""Operator-only Drive credential bootstrap; never mounted in the application."""
import argparse
import hmac
import os
from pathlib import Path
import secrets
import tempfile
import time
from urllib.parse import parse_qs, urlsplit
from wsgiref.simple_server import WSGIRequestHandler, make_server

from google_auth_oauthlib.flow import Flow

from config import GOOGLE_OAUTH_CLIENT, TOKEN_FILE
from storage._auth import DRIVE_SCOPES

STATE_TTL_SECONDS = 300


def write_credentials(credentials, token_file):
    """Replace only a fully serialized token, with owner-only permissions."""
    payload = credentials.to_json()
    target = Path(token_file).absolute()
    fd, temporary = tempfile.mkstemp(prefix='.oauth-', dir=target.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class BootstrapSession:
    def __init__(self, flow, token_file):
        self.flow = flow
        self.token_file = token_file
        self.state = secrets.token_urlsafe(32)
        self.deadline = time.monotonic() + STATE_TTL_SECONDS
        self.used = False
        self.auth_url, returned_state = flow.authorization_url(
            state=self.state, access_type='offline', prompt='consent',
        )
        if returned_state != self.state:
            raise ValueError('Authorization state was not retained.')

    def complete(self, callback):
        if self.used:
            raise ValueError('Bootstrap session already consumed.')
        self.used = True
        query = parse_qs(urlsplit(callback).query, keep_blank_values=True)
        states = query.get('state', [])
        if (time.monotonic() >= self.deadline or len(states) != 1
                or not hmac.compare_digest(states[0].encode(), self.state.encode())):
            raise ValueError('Missing, invalid, or expired OAuth state.')
        codes = query.get('code', [])
        if 'error' in query or len(codes) != 1 or not codes[0]:
            raise ValueError('Authorization did not return a code.')
        self.flow.fetch_token(code=codes[0])
        credentials = self.flow.credentials
        if not credentials.valid or not credentials.refresh_token:
            raise ValueError('Google did not return persistent credentials.')
        write_credentials(credentials, self.token_file)


class QuietHandler(WSGIRequestHandler):
    def log_message(self, format, *args):
        pass  # Callback URLs contain authorization codes; never log them.


def bootstrap(port):
    result = {'success': False}

    def callback(environ, start_response):
        if environ['REQUEST_METHOD'] != 'GET' or environ['PATH_INFO'] != '/oauth2callback':
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            return [b'Not found.']
        try:
            session.complete('/oauth2callback?' + environ.get('QUERY_STRING', ''))
            result['success'] = True
        except Exception:
            pass  # Do not expose provider errors, codes, or tokens.
        start_response('200 OK' if result['success'] else '400 Bad Request',
                       [('Content-Type', 'text/plain'), ('Cache-Control', 'no-store')])
        return [b'Credentials saved.' if result['success'] else b'Bootstrap failed. Restart the CLI to retry.']

    with make_server('127.0.0.1', port, callback, handler_class=QuietHandler) as server:
        flow = Flow.from_client_secrets_file(
            GOOGLE_OAUTH_CLIENT, scopes=DRIVE_SCOPES,
            redirect_uri=f'http://127.0.0.1:{server.server_port}/oauth2callback',
            autogenerate_code_verifier=True,
        )
        session = BootstrapSession(flow, TOKEN_FILE)
        print('Open this URL in a browser on this machine within five minutes:')
        print(session.auth_url)
        while not session.used and time.monotonic() < session.deadline:
            server.timeout = max(0, session.deadline - time.monotonic())
            server.handle_request()
    if not result['success']:
        raise RuntimeError('Bootstrap failed or expired; existing credentials were preserved.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765, help='Loopback callback port (default: 8765)')
    args = parser.parse_args()
    try:
        bootstrap(args.port)
    except Exception:
        parser.exit(1, 'OAuth bootstrap failed; existing credentials were preserved. Restart to retry.\n')
    print('Drive credentials saved successfully.')


if __name__ == '__main__':
    main()
