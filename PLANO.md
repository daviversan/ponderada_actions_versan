# Plano — Experimento CI/CD com GitHub Actions (MVP)

## Contexto

O repositório `ponderada_actions_versan` está **vazio** (sem commits), com o remoto
`https://github.com/daviversan/ponderada_actions_versan.git` já configurado. A atividade pede
um experimento prático: um pipeline CI/CD simples (app calculadora) executado **≥12 vezes** com
variações controladas, coleta de métricas reais via API do GitHub, geração de **4 gráficos** e um
**relatório técnico** em `README.md`.

Decisões do usuário:
- **Disparo das execuções:** somente `workflow_dispatch` (toggles clicáveis em "Run workflow").
- **Idioma:** relatório, instruções e comentários em **português (PT-BR)**.

Restrição do ambiente: o `gh` CLI desta máquina é um wrapper interno da Uber quebrado para GitHub
público. Portanto **todas** as operações no GitHub (criar/push do repo, rodar workflow, ver runs,
tirar prints) serão feitas pelo usuário via navegador / `git` puro. O entregável deste agente são os
arquivos + instruções. O `scripts/collect_metrics.py` roda **localmente** na máquina do usuário
usando um Personal Access Token (PAT) para consultar a API.

### Nota técnica sobre paralelo vs sequencial
O GitHub Actions **não aceita `needs:` dinâmico por input**. Para manter "só workflow_dispatch",
o toggle de paralelismo é resolvido com **dois jobs de teste alternativos gated por `if:`**:
`test_seq` (`needs: lint`) e `test_par` (sem `needs:`). Apenas um roda por execução, conforme o
input `mode`. Ambos publicam o artefato com o **mesmo nome**, então o job `build` baixa o que existir.

## Estrutura final do projeto

```
ponderada_actions_versan/
├── .github/workflows/ci.yml      # pipeline (workflow_dispatch com inputs)
├── app/
│   ├── __init__.py
│   └── math_ops.py               # add/sub/mul/div (div trata div/0)
├── tests/
│   └── test_math.py              # testes que leem env vars p/ variações
├── scripts/
│   ├── collect_metrics.py        # API GitHub + artefatos -> CSV/JSON
│   └── make_charts.py            # 4 gráficos com pandas + matplotlib
├── data/.gitkeep                 # saída: metrics.csv, steps.csv, runs.json
├── charts/.gitkeep              # saída: 4 PNGs
├── requirements.txt              # CI: pytest, pytest-json-report, flake8
├── requirements-dev.txt          # local: requests, pandas, matplotlib
├── setup.cfg                     # config flake8 (max-line-length, excludes)
├── .gitignore
└── README.md                     # relatório técnico + reprodução
```

## Componentes a implementar

### 1. App e testes
- `app/math_ops.py`: `soma`, `subtrai`, `multiplica`, `divide` (levanta `ValueError` em div/0).
- `tests/test_math.py`: testes-base + **variações dirigidas por variáveis de ambiente** (assim um
  único commit gera todas as variações via inputs do dispatch):
  - `FORCE_FAIL=1` → adiciona um teste que falha (assert proposital).
  - `SLOW_TEST=1` → adiciona um teste com `time.sleep(~5s)` (teste lento).
  - `TEST_MULTIPLIER=N` → `@pytest.mark.parametrize` expande para ~N casos (aumenta nº de testes).

### 2. Pipeline `.github/workflows/ci.yml`
- Gatilho: `workflow_dispatch` com inputs:
  - `mode` (choice: `parallel` | `sequential`)
  - `use_cache` (boolean)
  - `force_fail` (boolean), `slow_test` (boolean), `test_multiplier` (string, default "1")
- Jobs:
  - `lint`: setup-python, instala `requirements.txt`, roda `flake8`.
  - `test_seq` (`if: mode=='sequential'`, `needs: lint`) e `test_par` (`if: mode=='parallel'`,
    sem needs): ambos instalam deps, cache pip **condicional** (`actions/cache` com
    `if: inputs.use_cache=='true'`), rodam `pytest --json-report --json-report-file=report.json`,
    exportam `FORCE_FAIL/SLOW_TEST/TEST_MULTIPLIER` a partir dos inputs, e fazem
    `upload-artifact` (nome fixo `test-results`, `if: always()` para capturar falhas).
  - `build` (`needs: [lint, test_seq, test_par]`, `if: always()`): baixa artefato e o re-publica
    como `relatorio-final` (etapa "geração de artefato com os resultados").
- `continue-on-error`/`if: always()` nos uploads para que runs com falha ainda produzam artefato.

### 3. `scripts/collect_metrics.py` (API + artefatos → dados estruturados)
- Lê `GITHUB_TOKEN` e `GITHUB_REPOSITORY` (default `daviversan/ponderada_actions_versan`) do env.
- `GET /repos/{repo}/actions/workflows/ci.yml/runs` (paginado, recentes).
- Por run: `run_id`, `head_sha`, mensagem do commit, `status`/`conclusion`,
  `run_started_at`→`updated_at` = `workflow_duration`, `timestamp`.
- `GET /runs/{id}/jobs`: por job nome, `started_at`→`completed_at` = `job_duration`; steps →
  duração por etapa (gravadas em `data/steps.csv` p/ o gráfico de etapas).
- `GET /runs/{id}/artifacts` → baixa zip `test-results` (header de auth), lê `report.json`
  (pytest-json-report): `test_count`, `test_failures`, tempo médio dos testes.
- Saídas: `data/metrics.csv` no schema exigido
  `run_id,commit_sha,commit_message,status,workflow_duration,job_name,job_duration,test_count,test_failures,timestamp`
  (uma linha por job), `data/steps.csv` e `data/runs.json` (bruto). Imprime tabela markdown
  resumo p/ colar no relatório.

### 4. `scripts/make_charts.py` (4 gráficos obrigatórios)
Com pandas + matplotlib, lendo os CSVs:
1. `charts/total_duration_per_run.png` — tempo total do pipeline por execução (barras).
2. `charts/job_durations.png` — tempo por job/etapa (barras agrupadas por run).
3. `charts/success_failure.png` — taxa de sucesso vs falha (pizza/barra).
4. `charts/tests_vs_duration.png` — nº de testes × duração do pipeline (dispersão).

### 5. `README.md` — relatório técnico (template com lacunas marcadas)
Seções, já indicando **onde colar cada print** (com marcadores `> 📸 PRINT: ...`):
- **Visão geral / objetivo**.
- **Como reproduzir** (passo a passo abaixo).
- **Tabela de execuções**: 12+ linhas (run_id real, commit, inputs/variação, status) — colar saída
  do collect.
- **Variações feitas** (explicação de cada combinação de inputs).
- **Gráficos** (embed dos 4 PNGs).
- **Análise** respondendo as 8 perguntas do enunciado.
- **2 resultados inesperados** + **hipótese inicial vs observado** + **limitações dos dados**.
- **Evidências**: prints reais, IDs reais dos workflows, commits reais.

#### Onde tirar prints (indicado no README)
- Aba **Actions** com a lista das 12+ execuções → seção "Tabela de execuções".
- Tela de **um run com sucesso** (grafo de jobs) → seção "Gráficos/Variações".
- Tela de **um run com falha** (job vermelho) → seção "Falhas mais frequentes".
- Tela de **artefatos** de um run (download) → seção "Geração de artefato".
- Comparação visual **com cache vs sem cache** (tempo do step de install) → seção "Cache".

## Plano de execução das 12+ runs (matriz de inputs — sem editar YAML)
Documentado no README; cada linha = um clique em "Run workflow":
1. baseline: parallel, cache on, mult 1
2. baseline repetido (medir variância)
3. sequential, cache on, mult 1
4. parallel, **cache off**, mult 1
5. sequential, cache off, mult 1
6. parallel, cache on, **mult 5**
7. parallel, cache on, **mult 20**
8. sequential, cache on, mult 20
9. parallel, cache on, **slow_test on**
10. parallel, cache on, **force_fail on**
11. sequential, cache on, force_fail on
12. parallel, cache off, mult 20, slow_test on
(+ extras à vontade). Obs.: como é dispatch, vários runs podem compartilhar o mesmo `commit_sha`;
para ter alguns commits distintos, fazer 1–2 commits triviais entre lotes (opcional, documentado).

## Passo a passo de configuração do GitHub Actions (irá no README e relatado ao usuário)
1. `git add . && git commit -m "MVP CI/CD experiment"` e `git push -u origin main`.
   (Se o repo remoto não existir, criar em github.com/new com o nome `ponderada_actions_versan`.)
2. No GitHub → aba **Actions** → habilitar workflows se solicitado.
3. Selecionar o workflow **CI** → botão **Run workflow** → escolher os inputs conforme a matriz.
4. Repetir ≥12 vezes variando os inputs.
5. Criar um **PAT** (Settings → Developer settings → Tokens, escopo `repo`/`actions:read`).
6. Local: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt`.
7. `export GITHUB_TOKEN=...` e `python scripts/collect_metrics.py` → gera `data/`.
8. `python scripts/make_charts.py` → gera `charts/`.
9. Preencher lacunas/prints no `README.md`, commitar `data/`, `charts/` e o relatório, e dar push.

## Verificação
- Local (antes do push): `flake8 app tests` e `pytest -q` devem passar no estado base
  (sem env vars de variação) — valida app/testes/lint.
- `python scripts/collect_metrics.py` com token válido gera `data/metrics.csv` com o header exigido
  e ≥12×(nº de jobs) linhas; `make_charts.py` gera 4 PNGs não-vazios.
- No GitHub: ao menos 1 run verde (sucesso) e 1 vermelho (force_fail) confirmam captura de
  sucesso/falha; artefato `relatorio-final` baixável confirma a etapa de artefato.

## Notas
- `requirements.txt` (CI) fica enxuto; `pandas`/`matplotlib`/`requests` só em `requirements-dev.txt`.
- `setup.cfg` define `max-line-length` p/ o flake8 não falhar à toa.
- `.gitignore` ignora `.venv/`, `__pycache__/`, `report.json` local.
