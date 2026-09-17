import unittest

from opendbc.car.gm.interface import CarInterface
from opendbc.car.gm.values import CAR, CarControllerParams


class TestSuburbanLateralV2(unittest.TestCase):
  def test_suburban_low_speed_lateral_params(self):
    cp = CarInterface.get_non_essential_params(CAR.CHEVROLET_SUBURBAN_CAMERA_11TH_GEN)

    self.assertEqual(cp.minSteerSpeed, 0.0)
    self.assertTrue(cp.steerAtStandstill)
    self.assertAlmostEqual(cp.steerActuatorDelay, 0.30)
    self.assertEqual(cp.lateralTuning.which(), "torque")

    # V2 must not raise the GM/panda steering torque ceiling.
    self.assertEqual(CarControllerParams.STEER_MAX, 300)


if __name__ == "__main__":
  unittest.main()
