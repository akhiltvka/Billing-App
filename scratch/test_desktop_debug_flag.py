import os
import unittest

class TestDesktopDebugFlag(unittest.TestCase):
    def test_debug_default_off(self):
        if 'MPI_DEBUG' in os.environ:
            del os.environ['MPI_DEBUG']
        DEBUG_MODE = os.environ.get('MPI_DEBUG', '0') == '1'
        self.assertFalse(DEBUG_MODE)

    def test_debug_enabled_when_set(self):
        os.environ['MPI_DEBUG'] = '1'
        DEBUG_MODE = os.environ.get('MPI_DEBUG', '0') == '1'
        self.assertTrue(DEBUG_MODE)

    def test_debug_disabled_when_zero(self):
        os.environ['MPI_DEBUG'] = '0'
        DEBUG_MODE = os.environ.get('MPI_DEBUG', '0') == '1'
        self.assertFalse(DEBUG_MODE)

if __name__ == '__main__':
    unittest.main()
