# Vision service development

Use the accepted SDV Lab native-service packet and executable contract pinned
in `dependencies/integration-contract.json`. Two independent Aos applications;
no third AI service, CARLA/VISS/Cloud/actuator access or application credentials.
Keep raw inference in Perception and upstream fusion/shadow interpretation in
Assessment. Native Aos owns identity, resources, quotas and service lifecycle.

All compile/package/cache work is on the selected external SSD. Only isolated
unit tests run on the development Mac; real models, native/API/UI checks use
the existing M4 Vision VM. Preserve its Unit, disks, store and data and every
retained VDP/Brake/Tire instance. Do not reset/reprovision or rebuild CARLA/Main
Factory. Use scenario-owned normal cleanup, preserve shared Docker and caches.

Original code is Apache-2.0, copyright `maninblack`; preserve upstream notices
and identify modifications. Never track models, binaries, keys or runtime data.
Use `apply_patch`, targeted tests, exact upstream/dependency pins and no blind
external retries. Commit only this repository's owned work; do not merge Main
or publicly release artifacts implicitly. Do not spawn other agents.
