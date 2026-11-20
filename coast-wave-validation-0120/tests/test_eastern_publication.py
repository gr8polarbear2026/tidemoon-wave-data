import unittest
from publish_panhandle import validate_eastern_cells
from panhandle_pilot import LOCATIONS
class EasternPublication(unittest.TestCase):
 def bundle(self):
  return {n:{'forecast':[{'ocean_gridpoint':{'lat':30,'lon':-84.1666,'distance_km':5.7}}]} for n in ('stmarks','panacea')}
 def test_old_destinations_preserved(self):
  self.assertTrue({'pensacola','navarre','destin','panamacity','mexicobeach','portsaintjoe','capesanblas','apalachicola','carrabellewest'} <= set(LOCATIONS))
 def test_nearby(self): validate_eastern_cells(self.bundle())
 def test_distant(self):
  d=self.bundle();d['stmarks']['forecast'][0]['ocean_gridpoint']['distance_km']=65
  with self.assertRaises(ValueError):validate_eastern_cells(d)
 def test_mixed(self):
  d=self.bundle();d['stmarks']['forecast'].append({'ocean_gridpoint':{'lat':29.6667,'lon':-84.6666,'distance_km':5}})
  with self.assertRaises(ValueError):validate_eastern_cells(d)
