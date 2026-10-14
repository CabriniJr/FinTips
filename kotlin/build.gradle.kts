// Kotlin Android precisa enxergar as classes de AGP no mesmo classloader.
// A dependência fica condicionada à flag para manter o build JVM puro.
buildscript {
    val comAndroid = (findProperty("fintips.android") as String?)?.toBoolean() ?: false
    if (comAndroid) {
        repositories { google(); mavenCentral() }
        dependencies { classpath("com.android.tools.build:gradle:8.5.2") }
    }
}

plugins {
    kotlin("multiplatform") version "2.0.21" apply false
    kotlin("plugin.serialization") version "2.0.21" apply false
    kotlin("android") version "2.0.21" apply false
    id("org.jetbrains.kotlin.plugin.compose") version "2.0.21" apply false
}
