import unittest

from opendbc.car import gen_empty_fingerprint, structs
from opendbc.car.common.conversions import Conversions as CV
from opendbc.car.interfaces import get_torque_params
from opendbc.car.mazda.interface import CarInterface
from opendbc.car.mazda.values import (
  CAR, LKAS_LIMITS, STEER_TO_ZERO_EPS_FW, CarControllerParams, MazdaFlags, MazdaSafetyFlags,
)
from opendbc.sunnypilot.car.interfaces import get_speed_dep_config_for_car


Ecu = structs.CarParams.Ecu


def eps_fw(version: bytes) -> list[structs.CarParams.CarFw]:
  fw = structs.CarParams.CarFw()
  fw.ecu = Ecu.eps
  fw.address = 0x730
  fw.subAddress = 0
  fw.fwVersion = version
  return [fw]


def cx9_params(version: bytes | None):
  return CarInterface.get_params(
    CAR.MAZDA_CX9,
    gen_empty_fingerprint(),
    [] if version is None else eps_fw(version),
    alpha_long=False,
    is_release=False,
    docs=False,
  )


class TestMazdaCx9DonorEps(unittest.TestCase):
  def test_donor_eps_selects_current_zoompilot_lateral_envelope(self):
    expected_ceiling = (
      [8.0, 8.5, 9.4, 10.3, 11.2, 12.1, 13.0, 13.9, 14.5],
      [1148, 1132, 1092, 1048, 1012, 920, 808, 676, 620],
    )

    for version in sorted(STEER_TO_ZERO_EPS_FW):
      with self.subTest(version=version):
        cp = cx9_params(version)
        params = CarControllerParams(cp)

        self.assertTrue(cp.flags & MazdaFlags.STEER_TO_ZERO_EPS)
        self.assertTrue(cp.safetyConfigs[0].safetyParam & MazdaSafetyFlags.STEER_TO_ZERO_EPS.value)
        self.assertFalse(cp.dashcamOnly)
        self.assertEqual(cp.minSteerSpeed, 0.0)
        self.assertAlmostEqual(cp.steerActuatorDelay, 0.14)

        self.assertEqual(params.STEER_MAX, 1200)
        self.assertEqual(params.STEER_DELTA_UP, 12)
        self.assertEqual(params.STEER_DELTA_DOWN, 12)
        self.assertEqual(params.STEER_DRIVER_ALLOWANCE, 15)
        self.assertEqual(params.STEER_DRIVER_MULTIPLIER, 15)
        self.assertEqual(params.STEER_DRIVER_SAMPLES, 10)
        self.assertEqual(params.STEER_DRIVER_MARGIN, 2)
        self.assertEqual(params.EPS_CEILING_LOOKUP, expected_ceiling)

  def test_without_recognized_donor_eps_stays_conservative(self):
    for version in (None, b"UNKNOWN-EPS-FW"):
      with self.subTest(version=version):
        cp = cx9_params(version)

        self.assertFalse(cp.flags & MazdaFlags.STEER_TO_ZERO_EPS)
        self.assertFalse(cp.safetyConfigs[0].safetyParam & MazdaSafetyFlags.STEER_TO_ZERO_EPS.value)
        self.assertTrue(cp.dashcamOnly)
        self.assertAlmostEqual(cp.minSteerSpeed, LKAS_LIMITS.DISABLE_SPEED * CV.KPH_TO_MS)

  def test_torque_tune_converts_once_from_800_to_flat_1200_scale(self):
    cp = cx9_params(sorted(STEER_TO_ZERO_EPS_FW)[0])
    raw = get_torque_params()[CAR.MAZDA_CX9]
    tune = cp.lateralTuning.torque

    self.assertAlmostEqual(CarControllerParams.TUNE_SCALE, 1.5)
    self.assertAlmostEqual(tune.latAccelFactor, raw["LAT_ACCEL_FACTOR"] * 1.5, places=6)
    self.assertAlmostEqual(tune.friction, raw["FRICTION"] / 1.5, places=6)

    before = (tune.latAccelFactor, tune.friction)
    CarInterface.configure_torque_tune(CAR.MAZDA_CX9, cp.lateralTuning)
    # configure_torque_tune reinitializes the capnp union; reread the active torque member.
    tune_after = cp.lateralTuning.torque
    self.assertAlmostEqual(tune_after.latAccelFactor, before[0], places=6)
    self.assertAlmostEqual(tune_after.friction, before[1], places=6)

  def test_donor_eps_uses_current_speed_bin_seed_table(self):
    cp = cx9_params(sorted(STEER_TO_ZERO_EPS_FW)[0])
    cfg = get_speed_dep_config_for_car(cp)

    self.assertEqual(cfg["speed_bp"], [6.5, 9.5, 12.0, 16.4, 21.0, 28.0, 34.5, 37.0])
    self.assertEqual(cfg["seed_version"], 2)
    self.assertEqual(len(cfg["laf_bp"]), len(cfg["speed_bp"]))
    self.assertEqual(len(cfg["friction_bp"]), len(cfg["speed_bp"]))


if __name__ == "__main__":
  unittest.main()
