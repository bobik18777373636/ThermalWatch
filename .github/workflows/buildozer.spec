[app]

# ── Identity ──────────────────────────────────────────────────────────────────
title           = ThermalWatch
package.name    = thermalwatch
package.domain  = org.thermalwatch
source.dir      = .
source.include_exts = py,png,jpg,kv,atlas,ttf

version         = 1.0

# ── Requirements ──────────────────────────────────────────────────────────────
# Keep minimal — no numpy/pillow needed for this app.
requirements = python3,kivy==2.3.0,kivymd

# ── Orientation & window ──────────────────────────────────────────────────────
orientation     = portrait
fullscreen      = 0

# ── Android target (Samsung A50 runs Android 10, arm64) ───────────────────────
android.api             = 31
android.minapi          = 24
android.ndk             = 25b
android.sdk             = 33
android.archs           = arm64-v8a

# ── Permissions ───────────────────────────────────────────────────────────────
# FOREGROUND_SERVICE lets us keep polling even when screen dims.
android.permissions = \
    FOREGROUND_SERVICE, \
    RECEIVE_BOOT_COMPLETED

# ── Build extras ──────────────────────────────────────────────────────────────
android.gradle_dependencies =
android.enable_androidx    = True

# Allow spawning shell commands (needed for rish)
android.add_jars            =
android.add_src             =

# ── Buildozer / p4a internals ─────────────────────────────────────────────────
[buildozer]

# Log verbosity: 0 = quiet, 1 = info, 2 = debug
log_level = 1

# Where build artefacts land (relative to project root)
build_dir    = ./.buildozer
bin_dir      = ./bin

# Warn on version mismatch but don't abort
warn_on_root = 1
