plugins {
    kotlin("multiplatform") version "2.0.21"
}

val comAndroid = (findProperty("fintips.android") as String?)?.toBoolean() ?: false

kotlin {
    jvm {
        // O painel desktop e o servidor rodam aqui. O alvo Android entra ao
        // lado, lendo exatamente o mesmo commonMain.
        testRuns["test"].executionTask.configure { useJUnitPlatform() }
    }

    sourceSets {
        commonMain.dependencies {
            // Deliberadamente vazio por enquanto. O motor do FinTips quase não
            // tem dependência — o parser OFX é escrito à mão e a única
            // biblioteca do lado Python é o PyYAML. Manter assim é o que torna
            // a porta para Kotlin viável em primeiro lugar.
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
