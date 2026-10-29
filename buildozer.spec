[app]
title = مدير كرة القدم
package.name = footballmanager
package.domain = org.test
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,db
version = 1.0.0
requirements = python3,kivy,kivymd,arabic-reshaper,python-bidi,pillow
orientation = portrait
fullscreen = 0
android.permissions = WRITE_EXTERNAL_STORAGE
android.api = 33
android.minapi = 24
android.archs = arm64-v8a
android.ndk = 23b
# أضف هذه الخيارات في ملف buildozer.spec لتجاوز أخطاء الترجمة الصارمة
android.extra_cflags = -Wno-error=xor-used-as-pow -Wno-error=unused-command-line-argument
