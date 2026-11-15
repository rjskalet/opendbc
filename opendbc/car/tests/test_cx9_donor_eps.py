"""Fleet regression: donor EPS is recognized only when firmware is verified."""
from types import SimpleNamespace

from opendbc.car import gen_empty_fingerprint, structs
from opendbc.car.mazda.interface import CarInterface
from opendbc.car.mazda.values import CAR, CarControllerParams, MazdaFlags, MazdaSafetyFlags, STEER_TO_ZERO_EPS_FW


def _params(fw):
  versions = [] if fw is None else [SimpleNamespace(ecu=structs.CarParams.Ecu.eps, fwVersion=fw)]
  return CarInterface.get_params(CAR.MAZDA_CX9, gen_empty_fingerprint(), versions,
                                 alpha_long=False, is_release=False, docs=False)


def test_donor_eps_uses_measured_safety_envelope_and_stock_mrcc():
  cp = _params(next(iter(STEER_TO_ZERO_EPS_FW)))
  limits = CarControllerParams(cp)
  assert cp.flags & MazdaFlags.STEER_TO_ZERO_EPS
  assert cp.safetyConfigs[0].safetyParam & MazdaSafetyFlags.STEER_TO_ZERO_EPS
  assert cp.wheelbase == 2.93
  assert cp.minSteerSpeed == 0.
  assert not cp.dashcamOnly
  assert cp.pcmCruise and not cp.openpilotLongitudinalControl
  assert limits.STEER_MAX == 1200
  assert (limits.STEER_DELTA_UP, limits.STEER_DELTA_DOWN) == (12, 12)


def test_without_verified_eps_only_stock_legacy_capabilities_remain():
  cp = _params(None)
  limits = CarControllerParams(cp)
  assert not (cp.flags & MazdaFlags.STEER_TO_ZERO_EPS)
  assert not (cp.safetyConfigs[0].safetyParam & MazdaSafetyFlags.STEER_TO_ZERO_EPS)
  assert cp.dashcamOnly
  assert cp.minSteerSpeed > 0.
  assert cp.pcmCruise and not cp.openpilotLongitudinalControl
  assert limits.STEER_MAX == 800
  assert (limits.STEER_DELTA_UP, limits.STEER_DELTA_DOWN) == (10, 25)
