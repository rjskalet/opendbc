from opendbc.car.car_helpers import interfaces
from opendbc.car.gm.values import CAR, CarControllerParams
from opendbc.sunnypilot.car.interfaces import get_speed_dep_config_for_car


SUBURBAN = CAR.CHEVROLET_SUBURBAN_CAMERA_11TH_GEN


def suburban_params():
  return interfaces[SUBURBAN].get_non_essential_params(SUBURBAN)


def test_suburban_live_table_v1_config():
  cfg = get_speed_dep_config_for_car(suburban_params())
  assert cfg == {
    "speed_bp": [6.5, 9.5, 12.0, 16.4, 21.0, 28.0, 35.0],
    "laf_bp": [0.680, 0.680, 0.680, 0.435, 0.469, 0.378, 0.413],
    "friction_bp": [0.205, 0.205, 0.205, 0.195, 0.208, 0.181, 0.135],
    "seed_version": 1,
  }


def test_suburban_authority_and_factory_acc_unchanged():
  cp = suburban_params()
  limits = CarControllerParams(cp)
  assert limits.STEER_MAX == 300
  assert limits.STEER_DELTA_UP == 10
  assert limits.STEER_DELTA_DOWN == 15
  assert limits.STEER_STEP == 3
  assert cp.pcmCruise
  assert not cp.openpilotLongitudinalControl
