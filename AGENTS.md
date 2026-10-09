# Repository Working Rules

These rules apply to the entire opendbc repository.

- Never modify `master` or `cx9` directly. All CX-9 development must occur on dedicated test or migration branches.
- Never force-push.
- Preserve the `MAZDA_CX9` platform identity.
- Preserve firmware-gated `STEER_TO_ZERO_EPS` behavior.
- Preserve the existing K0A1, KBST, and KSD5 donor-EPS firmware allowlist unless explicitly instructed otherwise.
- Preserve stock Mazda MRCC. Do not introduce openpilot longitudinal control.
- Do not increase the existing 1200-count Panda safety ceiling or otherwise broaden Panda safety limits.
- Do not weaken driver-torque limits, steering rate limits, real-time limits, controls-allowed enforcement, or CAN TX restrictions.
- Preserve the existing controller speed-dependent torque schedule and EPS ceiling unless explicitly instructed otherwise.
- Preserve the current steer-to-zero delivery protections.
- Explicitly report any change affecting steering, CAN safety, firmware gating, vehicle identification, factory ACC, or lateral tuning.
- Run the Mazda safety and interface regression suites before recommending any merge.
- Do not silently change behavior for other Mazda platforms while modifying the CX-9.
