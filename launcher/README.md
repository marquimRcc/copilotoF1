# F1 25 Time Trial Launcher (POC)

Objetivo: iniciar o F1 25 pela Steam e reduzir a navegação manual até **Time Trial > Brasil (Interlagos)**, sem alterar o HUD ou a telemetria do CopilotoF1.

## Isolamento

Este módulo vive em `launcher/` e nesta branch:

`feature/f125-time-trial-launcher`

Não importa módulos do HUD nem altera o fluxo UDP/20777. A integração com o Copiloto será opcional e posterior.

## Fase 0 — descoberta e inicialização Steam (implementada)

O primeiro incremento implementa:

- Descoberta do Steam pelo Registro do Windows e caminhos padrão.
- Leitura de `steamapps/libraryfolders.vdf` para localizar bibliotecas adicionais.
- Leitura de `appmanifest_3059520.acf` para localizar a pasta instalada do F1 25.
- Detecção do processo `F1_25.exe` usando `tasklist`.
- Solicitação de inicialização via `steam://run/3059520`.
- Proteção contra iniciar uma segunda instância quando `F1_25.exe` já está em execução.
- Espera configurável pelo processo do jogo.
- Diagnóstico em texto ou JSON.

O AppID 3059520 e o executável de inicialização padrão `EAAntiCheat.GameServiceLauncher.exe` estão documentados no catálogo SteamDB. O launcher usa o protocolo Steam em vez de executar o binário diretamente, preservando o fluxo Steam/EA AntiCheat.

## Como testar no Windows

Na raiz do repositório, com Python 3 instalado:

```powershell
py -3 -m launcher --diagnose
py -3 -m launcher --diagnose --json
py -3 -m launcher --launch --wait 240
```

Também estão disponíveis:

- `launcher/diagnostico.bat`
- `launcher/iniciar_f1_25.bat`

O primeiro comando apenas diagnostica. O segundo solicita o lançamento e aguarda até 240 segundos pelo processo principal do jogo. A confirmação do processo não significa que os menus terminaram de carregar.

## O que ainda não está implementado

- Navegação automática nos menus.
- Seleção automática de Time Trial.
- Seleção automática de Brasil/Interlagos.
- Confirmação de sessão por telemetria.
- Inicialização automática do HUD.

Não foi identificado argumento público documentado da Steam/F1 25 para selecionar modo e pista durante a inicialização. A Steam documenta o uso de opções de inicialização, mas informa que os argumentos dependem do jogo; o catálogo atual do F1 25 mostra apenas a opção padrão e modo VR, não uma opção para Time Trial/Interlagos.

## Segurança e limites

- Não altera saves, perfil, banco de dados ou arquivos do jogo.
- Não executa `F1_25.exe` diretamente nem tenta contornar EA AntiCheat.
- Não envia teclas ou cliques nesta fase.
- Não inicia outra instância se o processo principal já estiver ativo.
- A detecção depende do processo `F1_25.exe`; a janela de carregamento do AntiCheat/EA pode anteceder sua aparição.

## Testes

```powershell
py -3 -m pytest tests/test_launcher_steam.py -q
```

Os testes cobrem ausência da Steam, leitura de bibliotecas VDF e prevenção de instância duplicada. A execução real do jogo precisa ser validada no PC Windows onde F1 25 está instalado.

## Próxima fase

1. Você executa o diagnóstico no seu Windows e compartilha o resultado.
2. Validamos o caminho Steam e a pasta do jogo.
3. Testamos o lançamento e o tempo real de inicialização.
4. Só então desenhamos a automação de menus, com checkpoints e cancelamento.
