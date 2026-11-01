<!-- SPDX-FileCopyrightText: 2026 maninblack -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Third-party notices

Selected VisionPilot source is derived from
https://github.com/autowarefoundation/vision_pilot at immutable revision
`e7e5c614832f175f1f9f10a0d0c0df2559ff2c38`, Apache-2.0. Original files at that
revision contain no additional per-file copyright statement. Preserve their
text and the unmodified upstream license. Modifications isolate output types,
remove inference/GUI/vehicle-output dependencies from fusion/planning and
separate actual processing elapsed time from planner horizon time.

The accepted wire-contract projection is generated from the MIT-licensed
`aosedge-sdv-demo` repository, copyright 2026 maninblack. Its source digest and
scope are recorded in `dependencies/integration-contract.json`.

Models and ARM64 runtime libraries are not tracked source. Their exact binary
distribution must carry their own reviewed dependency licenses/SBOM before a
package is accepted; this source notice is not a claim that a binary closure
has already passed that gate.
