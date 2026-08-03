import sys
import os
import unittest
import tempfile
import threading

# Set environment DB_PATH to a temporary DB
tmp_db_fd, tmp_db_path = tempfile.mkstemp(suffix=".db")
os.close(tmp_db_fd)
os.environ['DB_PATH'] = tmp_db_path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')

import database
import app

class TestAtomicDocumentNumbers(unittest.TestCase):
    def setUp(self):
        database.init_db()
        conn = database.get_db()
        for k in ['next_bill_no', 'next_po_no', 'next_cn_no', 'next_conversion_no', 'next_test_no']:
            conn.execute("INSERT OR REPLACE INTO shop_settings (key, value) VALUES (?, '1')", (k,))
        conn.commit()
        conn.close()

    def test_sequential_bill_numbers(self):
        conn = database.get_db()
        b1 = app.next_bill_no(conn)
        b2 = app.next_bill_no(conn)
        b3 = app.next_bill_no(conn)
        conn.close()

        self.assertEqual(b1, "MPI-00001")
        self.assertEqual(b2, "MPI-00002")
        self.assertEqual(b3, "MPI-00003")

    def test_sequential_po_cn_conversion_numbers(self):
        conn = database.get_db()
        po1 = app.next_po_no(conn)
        po2 = app.next_po_no(conn)
        
        cn1 = app.next_cn_no(conn)
        cn2 = app.next_cn_no(conn)
        
        cnv1 = app.next_conversion_no(conn)
        cnv2 = app.next_conversion_no(conn)
        conn.close()

        self.assertEqual(po1, "PO-00001")
        self.assertEqual(po2, "PO-00002")
        self.assertEqual(cn1, "CN-00001")
        self.assertEqual(cn2, "CN-00002")
        self.assertEqual(cnv1, "CNV-00001")
        self.assertEqual(cnv2, "CNV-00002")

    def test_concurrent_bill_number_generation(self):
        results = []
        lock = threading.Lock()

        def worker():
            conn = database.get_db()
            b_no = app.next_bill_no(conn)
            conn.commit()
            conn.close()
            with lock:
                results.append(b_no)

        threads = [threading.Thread(target=worker) for _ in range(15)]
        for t in threads: t.start()
        for t in threads: t.join()

        # All 15 generated bill numbers must be unique
        self.assertEqual(len(results), 15)
        self.assertEqual(len(set(results)), 15)

if __name__ == '__main__':
    unittest.main()
