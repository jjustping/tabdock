import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.plugin.compose")
}

// Signing key lives outside the repo: ~/.android/tabdock-signing.properties (older name: tabdeck-signing.properties)
// (storeFile=…, storePassword=…, keyAlias=…, keyPassword=…). Same key as the old TabDock app,
// so TabDock installs as an update over it.
val signingProps = Properties().apply {
    val f = listOf("tabdock", "tabdeck").map { File(System.getProperty("user.home"), ".android/$it-signing.properties") }.firstOrNull { it.exists() }
        ?: File(System.getProperty("user.home"), ".android/tabdock-signing.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}

android {
    namespace = "com.jjustping.tabdock"
    compileSdk {
        version = release(37)
    }
    defaultConfig {
        applicationId = "com.jjustping.tabdock"
        minSdk = 26
        targetSdk = 37
        versionCode = 108
        versionName = "0.14.0-beta"
    }
    signingConfigs {
        if (signingProps.isNotEmpty()) {
            create("release") {
                storeFile = File(signingProps.getProperty("storeFile"))
                storePassword = signingProps.getProperty("storePassword")
                keyAlias = signingProps.getProperty("keyAlias")
                keyPassword = signingProps.getProperty("keyPassword")
            }
        }
    }
    buildTypes {
        release {
            optimization { enable = false }
            if (signingProps.isNotEmpty()) signingConfig = signingConfigs.getByName("release")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildFeatures { compose = true }
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2026.02.01"))
    implementation("androidx.activity:activity-compose:1.8.0")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.core:core-ktx:1.10.1")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.6.1")
    // QR scanner for pairing: CameraX + ZXing (no Google Play services needed — fine for RuStore)
    implementation("androidx.camera:camera-camera2:1.4.2")
    implementation("androidx.camera:camera-lifecycle:1.4.2")
    implementation("androidx.camera:camera-view:1.4.2")
    implementation("com.google.zxing:core:3.5.3")
}
