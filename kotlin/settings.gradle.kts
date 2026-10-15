// A porta para Kotlin vive em kotlin/, ao lado do motor Python, e não no lugar
// dele. Enquanto o harness diferencial não fechar módulo a módulo, o Python
// continua sendo o produto que funciona — trocar antes disso seria trocar um
// motor testado por um que ninguém conferiu.

pluginManagement {
    repositories {
        gradlePluginPortal()
        mavenCentral()
        google()
    }
}

dependencyResolutionManagement {
    repositories {
        mavenCentral()
        // O repositório do Google só entra quando o alvo Android entrar: é ele
        // que serve o AGP e as bibliotecas androidx. Para o motor puro, tudo
        // que importa está no Maven Central.
        if ((providers.gradleProperty("fintips.android").orNull?.toBoolean() == true)) {
            google()
        }
    }
}

rootProject.name = "fintips"
include(":motor")
include(":conector")

// O app Android é o invólucro: uma Activity que abre a tela do dia. Toda a
// lógica está em `:motor`, então este módulo é fino de propósito — e só existe
// quando o alvo está ligado, porque sem SDK o AGP derruba a configuração.
if ((providers.gradleProperty("fintips.android").orNull?.toBoolean() == true)) {
    include(":app")
}
