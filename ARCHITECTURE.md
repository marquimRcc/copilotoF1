# 🏛️ Arquitetura Técnica do Copiloto F1

Documento de especificação técnica da arquitetura, fluxo de dados e protocolo UDP do Copiloto F1.

---

## 1. Visão Geral do Sistema

O Copiloto F1 é desenhado em camadas independentes para garantir baixa latência e consumo mínimo de CPU durante o jogo:

```
[ Jogo F1 (Steam) ] ──(UDP 20777)──> [ Camada de Ingestão UDP (Header & Parsers) ]
                                                    │
                           ┌────────────────────────┴────────────────────────┐
                           ▼                                                 ▼
             [ Gravador de Voltas CSV ]                             [ HUD em Tempo Real ]
                           │                                              (Fase 3)
                           ▼
                  [ Arquivos .csv ]
                           │
                           ▼
             [ Motor de Análise Prática ]
                           │
                           ▼
             [ Diagnóstico em Linguagem Humana ]
```

---

## 2. Camadas do Sistema

### 2.1 Camada de Protocolo UDP (`src/packets/`)
* **`header.py`**:
  * Interpreta o cabeçalho padrão de 29 bytes (`<HBBBBBQfIIBB`).
  * Suporta também cabeçalhos legados de 24 bytes para retrocompatibilidade.
  * Identifica o `packet_id`, `session_uid`, `player_car_index` e timestamp da sessão.
* **`car_telemetry.py`**:
  * Interpreta o pacote `PacketCarTelemetryData` (ID 6).
  * Extrai velocidade (km/h), aceleração (0.0 a 1.0), freio (0.0 a 1.0), esterço (-1.0 a 1.0), marcha (-1 a 8), RPM e DRS.
* **`lap_data.py`**:
  * Interpreta o pacote `PacketLapData` (ID 2).
  * Extrai a distância precisa do carro na volta (`m_lapDistance`), tempo atual e tempo da última volta em milissegundos, número da volta e indicador de volta válida/inválida.
* **`session.py`**:
  * Interpreta o pacote `PacketSessionData` (ID 1).
  * Detecta o circuito atual (`track_id`), tipo de sessão (Treino, Classificação, Corrida, Tomada de Tempo) e comprimento total da pista em metros.

### 2.2 Camada de Gravação (`src/recorder.py`)
* Sincroniza as amostras de telemetria com a posição na pista (`lap_distance`) da volta corrente.
* Monitora as transições de volta. Ao cruzar a linha de chegada, compila os dados e exporta para `data/volta_<num>_<circuito>_<status>_<timestamp>.csv`.

### 2.3 Camada de Análise (`src/analyzer.py`)
* Carrega pontos de telemetria indexados pela distância percorrida na pista.
* Divide a volta em zonas de curvas pré-cadastradas (`src/tracks/circuits.py`).
* Calcula as 4 métricas críticas de pilotagem:
  1. **Ponto de Frenagem:** Distância exata onde o pedal de freio ultrapassa o limiar de acionamento (> 20%).
  2. **Velocidade de Ápice:** Valor mínimo de velocidade dentro da zona de contorno.
  3. **Coasting:** Duração em que o piloto permanece sem freio e sem acelerador.
  4. **Retomada de Acelerador:** Distância e progressão até atingir aceleração plena (> 95%).

---

## 3. Especificação do Formato de Arquivo de Dados (CSV)

Os arquivos gerados em `data/` seguem o formato padronizado:

| Coluna | Tipo | Descrição |
|---|---|---|
| `session_time` | Float | Timestamp do jogo em segundos |
| `lap_number` | Int | Número da volta corrente |
| `lap_distance` | Float | Distância percorrida na volta em metros |
| `speed` | Int | Velocidade em km/h |
| `throttle` | Float | Acelerador aplicado (0.00 a 1.00) |
| `brake` | Float | Freio aplicado (0.00 a 1.00) |
| `steer` | Float | Ângulo de esterço (-1.00 a +1.00) |
| `gear` | Int | Marcha engatada (-1=R, 0=N, 1-8) |
| `engine_rpm` | Int | RPM do motor |
| `drs` | Int | 0 = desativado, 1 = ativo |
| `lap_time_ms` | Int | Tempo acumulado na volta em milissegundos |
| `is_valid` | Int | 1 = volta válida, 0 = volta invalidada |
