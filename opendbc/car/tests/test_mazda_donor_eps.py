import pytest

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


@pytest.mark.parametrize("version", sorted(STEER_TO_ZERO_EPS_FW))
def test_cx9_donor_eps_selects_current_zoompilot_lateral_envelope(version):
  cp = cx9_params(version)
  params = CarControllerParams(cp)

  assert cp.flags & MazdaFlags.STEER_TO_ZERO_EPS
  assert cp.safetyConfigs[0].safetyParam & MazdaSafetyFlags.STEER_TO_ZERO_EPS.value
  assert not cp.dashcamOnly
  assert cp.minSteerSpeed == 0.0
  assert cp.steerActuatorDelay == pytest.approx(0.14)

  assert params.STEER_MAX == 1200
  assert params.STEER_DELTA_UP == 12
  assert params.STEER_DELTA_DOWN == 12
  assert params.STEER_DRIVER_ALLOWANCE == 15
  assert params.STEER_DRIVER_MULTIPLIER == 15
  assert params.STEER_DRIVER_SAMPLES == 10
  assert params.STEER_DRIVER_MARGIN == 2
  assert params.EPS_CEILING_LOOKUP == (
    [8.0, 8.5, 9.4, 10.3, 11.2, 12.1, 13.0, 13.9, 14.5],
    [1148, 1132, 1092, 1048, 1012, 920, 808, 676, 620],
  )


@pytest.mark.parametrize("version", [None, b"UNKNOWN-EPS-FW"])
def test_cx9_without_recognized_donor_eps_stays_conservative(version):
  cp = cx9_params(version)

  assert not (cp.flags & MazdaFlags.STEER_TO_ZERO_EPS)
  assert not (cp.safetyConfigs[0].safetyParam & MazdaSafetyFlags.STEER_TO_ZERO_EPS.value)
  assert cp.dashcamOnly
  assert cp.minSteerSpeed == pytest.approx(LKAS_LIMITS.DISABLE_SPEED * CV.KPH_TO_MS)


def test_cx9_torque_tune_converts_once_from_800_to_flat_1200_scale():
  cp = cx9_params(sorted(STEER_TO_ZERO_EPS_FW)[0])
  raw = get_torque_params()[CAR.MAZDA_CX9]
  tune = cp.lateralTuning.torque

  assert CarControllerParams.TUNE_SCALE == pytest.approx(1.5)
  assert tune.latAccelFactor == pytest.approx(raw["LAT_ACCEL_FACTOR"] * 1.5, rel=1e-6)
  assert tune.friction == pytest.approx(raw["FRICTION"] / 1.5, rel=1e-6)

  before = (tune.latAccelFactor, tune.friction)
  CarInterface.configure_torque_tune(CAR.MAZDA_CX9, cp.lateralTuning)
  assert (tune.latAccelFactor, tune.friction) == pytest.approx(before, rel=1e-6)


def test_cx9_donor_eps_uses_current_speed_bin_seed_table():
  cp = cx9_params(sorted(STEER_TO_ZERO_EPS_FW)[0])
  cfg = get_speed_dep_config_for_car(cp)

  assert cfg["speed_bp"] == [6.5, 9.5, 12.0, 16.4, 21.0, 28.0, 34.5, 37.0]
  assert cfg["seed_version"] == 2
  assert len(cfg["laf_bp"]) == len(cfg["speed_bp"])
  assert len(cfg["friction_bp"]) == len(cfg["speed_bp"])
