"""Regression tests for debit-note document and export access."""

import unittest

from app import app


class TestDebitNotePrintExport(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()

    def test_print_route_requires_authentication(self):
        response = self.client.get('/debit-note/999999')
        self.assertEqual(response.status_code, 302)

    def test_export_route_requires_authentication(self):
        response = self.client.get('/api/purchase-returns?export=excel')
        self.assertEqual(response.status_code, 401)


if __name__ == '__main__':
    unittest.main()
