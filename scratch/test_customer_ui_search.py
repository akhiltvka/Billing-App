import sys
import os
import unittest
import tempfile

tmp_db_fd, tmp_db_path = tempfile.mkstemp(suffix=".db")
os.close(tmp_db_fd)
os.environ['DB_PATH'] = tmp_db_path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')

import database
import app

class TestCustomerSearchUI(unittest.TestCase):
    def setUp(self):
        database.init_db()
        self.app = app.app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'admin'
            sess['user_role'] = 'admin'

    def test_customer_search_api_name_and_phone(self):
        conn = database.get_db()
        conn.execute("INSERT INTO customers (name, phone) VALUES ('Nikhil Sharma', '9876543210')")
        conn.execute("INSERT INTO customers (name, phone) VALUES ('Anil Verma', '9123456789')")
        conn.commit()
        conn.close()

        # Search by name "nikhil"
        res_name = self.client.get('/api/customers?q=nikhil')
        self.assertEqual(res_name.status_code, 200)
        data_name = res_name.get_json()['data']
        self.assertEqual(len(data_name), 1)
        self.assertEqual(data_name[0]['name'], 'Nikhil Sharma')

        # Search by phone "9876"
        res_phone = self.client.get('/api/customers?q=9876')
        self.assertEqual(res_phone.status_code, 200)
        data_phone = res_phone.get_json()['data']
        self.assertEqual(len(data_phone), 1)
        self.assertEqual(data_phone[0]['name'], 'Nikhil Sharma')

if __name__ == '__main__':
    unittest.main()
