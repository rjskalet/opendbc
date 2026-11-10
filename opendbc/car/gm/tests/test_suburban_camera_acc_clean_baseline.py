import unittest
from opendbc.car import gen_empty_fingerprint
from opendbc.car.gm.interface import CarInterface
from opendbc.car.gm.values import CAR, CarControllerParams, GMSafetyFlags
from opendbc.sunnypilot.car.gm.interface_ext import CarInterfaceExt


class TestSuburbanCameraAccCleanBaseline(unittest.TestCase):
  @staticmethod
  def get_params(candidate, alpha_long):
    return CarInterface.get_params(candidate, gen_empty_fingerprint(), [], alpha_long, False, False)

  def assert_stock_camera_acc(self, candidate):
    cp = self.get_params(candidate, alpha_long=True)
    safety_param = cp.safetyConfigs[0].safetyParam

    self.assertFalse(cp.alphaLongitudinalAvailable)
    self.assertFalse(cp.openpilotLongitudinalControl)
    self.assertTrue(cp.pcmCruise)
    self.assertTrue(safety_param & GMSafetyFlags.HW_CAM.value)
    self.assertFalse(safety_param & GMSafetyFlags.HW_CAM_LONG.value)

  def test_alt_accs_ignore_carried_alpha_long(self):
    for candidate in (CAR.CHEVROLET_SUBURBAN_CAMERA_11TH_GEN, CAR.GMC_YUKON):
      with self.subTest(candidate=candidate):
        self.assert_stock_camera_acc(candidate)

  def test_normal_camera_acc_keeps_alpha_long(self):
    cp = self.get_params(CAR.CHEVROLET_SILVERADO, alpha_long=True)
    safety_param = cp.safetyConfigs[0].safetyParam

    self.assertTrue(cp.alphaLongitudinalAvailable)
    self.assertTrue(cp.openpilotLongitudinalControl)
    self.assertFalse(cp.pcmCruise)
    self.assertTrue(safety_param & GMSafetyFlags.HW_CAM.value)
    self.assertTrue(safety_param & GMSafetyFlags.HW_CAM_LONG.value)

  def test_clean_baseline_params(self):
    cp = CarInterface.get_non_essential_params(CAR.CHEVROLET_SUBURBAN_CAMERA_11TH_GEN)

    self.assertAlmostEqual(cp.minSteerSpeed, 10 / 3.6, places=6)
    self.assertFalse(cp.steerAtStandstill)
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


if __name__ == "__main__":
  unittest.main()
