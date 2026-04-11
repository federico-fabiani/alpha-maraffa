# Firebase
-keep class com.google.firebase.** { *; }
-keep class com.maraffa.beccaccino.data.model.** { *; }

# Hilt
-keep class dagger.hilt.** { *; }
-keep @dagger.hilt.android.HiltAndroidApp class * { *; }
-keep @dagger.hilt.android.AndroidEntryPoint class * { *; }
