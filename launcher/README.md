# F1 25 Time Trial Launcher (POC)

Objetivo: iniciar o F1 25 pela Steam e reduzir a navegação manual até **Time Trial > Brasil (Interlagos)**, sem alterar o HUD ou a telemetria do CopilotoF1.

## Isolamento

Este módulo vive em `launcher/` e nesta branch:

`feature/f125-time-trial-launcher`

Não importar módulos do HUD nem alterar o fluxo UDP/20777. A integração com o Copiloto será opcional e posterior.

## Investigação inicial

- O repositório do CopilotoF1 já recebe telemetria e identifica tipo de sessão/pista, mas não controla menus do jogo.
- A documentação pública do Swofty Launcher descreve addons capazes de alterar dados, layouts de menu e código do jogo. Isso torna possível investigar uma extensão/addon, mas não comprova que exista uma opção pronta para abrir diretamente Time Trial em Interlagos.
- A documentação do Swofty também descreve ambientes de teste do tipo `session` com `mode: time_trial` e `track`. Esse recurso aparece na documentação de testes de addons; não deve ser confundido com uma opção pública de inicialização direta do jogo para o usuário final.
- Até esta investigação, não foi confirmado um argumento oficial da Steam/F1 25 que selecione modo e circuito no boot.

Referências:
- https://github.com/Swofty-Developments/SwoftyLauncher
- https://f1.swofty.net/std/testing.html
- https://f1.swofty.net/reference/cli
- https://f1.swofty.net/design/

## Estratégia

1. **Descoberta, sem modificar o jogo:** identificar AppID, executável, processo, caminhos Steam/EA e opções reais de inicialização.
2. **Prova de lançamento:** abrir o jogo pela Steam e detectar quando o processo está disponível.
3. **Navegação:** avaliar primeiro addon/API documentada do Swofty; se não houver mecanismo confiável, testar automação de teclado/controle com checkpoints e timeout.
4. **Seleção da sessão:** Time Trial e Interlagos, validando o estado antes de confirmar cada etapa.
5. **Integração opcional:** iniciar o CopilotoF1 após a sessão estar carregada.

## Regras de segurança

- Não editar saves, perfil, banco de dados ou arquivos do jogo nesta primeira POC.
- Não sobrescrever arquivos do F1 25.
- Não executar automação enquanto outra sessão do jogo estiver aberta.
- Não enviar comandos cegamente: cada etapa deve ter timeout, log e possibilidade de cancelamento.
- Não automatizar login, autenticação ou telas de terceiros.
- Se a navegação depender de coordenadas frágeis, preferir atalhos/controle com detecção visual e permitir modo manual.

## Critérios de aceite da POC

- Iniciar o F1 25 sem afetar o Copiloto/HUD.
- Detectar processo e janela do jogo.
- Não iniciar uma segunda instância se o jogo já estiver aberto.
- Registrar em log cada etapa e erro.
- Só declarar sucesso quando a sessão ativa for confirmada como Time Trial em Interlagos via telemetria, quando disponível.

## Estado

**Fase 0 — branch e investigação:** branch criada; documentação inicial registrada.
**Próximo passo:** implementar somente a descoberta do ambiente Steam/F1 25 e o monitoramento do processo, sem navegar nos menus ainda.
