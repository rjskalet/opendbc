"""Fleet integration regression tests for the exact Mazda donor EPS and GM camera-ACC paths.

These tests use synthetic firmware/CAN values; real donor-EPS CAN capture and road
validation remain necessary before this branch is released for vehicle testing.
"""
import unittest

from opendbc.can import CANPacker, CANParser
from opendbc.car import structs
from opendbc.car.common.conversions import Conversions as CV
from opendbc.car.gm.interface import CarInterface as GMInterface
from opendbc.car.gm.values import CAR as GM, CarControllerParams as GMControllerParams, GMSafetyFlags
from opendbc.car.mazda.interface import CarInterface as MazdaInterface
from opendbc.car.mazda.values import (CAR as MAZDA, CarControllerParams as MazdaControllerParams,
                                       MazdaFlags, MazdaSafetyFlags, STEER_TO_ZERO_EPS_FW)


def empty_fingerprint():
  return {bus: {} for bus in range(12)}


def cx9_params(firmware=None, alpha_long=False):
  car_fw = ([] if firmware is None else [
    structs.CarParams.CarFw(ecu=structs.CarParams.Ecu.eps, fwVersion=firmware)
  ])
  return MazdaInterface.get_params(MAZDA.MAZDA_CX9, empty_fingerprint(), car_fw,
                                   alpha_long=alpha_long, is_release=False, docs=False)


class TestFleetCarParams(unittest.TestCase):
  def test_2018_cx9_geometry_and_legacy_firmware_gating(self):
    cp = cx9_params(alpha_long=True)
    self.assertAlmostEqual(cp.wheelbase, 2.93, places=4)
    self.assertAlmostEqual(cp.centerToFront, 2.93 * 0.41, places=4)
    self.assertTrue(cp.dashcamOnly)
    self.assertFalse(cp.flags & MazdaFlags.STEER_TO_ZERO_EPS)
    self.assertFalse(cp.safetyConfigs[0].safetyParam & MazdaSafetyFlags.STEER_TO_ZERO_EPS)
    self.assertFalse(cp.openpilotLongitudinalControl)
    self.assertTrue(cp.pcmCruise)

  def test_unrecognized_eps_firmware_cannot_enable_donor_steering(self):
    cp = cx9_params(firmware=b"UNRECOGNIZED-EPS", alpha_long=True)
    self.assertTrue(cp.dashcamOnly)
    self.assertFalse(cp.flags & MazdaFlags.STEER_TO_ZERO_EPS)
    self.assertFalse(cp.safetyConfigs[0].safetyParam & MazdaSafetyFlags.STEER_TO_ZERO_EPS)

  def test_verified_donor_eps_enables_matching_safety_limits_not_longitudinal(self):
    for fw in STEER_TO_ZERO_EPS_FW:
      with self.subTest(fw=fw):
        cp = cx9_params(firmware=fw, alpha_long=True)
        self.assertFalse(cp.dashcamOnly)
        self.assertAlmostEqual(cp.wheelbase, 2.93, places=4)
        self.assertTrue(cp.flags & MazdaFlags.STEER_TO_ZERO_EPS)
        self.assertTrue(cp.safetyConfigs[0].safetyParam & MazdaSafetyFlags.STEER_TO_ZERO_EPS)
        self.assertFalse(cp.openpilotLongitudinalControl)
        self.assertTrue(cp.pcmCruise)
        self.assertEqual(cp.minSteerSpeed, 0.0)
        limits = MazdaControllerParams(cp)
        self.assertEqual(limits.STEER_MAX, 1200)
        self.assertEqual(limits.STEER_DELTA_UP, 12)
        self.assertEqual(limits.STEER_DELTA_DOWN, 12)
        self.assertAlmostEqual(limits.STEER_UNDELIVERED_ALERT_MIN_SPEED, 12. * CV.MPH_TO_MS)

  def test_suburban_factory_acc_survives_alpha_request(self):
    for alpha_long in (False, True):
      with self.subTest(alpha_long=alpha_long):
        cp = GMInterface.get_params(GM.CHEVROLET_SUBURBAN_CAMERA_11TH_GEN,
                                    empty_fingerprint(), [], alpha_long=alpha_long,
                                    is_release=False, docs=False)
        self.assertTrue(cp.pcmCruise)
        self.assertFalse(cp.openpilotLongitudinalControl)
        self.assertFalse(cp.alphaLongitudinalAvailable)
        self.assertTrue(cp.safetyConfigs[0].safetyParam & GMSafetyFlags.HW_CAM)
        self.assertFalse(cp.safetyConfigs[0].safetyParam & GMSafetyFlags.HW_CAM_LONG)
        self.assertEqual(GMControllerParams.STEER_MAX, 300)
        self.assertEqual(GMControllerParams.STEER_DELTA_UP, 10)
        self.assertEqual(GMControllerParams.STEER_DELTA_DOWN, 15)


class TestMazdaDonorCanSignals(unittest.TestCase):
  def test_donor_eps_feedback_and_fault_bit_synthetic_can_round_trip(self):
    packer = CANPacker("mazda_2017")
    parser = CANParser("mazda_2017", [("STEER_RATE", 100)], 0)
    for n, (torque, fault) in enumerate(((-2000, 0), (-400, 1), (0, 0), (400, 1), (2000, 0)), 1):
      with self.subTest(torque=torque, fault=fault):
        msg = packer.make_can_msg("STEER_RATE", 0, {
          "LKAS_EFFECTIVE": torque, "LKAS_FAULT": fault, "LKAS_BLOCK": 0,
          "LKAS_TRACK_STATE": 0, "LKAS_REQUEST": 0,
        })
        parser.update([n * 10_000_000, [msg]])
        self.assertEqual(parser.vl["STEER_RATE"]["LKAS_EFFECTIVE"], torque)
        self.assertEqual(parser.vl["STEER_RATE"]["LKAS_FAULT"], fault)


if __name__ == "__main__":
  unittest.main()
