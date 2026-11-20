import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from regional_panhandle import HOURS, UTC, LOCATIONS, regional_url, cycle_time
from publish_panhandle import complete_previous, verify_cells, select_cycle, prepare


class ExtendedPanhandle(unittest.TestCase):
    def test_native_hourly_schedule(self):
        self.assertEqual(HOURS, tuple(range(3,73)))
        self.assertEqual(len(LOCATIONS)*len(HOURS),770)
        self.assertIn('f072.grib2', regional_url('20261120','00',72))
        self.assertIn('leftlon=-87.89', regional_url('20261120','00',72))

    def test_model_cycle_utc(self):
        self.assertEqual((cycle_time('20261120','18')+dt.timedelta(hours=72)).isoformat(),
                         '2026-11-23T18:00:00+00:00')

    def test_stale_cycle_not_eligible(self):
        now=dt.datetime(2026,11,20,22,0,tzinfo=UTC)
        with patch('publish_panhandle.index_ready',return_value=False) as probe:
            with self.assertRaisesRegex(RuntimeError,'retained'):
                select_cycle(Mock(),now,None)
            self.assertEqual([c.args[2] for c in probe.call_args_list],['18','12','06'])

    def test_same_complete_cycle_skip(self):
        now=dt.datetime(2026,11,20,8,0,tzinfo=UTC)
        with patch('publish_panhandle.complete_previous',return_value=True), patch('publish_panhandle.index_ready') as probe:
            self.assertIsNone(select_cycle(Mock(),now,Path('previous')))
            probe.assert_not_called()

    def test_missing_or_corrupt_payload_keeps_prior_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'stage'
            path.mkdir()
            prior=path/'portsaintjoe.json'
            prior.write_bytes(b'prior verified bytes')
            invalid=Path(folder)/'bad.grib2'
            invalid.write_bytes(b'<html>fake</html>')
            now=dt.datetime.now(UTC)
            for injected in (invalid, Path(folder)/'missing'):
                with self.assertRaises((ValueError,OSError)):
                    prepare('20261120','00',lambda _:injected,path,now)
                self.assertEqual(prior.read_bytes(),b'prior verified bytes')
                self.assertEqual(list(path.iterdir()),[prior])

    def test_reject_all_location_cell_change(self):
        with self.assertRaisesRegex(ValueError,'mixed'):
            verify_cells({'pensacola':{'forecast':[
                {'ocean_gridpoint':{'lat':29.5,'lon':-85.0,'distance_km':7}},
                {'ocean_gridpoint':{'lat':29.5,'lon':-85.1,'distance_km':10}},
            ]}},('pensacola',))


if __name__=='__main__':
    unittest.main()
