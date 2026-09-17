plugins {
    kotlin("multiplatform") version "2.0.21"
}

val comAndroid = (findProperty("fintips.android") as String?)?.toBoolean() ?: false

kotlin {
    jvm {
        // O painel desktop e o servidor rodam aqui. O alvo Android entra ao
        // lado, lendo exatamente o mesmo commonMain.
        testRuns["test"].executionTask.configure {
            useJUnitPlatform()
            testLogging {
                // Sem isto o Gradle só diz "FAILED" e engole a mensagem. O
                // harness inteiro existe para nomear qual caso divergiu — de
                // nada adianta se a mensagem não chega a quem lê o log.
                events("failed")
                exceptionFormat = org.gradle.api.tasks.testing.logging.TestExceptionFormat.FULL
                showStackTraces = false
            }
        }
    }

    sourceSets {
        commonMain.dependencies {
            // Uma dependência só, e por um motivo que não existe no Python:
            // data e hora não estão no stdlib do Kotlin. O `datetime` do
            // Python é biblioteca padrão; aqui, não. O resto do motor segue
            // sem dependência — o leitor OFX é escrito à mão, como lá.
            implementation("org.jetbrains.kotlinx:kotlinx-datetime:0.6.1")
        }
        commonTest.dependencies {
            implementation(kotlin("test"))
        }
        jvmTest.dependencies {
            // Só para o harness ler os arquivos de ouro. Usamos a navegação por
            // JsonElement, que não precisa do plugin de compilação — o motor
            // continua sem dependência nenhuma.
            implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.7.3")
        }
    }
}

if (comAndroid) {
    // Placeholder consciente: o alvo Android precisa do plugin AGP e do SDK,
    // que não existem nesta máquina. Quando for ligar, acrescente aqui
    // `androidTarget()` e o bloco `android { ... }`, sem tocar em commonMain.
    logger.lifecycle("alvo Android pedido — configure o AGP e o SDK antes")
}
