<!-- SPDX-FileCopyrightText: 2026 maninblack -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Vision Pilot Services

Two independent Linux ARM64 Aos applications for the separate SDV Vision VM:
Perception runs AutoDrive/AutoSteer/AutoSpeed; Assessment performs time-aware
fusion and shadow interpretation. They consume native platform resources,
not CARLA or vehicle-control interfaces. Results never actuate the vehicle.

This feature checkout is under implementation, not a released or qualified
installer. Source/unit checks do not imply native or full API/UI acceptance.
The existing Brake/Tire Lab is outside its installation and data scope.

## Source checks

Use Python 3.12 or newer and NumPy for isolated array fixtures. In a fresh
checkout, prepare its local test environment once; models, VM and simulator
are not required:

```sh
python3 -m venv .local/test-env
.local/test-env/bin/python -m pip install -r requirements-test.txt
.local/test-env/bin/python -B tools/check.py
```

Model/preprocessing tests use injected sessions and synthetic unit fixtures.
Real models and native identity/quota/IPC checks run only on the dedicated M4.
Weights and reusable ARM64 libraries are external digest-bound build inputs.

## Ownership and dependencies

`common/` contains strict shared DTOs; `apps/perception/` owns inference;
`apps/assessment/` owns upstream fusion/shadow planning. `packaging/aos/`
contains separate release profiles. `dependencies/` pins the accepted contract
and upstream source; `third_party/` preserves selected Apache-2.0 sources.
There is no ROS, CUDA, GUI, vehicle output adapter or continuous recording.

The integration repository owns selected-source enrollment and complete Lab
qualification. The vehicle platform owns Camera Access and the internal OEM
exchange adapter; neither application receives its TLS credentials.
