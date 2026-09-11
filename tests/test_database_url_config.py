"""Tests for external DATABASE_URL resolution, password percent-encoding, and startup enforcement."""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from database import (
    get_database_url,
    get_external_config_dir,
    normalize_database_url,
    save_database_url,
    set_restrictive_permissions
)


class TestDatabaseUrlConfig(unittest.TestCase):

    def test_normalize_database_url_encodes_raw_password_special_characters(self):
        """Verify that raw passwords containing @, #, :, ?, !, %, etc. are percent-encoded."""
        raw_url = "postgresql://postgres:MyP@ss#w:rd/?!%123@db.supabase.co:5432/postgres?sslmode=require"
        normalized = normalize_database_url(raw_url)

        self.assertTrue(normalized.startswith("postgresql://"))
        self.assertIn("@db.supabase.co:5432/postgres?sslmode=require", normalized)
        # Password must not contain unencoded delimiters like raw # or second @
        # Split out credentials
        auth = normalized.split("://")[1].rpartition("@")[0]
        user, _, pw = auth.partition(":")
        self.assertEqual(user, "postgres")
        self.assertNotIn("@", pw)
        self.assertNotIn("#", pw)
        self.assertNotIn(":", pw)
        self.assertIn("%40", pw)  # @
        self.assertIn("%23", pw)  # #
        self.assertIn("%3A", pw)  # :

    def test_normalize_database_url_handles_already_encoded_passwords(self):
        """Verify that already percent-encoded passwords are not double-encoded."""
        encoded_url = "postgresql://postgres:MyP%40ss%23123%21@db.supabase.co:5432/postgres"
        normalized = normalize_database_url(encoded_url)
        self.assertEqual(normalized, encoded_url)

    def test_normalize_database_url_converts_postgres_scheme(self):
        """Verify that postgres:// is normalized to postgresql://."""
        url = "postgres://usr:pwd@localhost:5432/db"
        normalized = normalize_database_url(url)
        self.assertTrue(normalized.startswith("postgresql://usr:pwd@localhost:5432/db"))

    def test_normalize_database_url_preserves_supabase_pooler_usernames(self):
        """Verify that dotted usernames (e.g. postgres.projectref) are preserved."""
        url = "postgresql://postgres.myprojectref:secret@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
        normalized = normalize_database_url(url)
        self.assertIn("postgres.myprojectref:secret@", normalized)

    def test_get_database_url_from_environment(self):
        """Verify get_database_url prioritizes DATABASE_URL environment variable."""
        test_env_url = "postgresql://envuser:envpass@db.env.co:5432/postgres"
        with patch.dict(os.environ, {'DATABASE_URL': test_env_url}):
            loaded = get_database_url()
            self.assertEqual(loaded, test_env_url)

    def test_save_and_get_database_url_from_external_file(self):
        """Verify save_database_url writes to external file and get_database_url loads it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_url = "postgresql://fileuser:raw@pass#1@db.file.co:5432/postgres"
            with patch.dict(os.environ, {'PROGRAMDATA': tmpdir}, clear=False):
                # Ensure DATABASE_URL is not in environment
                os.environ.pop('DATABASE_URL', None)
                norm = save_database_url(test_url)
                self.assertIn("%40", norm)

                expected_file = os.path.join(tmpdir, 'MPI_Billing_App', 'database_url.txt')
                self.assertTrue(os.path.exists(expected_file))
                with open(expected_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                self.assertEqual(content, norm)

                # Now load via get_database_url
                loaded = get_database_url()
                self.assertEqual(loaded, norm)

    def test_set_restrictive_permissions_executes_safely(self):
        """Verify set_restrictive_permissions executes without error on created config files."""
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(b"test_secret")
            tmp_path = tf.name
        try:
            set_restrictive_permissions(tmp_path)
            self.assertTrue(os.path.exists(tmp_path))
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_startup_validation_raises_when_unconfigured_outside_test_mode(self):
        """Verify validate_sync_configuration raises RuntimeError when unconfigured outside tests."""
        from app import validate_sync_configuration
        with tempfile.TemporaryDirectory() as empty_tmpdir:
            with patch.dict(os.environ, {'PROGRAMDATA': empty_tmpdir, 'TESTING': '0'}, clear=False):
                os.environ.pop('DATABASE_URL', None)
                os.environ.pop('PYTEST_CURRENT_TEST', None)
                # Temporarily simulate non-pytest runtime
                with patch.dict(sys.modules):
                    sys.modules.pop('pytest', None)
                    with self.assertRaises(RuntimeError) as ctx:
                        validate_sync_configuration()
                    self.assertIn("DATABASE_URL", str(ctx.exception))
                    self.assertIn("Setup Wizard", str(ctx.exception))
