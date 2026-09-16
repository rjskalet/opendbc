from dataclasses import dataclass, field
from enum import IntFlag

from opendbc.car import Bus, CarSpecs, DbcDict, PlatformConfig, Platforms
from opendbc.car.common.conversions import Conversions as CV
from opendbc.car.structs import CarParams
from opendbc.car.docs_definitions import CarHarness, CarDocs, CarParts
from opendbc.car.fw_query_definitions import FwQueryConfig, Request, StdQueries

Ecu = CarParams.Ecu


# Steer torque limits

class CarControllerParams:
  STEER_MAX = 800                # theoretical max_steer 2047
  STEER_DELTA_UP = 10            # torque increase per refresh
  STEER_DELTA_DOWN = 25          # torque decrease per refresh
  STEER_DRIVER_ALLOWANCE = 15    # allowed driver torque before start limiting
  STEER_DRIVER_MULTIPLIER = 1    # weight driver torque
  STEER_DRIVER_FACTOR = 1        # from dbc
  STEER_STEP = 1                 # 100 Hz

  def __init__(self, CP):
    if CP.flags & MazdaFlags.STEER_TO_ZERO_EPS:
      # ZoomPilot's measured 2022 CX-5 EPS envelope. Keep controller and panda synchronized.
      self.STEER_MAX = 1200
      self.STEER_DELTA_UP = 12
      self.STEER_DELTA_DOWN = 12
      self.STEER_DRIVER_MULTIPLIER = 15
      self.STEER_DRIVER_SAMPLES = 10
      self.STEER_DRIVER_MARGIN = 2
      self.STEER_MAX_LOOKUP = ([0., 14.2, 14.5], [1200, 1200, 800])
      self.EPS_CEILING_LOOKUP = ([8.0, 8.5, 9.4, 10.3, 11.2, 12.1, 13.0, 13.9, 14.5],
                                 [1148, 1132, 1092, 1048, 1012, 920, 808, 676, 620])
      self.STEER_UNDELIVERED_MIN = 200
      self.STEER_UNDELIVERED_FRAMES = 20
      self.STEER_UNDELIVERED_ALERT_FRAMES = 80
      self.STEER_UNDELIVERED_ALERT_MIN_SPEED = 12. * CV.MPH_TO_MS
      self.STEER_UNDELIVERED_ALERT_ORIGIN_SPEED = 1.0
    else:
      self.STEER_MAX = 800
      self.STEER_DELTA_UP = 10
      self.STEER_DELTA_DOWN = 25
      self.STEER_DRIVER_MULTIPLIER = 1
      self.STEER_DRIVER_SAMPLES = 1
      self.STEER_DRIVER_MARGIN = 0


@dataclass
class MazdaCarDocs(CarDocs):
  package: str = "All"
  car_parts: CarParts = field(default_factory=CarParts.common([CarHarness.mazda]))


@dataclass(frozen=True, kw_only=True)
class MazdaCarSpecs(CarSpecs):
  tireStiffnessFactor: float = 0.7  # not optimized yet


class MazdaFlags(IntFlag):
  # Gen 1 hardware: same CAN messages and same camera.
  GEN1 = 1
  # EPS firmware that can steer to zero speed (2022 CX-5 donor rack family).
  STEER_TO_ZERO_EPS = 2


class MazdaSafetyFlags(IntFlag):
  # Selects the matching steer-to-zero torque envelope in panda safety.
  STEER_TO_ZERO_EPS = 2


@dataclass
class MazdaPlatformConfig(PlatformConfig):
  dbc_dict: DbcDict = field(default_factory=lambda: {Bus.pt: 'mazda_2017'})
  flags: int = MazdaFlags.GEN1


class CAR(Platforms):
  MAZDA_CX5 = MazdaPlatformConfig(
    [MazdaCarDocs("Mazda CX-5 2017-21")],
    MazdaCarSpecs(mass=3655 * CV.LB_TO_KG, wheelbase=2.7, steerRatio=15.5)
  )
  MAZDA_CX9 = MazdaPlatformConfig(
    [MazdaCarDocs("Mazda CX-9 2016-20")],
    # Keep stock SunnyPilot geometry for this first EPS-only validation package.
    MazdaCarSpecs(mass=4217 * CV.LB_TO_KG, wheelbase=3.1, steerRatio=17.6)
  )
  MAZDA_3 = MazdaPlatformConfig(
    [MazdaCarDocs("Mazda 3 2017-18")],
    MazdaCarSpecs(mass=2875 * CV.LB_TO_KG, wheelbase=2.7, steerRatio=14.0)
  )
  MAZDA_6 = MazdaPlatformConfig(
    [MazdaCarDocs("Mazda 6 2017-20")],
    MazdaCarSpecs(mass=3443 * CV.LB_TO_KG, wheelbase=2.83, steerRatio=15.5)
  )
  MAZDA_CX9_2021 = MazdaPlatformConfig(
    [MazdaCarDocs("Mazda CX-9 2021-23", video="https://youtu.be/dA3duO4a0O4")],
    MAZDA_CX9.specs
  )
  MAZDA_CX5_2022 = MazdaPlatformConfig(
    [MazdaCarDocs("Mazda CX-5 2022-25")],
    MAZDA_CX5.specs,
  )


class LKAS_LIMITS:
  STEER_THRESHOLD = 15
  DISABLE_SPEED = 45    # kph
  ENABLE_SPEED = 52     # kph


# Keep this synchronized with ZoomPilot's steer-to-zero EPS firmware set.
STEER_TO_ZERO_EPS_FW = {
  b'K0A1-3210X-A-00\x00\x00\x00\x00\x00\x00\x00\x00\x00',
  b'KBST-3210X-A-00\x00\x00\x00\x00\x00\x00\x00\x00\x00',
  b'KSD5-3210X-C-00\x00\x00\x00\x00\x00\x00\x00\x00\x00',
}


class Buttons:
  NONE = 0
  SET_PLUS = 1
  SET_MINUS = 2
  RESUME = 3
  CANCEL = 4


FW_QUERY_CONFIG = FwQueryConfig(
  fw_version_regex=br"[A-Z0-9-]{11,16}\x00{8,13}",
  requests=[
    Request(
      [StdQueries.MANUFACTURER_SOFTWARE_VERSION_REQUEST],
      [StdQueries.MANUFACTURER_SOFTWARE_VERSION_RESPONSE],
      bus=0,
    ),
  ],
)

DBC = CAR.create_dbc_map()
