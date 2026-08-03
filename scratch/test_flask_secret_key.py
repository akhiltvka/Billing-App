import sys
import os
import unittest
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')

import app

class TestFlaskSecretKey(unittest.TestCase):
    def test_env_override(self):
        os.environ['APP_SECRET_KEY'] = 'test_custom_env_secret_12345'
        key = app._get_flask_secret_key()
        self.assertEqual(key, 'test_custom_env_secret_12345')

    def test_persisted_file_generation_and_reuse(self):
        if 'APP_SECRET_KEY' in os.environ:
            del os.environ['APP_SECRET_KEY']

        # Use temporary directory for testing persistent key file
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ['PROGRAMDATA'] = tmpdir
            
            # First invocation -> generates and persists
            key1 = app._get_flask_secret_key()
            self.assertEqual(len(key1), 64)  # hex string of 32 bytes = 64 chars

            secret_file = os.path.join(tmpdir, 'MPI_Billing_App', 'flask_secret.key')
            self.assertTrue(os.path.exists(secret_file))

            # Second invocation -> reads existing key
            key2 = app._get_flask_secret_key()
            self.assertEqual(key1, key2)

    def test_fallback_on_file_error(self):
        if 'APP_SECRET_KEY' in os.environ:
            del os.environ['APP_SECRET_KEY']

        # Point PROGRAMDATA to a non-existent drive path to force file I/O exception
        os.environ['PROGRAMDATA'] = 'Z:\\non_existent_dir_98765'
        key = app._get_flask_secret_key()
        self.assertIsNotNone(key)
        self.assertEqual(len(key), 32)  # os.urandom(32) returns 32 bytes

if __name__ == '__main__':
    unittest.main()
