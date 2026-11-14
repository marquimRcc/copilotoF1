# 🏎️ Copiloto F1 - Assistente e Analista de Telemetria

Assistente e analista de telemetria open-source para a franquia de jogos **EA SPORTS F1** (F1 23, F1 24, F1 25 e compatíveis) no PC (Steam).

O Copiloto F1 escuta a telemetria transmitida pelo jogo via rede local (UDP), grava as voltas com precisão e gera **diagnósticos práticos curva a curva** (ponto de frenagem em metros, velocidade de ápice, hesitação de acelerador e marcha correta).

---

## 📋 Funcionalidades

* 📡 **Captura UDP de Alta Performance:** Escuta a porta padrão `20777` com zero dependências externas pesadas (apenas Python padrão `socket` e `struct`).
* 📁 **Exportação Automática para CSV:** Detecta a conclusão de cada volta e gera arquivos estruturados em `data/` com telemetria detalhada de pedal, volante, marcha, velocidade e tempos.
* 🧠 **Diagnóstico Prático sem Gráficos Complicados:** Análise direta do que você precisa ajustar no carro:
  * *"Na Curva 1 de Monza, você freou 22m antes do ponto ideal e perdeu tempo na aproximação."*
  * *"Hesitação de 0.35s para voltar a acelerar na saída da curva."*
  * *"Você fez a curva em 2ª marcha; manter em 3ª melhora a tração."*
* 🏁 **Base de Circuitos Mapeados:** Autódromo de Monza, Interlagos (Brasil), Spa-Francorchamps, Silverstone e Red Bull Ring pré-configurados com suas zonas reais de frenagem e contorno.
* 🖥️ **Totalmente Cross-Platform:** Funciona de forma idêntica no **Windows** e no **Linux**.

---

## ⚙️ Configuração no Jogo (EA SPORTS F1 na Steam)

Para que o Copiloto F1 receba seus dados, ative a saída de telemetria nas configurações do jogo:

1. Abra o jogo **F1** na Steam.
2. Acesse: **Opções do Jogo** ➔ **Configurações** ➔ **Configurações de Telemetria UDP**.
3. Ajuste os seguintes parâmetros:
   * **Telemetria UDP:** `Ativado` (On)
   * **Modo de Transmissão (Broadcast):** `Desativado` (Off)
   * **Endereço IP:** `127.0.0.1`
   * **Porta UDP:** `20777`
   * **Taxa de Envio (Send Rate):** `60Hz` (ou `30Hz`)
   * **Formato UDP:** `2024` (ou o ano correspondente da versão que estiver jogando)

---

## 🚀 Como Usar

### 1. Iniciar o HUD em Tempo Real (Recomendado)
A janela do HUD (450x230) fica sempre no topo (Always on Top) sobre o jogo, alerta o ponto exato de frenagem com o **Layout 1 (Flag Periférica)** e salva as voltas em CSV automaticamente:

* **No Windows:** Dê 2 cliques no arquivo `iniciar_hud.bat` (ou no atalho da Área de Trabalho).
* **Ou via terminal:**
  ```bash
  python src/hud/overlay.py
  ```
* **Dica (Modo Demonstração):** Para testar o visual e a troca de cores sem abrir o jogo:
  ```bash
  python src/hud/overlay.py --demo
  ```

### 2. Criar Atalho na Área de Trabalho (Windows)
Para abrir o HUD direto da sua Área de Trabalho com 1 clique:
```bash
python criar_atalho_windows.py
```

### 3. Analisar a sua Volta
Para gerar o relatório prático em texto de uma volta:

```bash
# Análise individual de uma volta em Monza (track-id 11):
python src/analyzer.py data/volta_01_monza__itália_valida_20261114_094000.csv --track-id 11
```

### 4. Comparar Sua Volta contra sua Melhor Volta (PB) ou Referência
```bash
python src/analyzer.py data/minha_volta.csv --ref-csv data/minha_melhor_volta.csv --track-id 11
```

O analisador exibirá diagnósticos como:
```text
=================================================================
🏎️  DIAGNÓSTICO PRÁTICO DE PILOTAGEM - AUTODROMO NAZIONALE MONZA
=================================================================
⏱️ Tempo da sua volta: 01:21.750
⏱️ Tempo de referência: 01:21.430 (Delta: +0.320s)
-----------------------------------------------------------------

📍 Curva 1-2 (Variante del Rettifilo)
   🛑 FRENAGEM ANTECIPADA: Você freou a 18.0 metros ANTES do ponto ideal (148m vs 130m).
      👉 Recomendação: Confie mais no carro e atrase a freada em direção à placa de referência.
   ✅ Velocidade no Ápice: 74 km/h (bem equilibrada).
   ⚙️ MARCHA: Você fez em 2ª marcha. Fazer em 3ª marcha evita destracionar e melhora a tração na saída.

📍 Curva 4-5 (Variante della Roggia)
   ✅ FRENAGEM NO PONTO: Excelente! Ponto de freio alinhado com a referência.
   ⏱️ HESITAÇÃO NA SAÍDA: 0.32s de carro 'solto' (sem freio e sem acelerador).
      👉 Retome o acelerador mais cedo e de forma progressiva para não perder velocidade de reta.
=================================================================
```

---

## 🧪 Testes Locais e Simulação

Você pode validar todo o funcionamento sem abrir o jogo através do simulador de telemetria incluso:

```bash
# Executa todos os testes unitários e de integração de ponta a ponta:
python -m unittest discover tests
```

---

## 🗺️ Roadmap do Projeto

* [x] **Fase 1:** Parsers de protocolo UDP F1 (Header, CarTelemetry, LapData, Session), Gravador CSV e Simulador.
* [x] **Fase 2 (Núcleo):** Motor de cálculo de ponto de freio, ápice, hesitação e gerador de diagnóstico humano em texto.
* [ ] **Fase 3:** HUD compacto em tempo real (janela flutuante 450x230 com alerta visual "FREIA!") e atalho para Área de Trabalho no Windows.
