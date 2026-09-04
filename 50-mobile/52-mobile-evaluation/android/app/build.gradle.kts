plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "com.lunchmarcoly.evaluation52"
    compileSdk = 35
    defaultConfig {
        applicationId = "com.lunchmarcoly.evaluation52"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "1.0.0"
        val localFile = rootProject.file("local.properties")
        val fromFile = if (localFile.exists()) {
            localFile.readLines()
                .firstOrNull { it.startsWith("ld.mobile.key=") }
                ?.substringAfter("=")
                ?.trim()
                .orEmpty()
        } else {
            ""
        }
        val mobileKey = fromFile.ifBlank { System.getenv("LD_MOBILE_KEY").orEmpty() }
        buildConfigField("String", "LD_MOBILE_KEY", "\"${mobileKey.replace("\\", "\\\\").replace("\"", "\\\"")}\"")
    }
    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.10.01")
    implementation(composeBom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    // LaunchDarkly capability: Android mobile SDK
    // https://launchdarkly.com/docs/sdk/client-side/android
    implementation("com.launchdarkly:launchdarkly-android-client-sdk:5.9.1")
    debugImplementation("androidx.compose.ui:ui-tooling")
}
