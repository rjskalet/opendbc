from opendbc.car.car_helpers import _normalize_gm_suburban_camera_candidate
from opendbc.car.gm.values import ALT_ACCS, CAMERA_ACC_CAR, CAR


SUBURBAN_VIN = "1GNSKJKJ9KR123456"
YUKON_VIN = "1GKS2CKJ9KR123456"

MATCHING_FINGERPRINT = {
  0: {
    190: 6,
    201: 8,
    209: 7,
    211: 2,
    241: 6,
    304: 1,
    320: 3,
  },
}


def test_suburban_camera_from_yukon_candidate():
  assert _normalize_gm_suburban_camera_candidate("GMC_YUKON", MATCHING_FINGERPRINT, SUBURBAN_VIN) == \
         "CHEVROLET_SUBURBAN_CAMERA_11TH_GEN"


def test_suburban_camera_from_ambiguous_candidate():
  assert _normalize_gm_suburban_camera_candidate(None, MATCHING_FINGERPRINT, SUBURBAN_VIN) == \
         "CHEVROLET_SUBURBAN_CAMERA_11TH_GEN"


def test_suburban_camera_does_not_require_transient_camera_diagnostics():
  # Camera diagnostic request/response IDs are not guaranteed to appear in the short
  # passive fingerprint window. VIN + the stable PT signature must still resolve it.
  fingerprint = {0: MATCHING_FINGERPRINT[0].copy(), 2: {}}
  assert _normalize_gm_suburban_camera_candidate("GMC_YUKON", fingerprint, SUBURBAN_VIN) == \
         "CHEVROLET_SUBURBAN_CAMERA_11TH_GEN"


def test_yukon_vin_stays_yukon():
  assert _normalize_gm_suburban_camera_candidate("GMC_YUKON", MATCHING_FINGERPRINT, YUKON_VIN) == "GMC_YUKON"


def test_wrong_powertrain_signature_does_not_match():
  fingerprint = {bus: messages.copy() for bus, messages in MATCHING_FINGERPRINT.items()}
  fingerprint[0][304] = 8
  assert _normalize_gm_suburban_camera_candidate("GMC_YUKON", fingerprint, SUBURBAN_VIN) == "GMC_YUKON"


def test_suburban_camera_uses_camera_acc_alt_acc_path():
  platform = CAR.CHEVROLET_SUBURBAN_CAMERA_11TH_GEN
  assert platform in CAMERA_ACC_CAR
  assert platform in ALT_ACCS
