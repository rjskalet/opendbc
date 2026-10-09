"""Measured per-brand behavior used by the stock-ACC button servo."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ICBMActuationProfile:
  # Fastest discrete tap cadence the stock ECU reliably registers.
  tap_rate_hz: float = 5.
  # Some stock ACCs wait for the dash set speed to stop moving before decelerating.
  decel_needs_stable_setpoint: bool = False


ICBM_ACTUATION_PROFILES: dict[str, ICBMActuationProfile] = {
  'mazda': ICBMActuationProfile(
    tap_rate_hz=5.,
    decel_needs_stable_setpoint=True,
  ),
}

DEFAULT_PROFILE = ICBMActuationProfile()


def get_actuation_profile(brand: str) -> ICBMActuationProfile:
  return ICBM_ACTUATION_PROFILES.get(brand, DEFAULT_PROFILE)
