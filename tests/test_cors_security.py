"""
Regression Test Suite for CORS Allowlist & Session Cookie Security
"""

import unittest
import json
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, get_db


class TestCorsSecurity(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test_cors_secret_key'

        # Ensure a test user exists
        conn = get_db()
        conn.execute("DELETE FROM users WHERE username='test_cors_user'")
        conn.execute("""
            INSERT INTO users (username, password_hash, full_name, role, role_id, active)
            VALUES ('test_cors_user', 'dummy_hash', 'CORS Test User', 'admin', 1, 1)
        """)
        self.user_id = conn.execute("SELECT id FROM users WHERE username='test_cors_user'").fetchone()['id']
        conn.commit()
        conn.close()

    def test_allowed_origins_receive_cors_headers(self):
        """Allowed origins (5000 and 5173) must receive Access-Control-Allow-Origin and credentials headers."""
        allowed = [
            "http://127.0.0.1:5000",
            "http://localhost:5000",
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ]

        for orig in allowed:
            headers = {
                'Origin': orig,
                'Access-Control-Request-Method': 'GET'
            }
            # Preflight OPTIONS request
            response = self.client.open('/api/categories', method='OPTIONS', headers=headers)
            self.assertEqual(
                response.headers.get('Access-Control-Allow-Origin'),
                orig,
                f"Origin {orig} should be allowed"
            )
            self.assertEqual(
                response.headers.get('Access-Control-Allow-Credentials'),
                'true'
            )

    def test_disallowed_origin_does_not_receive_cors_reflection(self):
        """Disallowed external origins must not be reflected in Access-Control-Allow-Origin."""
        disallowed = [
            "http://malicious-site.com",
            "https://attacker.org",
            "http://localhost:8080",
            "http://127.0.0.1:3000"
        ]

        for orig in disallowed:
            headers = {
                'Origin': orig,
                'Access-Control-Request-Method': 'GET'
            }
            response = self.client.open('/api/categories', method='OPTIONS', headers=headers)
            self.assertNotEqual(
                response.headers.get('Access-Control-Allow-Origin'),
                orig,
                f"Origin {orig} should NOT receive Access-Control-Allow-Origin header"
            )

    def test_session_cookie_authentication_works_normally(self):
        """Session cookies must work correctly for desktop app and browser access."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user_id
            sess['username'] = 'test_cors_user'
            sess['user_role'] = 'admin'

        response = self.client.get('/api/auth/me')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data.get('status'), 'ok')
        self.assertEqual(data.get('data', {}).get('username'), 'test_cors_user')


if __name__ == '__main__':
    unittest.main()
