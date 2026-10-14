// Invólucro Android. NUNCA FOI COMPILADO — ver o aviso em motor/build.gradle.kts.
plugins {
    id("com.android.application") version "8.5.2"
    kotlin("android") version "2.0.21"
    id("org.jetbrains.kotlin.plugin.compose") version "2.0.21"
}

android {
    namespace = "com.fintips.app"
    compileSdk = 34
    defaultConfig {
        applicationId = "com.fintips.app"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "0.6.0"
    }
    buildFeatures { compose = true }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
}

dependencies {
    implementation(project(":motor"))
    val compose = "1.7.5"
    implementation("androidx.compose.ui:ui:$compose")
    implementation("androidx.compose.foundation:foundation:$compose")
    implementation("androidx.compose.material3:material3:1.3.1")
    implementation("androidx.activity:activity-compose:1.9.3")
}
