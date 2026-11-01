// SPDX-FileCopyrightText: 2026 maninblack
// SPDX-License-Identifier: Apache-2.0
#pragma once
// The functional service exports bounded typed results, not upstream debug
// telemetry. This shim leaves computation unchanged and prevents GUI/log deps.
#define VP_INFO(...) ((void)0)
