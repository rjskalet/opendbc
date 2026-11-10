import unittest

from opendbc.car.values import PLATFORMS
from opendbc.car.tests.routes import non_tested_cars, routes
from opendbc.car.tests.routes_suburban import suburban_routes


class TestRoutes(unittest.TestCase):
  def test_test_route_present(self):
    tested_platforms = [r.car_model for r in routes + suburban_routes]
    for platform in PLATFORMS.keys():
      with self.subTest(platform=platform):
        assert platform in set(tested_platforms) | set(non_tested_cars), \
          f"Missing test route for {platform}. Add a route to opendbc/car/tests/routes.py"
