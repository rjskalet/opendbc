"""Checks that our camera-harness Suburban preserves factory cruise and steering safety."""
import pytest
from opendbc.car import gen_empty_fingerprint
from opendbc.car.gm.interface import CarInterface
from opendbc.car.gm.values import ALT_ACCS, CAMERA_ACC_CAR, CAR, CarControllerParams, GMSafetyFlags
from opendbc.car.common.conversions import Conversions as CV

SUBURBAN = CAR.CHEVROLET_SUBURBAN_CAMERA_11TH_GEN

@pytest.mark.parametrize("alpha_long", [False, True])
def test_suburban_camera_harness_keeps_factory_acc(alpha_long):
  cp = CarInterface.get_params(SUBURBAN, gen_empty_fingerprint(), [], alpha_long, False, True)
  assert SUBURBAN in CAMERA_ACC_CAR and SUBURBAN in ALT_ACCS
  assert cp.pcmCruise
  assert not cp.openpilotLongitudinalControl and not cp.alphaLongitudinalAvailable
  assert cp.safetyConfigs[0].safetyParam & GMSafetyFlags.HW_CAM.value
  assert not cp.safetyConfigs[0].safetyParam & GMSafetyFlags.HW_CAM_LONG.value
  assert cp.minSteerSpeed == pytest.approx(10 * CV.KPH_TO_MS)
  assert cp.steerActuatorDelay == pytest.approx(0.2)
  assert not cp.dashcamOnly

def test_gm_steer_limits_remain_stock():
  assert CarControllerParams.STEER_MAX == 300
  assert (CarControllerParams.STEER_DELTA_UP, CarControllerParams.STEER_DELTA_DOWN) == (10, 15)
