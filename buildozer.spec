[app]

# (str) Title of your application
title = مدير كرة القدم

# (str) Package name
package.name = footballmanager

# (str) Package domain (needed for android packaging)
package.domain = org.test

# (str) Source files where the let's go (relative to directory of spec)
source.dir = .

# (list) Source files to include (let's include py,png,jpg,kv,atlas,db)
source.include_exts = py,png,jpg,kv,atlas,db

# (str) Application versioning
version = 1.0.0

# (list) Application requirements
# Add your dependencies here, separated by commas
requirements = python3,kivy,kivymd,arabic-reshaper,python-bidi,pillow

# (list) Custom source folders for python extensions
# source.include_patterns = assets/*,images/*.png

# (str) Supported orientations
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (list) Permissions
android.permissions = WRITE_EXTERNAL_STORAGE

# (int) Target Android API, should be as high as possible.
android.api = 33

# (int) Minimum API your APK will support.
android.minapi = 24

# (list) Architectures to build for
android.archs = arm64-v8a

# (str) NDK version to use
android.ndk = 25b

# (str) Extra cflags to suppress warnings/errors during compilation of old libraries like libwebp
android.extra_cflags = -w

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1
 
