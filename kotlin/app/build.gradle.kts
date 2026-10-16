// Android opcional. assembleDebug validado em 14/10/2026; ver docs/VISUAL.md.
plugins {
    id("com.android.application")
    kotlin("android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "com.fintips.app"
    compileSdk = 34
    defaultConfig {
        applicationId = "com.fintips.app"
        minSdk = 26
        targetSdk = 34
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        versionCode = 12
        versionName = "0.6.0"
    }
    buildFeatures { compose = true }
    // O runner pode definir outro Android user home. Na publicação, apontar
    // explicitamente para o keystore validado, sem depender desse default.
    signingConfigs {
        getByName("debug") {
            providers.environmentVariable("FINTIPS_SIGNING_KEYSTORE").orNull?.let { caminho ->
                storeFile = file(caminho)
                storePassword = "android"
                keyAlias = "androiddebugkey"
                keyPassword = "android"
            }
        }
    }
    buildTypes {
        getByName("debug") {
            val ci = providers.gradleProperty("fintips.ciPreview").orNull == "true"
            applicationIdSuffix = if (ci) ".ci" else ".ui"
            versionNameSuffix = if (ci) "-ci" else "-ui-preview.12"
            manifestPlaceholders["previewLabel"] = if (ci) "FinTips CI" else "FinTips UI"
        }
    }
    // APK de avaliação: a UI revisada roda sem servidor no próprio aparelho.
    // O alvo release continua usando a tela Compose e o motor local.
    sourceSets.getByName("debug").assets.srcDir("../../fintips/web")
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_11)
    }
}

dependencies {
    androidTestImplementation("androidx.test:runner:1.6.2")
    androidTestImplementation("com.squareup.okhttp3:mockwebserver:4.12.0")
    androidTestImplementation("com.squareup.okhttp3:okhttp-tls:4.12.0")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test:core:1.6.1")
    debugImplementation(project(":conector"))
    debugImplementation("androidx.webkit:webkit:1.11.0")
    implementation(project(":motor"))
    // Esta tela importa Clock/LocalDate diretamente; não depender da
    // dependência implementation interna do motor para compilá-los.
    implementation("org.jetbrains.kotlinx:kotlinx-datetime:0.6.1")
    debugImplementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.7.3")
    val compose = "1.7.5"
    implementation("androidx.compose.ui:ui:$compose")
    implementation("androidx.compose.foundation:foundation:$compose")
    implementation("androidx.compose.material3:material3:1.3.1")
    implementation("androidx.activity:activity-compose:1.9.3")
}
