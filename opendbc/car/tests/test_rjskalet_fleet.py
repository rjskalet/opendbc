"""Integration invariants for the donor-EPS CX-9 and camera-harness Suburban."""
from pathlib import Path
import tomllib

import pytest

from opendbc.car import gen_empty_fingerprint
from opendbc.car.common.conversions import Conversions as CV
from opendbc.car.gm.interface import CarInterface as GMInterface
from opendbc.car.gm.values import ALT_ACCS, CAMERA_ACC_CAR, CAR as GM, CarControllerParams as GMController, GMSafetyFlags
from opendbc.car.mazda.tests.conftest import car_params, eps_fw
from opendbc.car.mazda.values import CAR as Mazda, CarControllerParams as MazdaController, MazdaFlags

SUBURBAN = GM.CHEVROLET_SUBURBAN_CAMERA_11TH_GEN
SWAPPED_EPS_FW = b'KSD5-3210X-C-00' + b'\x00' * 9
TORQUE_DATA = Path(__file__).resolve().parent.parent / 'torque_data'


@pytest.mark.parametrize('alpha_long', [False, True])
def test_suburban_preserves_factory_cruise_when_alpha_requested(alpha_long):
  cp = GMInterface.get_params(SUBURBAN, gen_empty_fingerprint(), [], alpha_long=alpha_long,
                              is_release=False, docs=True)
  assert SUBURBAN in CAMERA_ACC_CAR and SUBURBAN in ALT_ACCS
  assert cp.pcmCruise and not cp.openpilotLongitudinalControl and not cp.alphaLongitudinalAvailable
  assert cp.safetyConfigs[0].safetyParam & GMSafetyFlags.HW_CAM.value
  assert not cp.safetyConfigs[0].safetyParam & GMSafetyFlags.HW_CAM_LONG.value
  assert cp.minSteerSpeed == pytest.approx(10 * CV.KPH_TO_MS)
  assert cp.steerActuatorDelay == pytest.approx(0.2)
  assert not cp.dashcamOnly
  assert GMController.STEER_MAX == 300
  assert (GMController.STEER_DELTA_UP, GMController.STEER_DELTA_DOWN) == (10, 15)


def test_cx9_donor_eps_retains_stock_mrcc_and_zoompilot_safety_envelope():
  cp = car_params(Mazda.MAZDA_CX9, car_fw=eps_fw(SWAPPED_EPS_FW), alpha_long=True)
  assert cp.flags & MazdaFlags.STEER_TO_ZERO_EPS
  assert cp.pcmCruise and not cp.openpilotLongitudinalControl and not cp.alphaLongitudinalAvailable
  assert cp.minSteerSpeed == 0.0
  assert not cp.dashcamOnly
  controller = MazdaController(cp)
  assert controller.STEER_MAX == 1200
  assert (controller.STEER_DELTA_UP, controller.STEER_DELTA_DOWN) == (10, 10)


def test_measured_torque_seeds_are_vehicle_specific():
  with (TORQUE_DATA / 'speed_dependent.toml').open('rb') as file:
    data = tomllib.load(file)
  assert data['MAZDA_CX9']['substitute'] == 'MAZDA_CX9_2021'
  assert data['MAZDA_CX9']['requires_steer_to_zero']
  assert data['CHEVROLET_SUBURBAN_CAMERA_11TH_GEN']['seed_version'] == 1
  with (TORQUE_DATA / 'override.toml').open('rb') as file:
    override = tomllib.load(file)
  assert override['CHEVROLET_SUBURBAN_CAMERA_11TH_GEN'] == [1.2, 2.5, 0.26]
