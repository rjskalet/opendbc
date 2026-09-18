import unittest
from types import SimpleNamespace

from opendbc.car import Bus, structs
from opendbc.car.gm.interface import CarInterface
from opendbc.car.gm.values import CAR, CarControllerParams
from opendbc.sunnypilot.car.gm.carstate_ext import CarStateExt
from opendbc.sunnypilot.car.gm.interface_ext import CarInterfaceExt


class TestSuburbanCameraAccCleanBaseline(unittest.TestCase):
  def test_clean_baseline_params(self):
    cp = CarInterface.get_non_essential_params(CAR.CHEVROLET_SUBURBAN_CAMERA_11TH_GEN)

    self.assertEqual(cp.minSteerSpeed, 0.0)
    self.assertTrue(cp.steerAtStandstill)
    self.assertAlmostEqual(cp.steerActuatorDelay, 0.20)
    self.assertFalse(cp.openpilotLongitudinalControl)
    self.assertTrue(cp.pcmCruise)

    self.assertEqual(cp.lateralTuning.which(), "torque")
    self.assertAlmostEqual(cp.lateralTuning.torque.latAccelFactor, 1.20)
    self.assertAlmostEqual(cp.lateralTuning.torque.latAccelOffset, 0.0)
    self.assertAlmostEqual(cp.lateralTuning.torque.friction, 0.26)

    self.assertEqual(CarControllerParams.STEER_MAX, 300)
    self.assertEqual(CarControllerParams.STEER_DELTA_UP, 10)
    self.assertEqual(CarControllerParams.STEER_DELTA_DOWN, 15)

  def test_extension_does_not_replace_suburban_tune(self):
    cp = CarInterface.get_non_essential_params(CAR.CHEVROLET_SUBURBAN_CAMERA_11TH_GEN)

    class NoCrossPlatformTune:
      @staticmethod
      def configure_torque_tune(*args, **kwargs):
        raise AssertionError("SunnyPilot extension must not replace the Suburban calibration")

    CarInterfaceExt(cp, NoCrossPlatformTune)

    self.assertAlmostEqual(cp.steerActuatorDelay, 0.20)
    self.assertAlmostEqual(cp.lateralTuning.torque.latAccelFactor, 1.20)
    self.assertAlmostEqual(cp.lateralTuning.torque.latAccelOffset, 0.0)
    self.assertAlmostEqual(cp.lateralTuning.torque.friction, 0.26)

  def test_zero_speed_noise_does_not_raise_low_speed_alert(self):
    cp = SimpleNamespace(carFingerprint=CAR.CHEVROLET_SUBURBAN_CAMERA_11TH_GEN, minSteerSpeed=0.0)
    cp_sp = SimpleNamespace(flags=0)
    ret = structs.CarState()
    ret.lowSpeedAlert = True

    CarStateExt(cp, cp_sp).update(ret, {Bus.pt: SimpleNamespace(vl={})})
    self.assertFalse(ret.lowSpeedAlert)


if __name__ == "__main__":
  unittest.main()
