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
        versionCode = 3
        versionName = "0.6.0"
    }
    buildFeatures { compose = true }
    buildTypes {
        getByName("debug") {
            applicationIdSuffix = ".ui"
            versionNameSuffix = "-ui-preview.3"
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
    debugImplementation("androidx.webkit:webkit:1.11.0")
    implementation(project(":motor"))
    // Esta tela importa Clock/LocalDate diretamente; não depender da
    // dependência implementation interna do motor para compilá-los.
    implementation("org.jetbrains.kotlinx:kotlinx-datetime:0.6.1")
    val compose = "1.7.5"
    implementation("androidx.compose.ui:ui:$compose")
    implementation("androidx.compose.foundation:foundation:$compose")
    implementation("androidx.compose.material3:material3:1.3.1")
    implementation("androidx.activity:activity-compose:1.9.3")
}
