plugins { kotlin("jvm") }

kotlin { compilerOptions { jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_11) } }
java { sourceCompatibility = JavaVersion.VERSION_11; targetCompatibility = JavaVersion.VERSION_11 }

dependencies {
    implementation(project(":motor"))
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.7.3")
    testImplementation(kotlin("test-junit5"))
    testRuntimeOnly("org.junit.jupiter:junit-jupiter-engine:5.11.3")
}
tasks.test { useJUnitPlatform() }

// Caminhos de dependências, nunca dados ou credenciais. Usado pelo teste SDK.
tasks.register("classpathDeTeste") {
    dependsOn(tasks.testClasses)
    doLast {
        layout.buildDirectory.file("test-classpath.txt").get().asFile.writeText(sourceSets.test.get().runtimeClasspath.asPath)
    }
}
