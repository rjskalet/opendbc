# Latest SunnyPilot fleet integration — draft

Source: sunnypilot/opendbc master `c0e74738a8068b2fc88c68f1f475887e1dec290f` (matching SunnyPilot `c6e564cdcd68dc6334381ac0d929133b1d824479`).

## Intent
Keep latest SunnyPilot as the base, selectively forward-port **our existing** verified Mazda donor-EPS and Suburban camera-harness implementation. This draft is **not for installation** until the complete paired openpilot build is validated.

## Suburban camera-ACC
- Reinstated `CHEVROLET_SUBURBAN_CAMERA_11TH_GEN` platform with 3.302 m chassis wheelbase, `CAMERA_ACC_CAR` and `ALT_ACCS` memberships.
- Retain original GM 300-count max steering, 10 up / 15 down torque slew, steering floor ~10 km/h.
- Explicitly restore `pcmCruise=True`, `openpilotLongitudinalControl=False` and clear `HW_CAM_LONG` whenever an Alpha longitudinal request comes in; do not let it disable factory ACC.
- Preserve measured Suburban speed-dependent torque seeds; **do not** introduce experimental U-floor modifications.
- Auto-fingerprint still requires verified CAN dataset. Do not invent a Yukon fingerprint or assert automatic recognition.

## Mazda CX-9 donor EPS
- Port firmware-based identification of a verified 2022 donor EPS and the matching steering controls/safety envelope, but keep **factory MRCC** and openpilot longitudinal off.
- Preserve 1200-count normalized steering and 12/12 safety slew as in our existing verified build. Compare against ZoomPilot refinements **after** initial safety tests; do not silently change limits.
- Preserve the original CX-9 torque bins and avoid substituting CX-5 seeds.
- Preserve correct 2.93 m wheelbase and known steering behavior; check process replay before setting final calibration.

## Mazda forward-port details
- Retains original donor EPS firmware list, matching 1200-count/12-up/12-down controller and panda safety envelope, speed-dependent EPS ceiling and LKAS non-delivery guards.
- Latest SunnyPilot's modern panda RX message-match handling and Mazda comma-power documentation are retained.
- Donor-specific state/ICBM extensions are forward-ported independently; native safety and carParams tests added.

## Gates
- Native SunnyPilot unit and build CI + companion opendbc tests
- Panda safety and carParams invariants, donor EPS firmware gating
- Process replay against both vehicles' existing logs
- No merge into master or installation on a Comma 4 until all checks pass

## Donor EPS signal/fault audit (review-stage, not hardware certified)
- STEER_RATE.LKAS_EFFECTIVE updated to documented 10-bit / 4-count scaling from pinned ZoomPilot opendbc. The previous 12-bit 1-count interpretation could misread applied EPS output.
- Add independent EPS `LKAS_FAULT` bit. Verified donor EPS uses this for **permanent** steering faults, while camera-only faults produce **temporary** disengagement and sustained steering non-delivery remains temporary.
- Stock/non-donor Mazda keeps previous camera-based permanent and block-based temporary behavior.
- Synthetic regression tests cover true EPS faults, camera-only errors, expected low-speed blocks, and exact signal definitions.
- **Still required:** compare against actual 2018 CX-9 raw CAN data, including sign/scaling, sensor fault transitions, and steering non-delivery before installation.
