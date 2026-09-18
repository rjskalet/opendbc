import unittest
from types import SimpleNamespace

from opendbc.car import Bus, structs
from opendbc.car.gm.interface import CarInterface
from opendbc.car.gm.values import CAR, CarControllerParams
from opendbc.sunnypilot.car.gm.carstate_ext import CarStateExt


class TestSuburbanLateralV3(unittest.TestCase):
  def test_suburban_v3_lateral_params(self):
    cp = CarInterface.get_non_essential_params(CAR.CHEVROLET_SUBURBAN_CAMERA_11TH_GEN)

    self.assertEqual(cp.minSteerSpeed, 0.0)
    self.assertTrue(cp.steerAtStandstill)
    self.assertAlmostEqual(cp.steerActuatorDelay, 0.30)
    self.assertEqual(cp.lateralTuning.which(), "torque")
    self.assertAlmostEqual(cp.lateralTuning.torque.latAccelFactor, 0.68)
    self.assertAlmostEqual(cp.lateralTuning.torque.latAccelOffset, -0.26)
    self.assertAlmostEqual(cp.lateralTuning.torque.friction, 0.205)

    # V3 must not raise the GM/panda steering torque ceiling.
    self.assertEqual(CarControllerParams.STEER_MAX, 300)

  def test_suburban_zero_speed_noise_does_not_raise_low_speed_alert(self):
    cp = SimpleNamespace(carFingerprint=CAR.CHEVROLET_SUBURBAN_CAMERA_11TH_GEN, minSteerSpeed=0.0)
    cp_sp = SimpleNamespace(flags=0)
    ret = structs.CarState()
    ret.lowSpeedAlert = True

    CarStateExt(cp, cp_sp).update(ret, {Bus.pt: SimpleNamespace(vl={})})
    self.assertFalse(ret.lowSpeedAlert)


if __name__ == "__main__":
  unittest.main()
