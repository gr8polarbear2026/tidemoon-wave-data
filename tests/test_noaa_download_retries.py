import unittest
from unittest.mock import Mock
import requests
from noaa_validator import get_grib_with_retries


def response(status):
    r = Mock(spec=requests.Response)
    r.status_code = status
    if status >= 400:
        r.raise_for_status.side_effect = requests.HTTPError(
            f'{status} Service Unavailable', response=r)
    else:
        r.raise_for_status.return_value = None
    return r


class NoaaRetryTests(unittest.TestCase):
    def test_transient_503_recovers(self):
        session = Mock()
        good = response(200)
        session.get.side_effect = [response(503), good]
        delays = []
        self.assertIs(get_grib_with_retries(session, 'https://example.invalid', sleep=delays.append), good)
        self.assertEqual(delays, [12])
        self.assertEqual(session.get.call_count, 2)

    def test_transient_503_exhausts(self):
        session = Mock()
        session.get.side_effect = [response(503), response(503), response(503)]
        delays = []
        with self.assertRaises(requests.HTTPError):
            get_grib_with_retries(session, 'https://example.invalid', sleep=delays.append)
        self.assertEqual(delays, [12, 24])
        self.assertEqual(session.get.call_count, 3)

    def test_permanent_404_not_retried(self):
        session = Mock()
        session.get.return_value = response(404)
        delays = []
        with self.assertRaises(requests.HTTPError):
            get_grib_with_retries(session, 'https://example.invalid', sleep=delays.append)
        self.assertEqual(delays, [])
        self.assertEqual(session.get.call_count, 1)


if __name__ == '__main__':
    unittest.main()
