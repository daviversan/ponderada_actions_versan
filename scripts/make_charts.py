#!/usr/bin/env python3
"""Gera os 4 gráficos obrigatórios a partir dos CSVs em data/.

Lê data/metrics.csv (e data/steps.csv quando disponível) e produz em charts/:
1. total_duration_per_run.png  — tempo total do pipeline por execução (barras).
2. job_durations.png           — tempo por job/etapa (barras agrupadas por run).
3. success_failure.png         — taxa de sucesso vs falha (pizza).
4. tests_vs_duration.png       — nº de testes x duração do pipeline (dispersão).

Uso: python scripts/make_charts.py
"""

import os
import sys

import matplotlib

matplotlib.use("Agg")  # backend sem display, para rodar headless
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(HERE, "data")
CHARTS_DIR = os.path.join(HERE, "charts")


def carregar_metrics():
    path = os.path.join(DATA_DIR, "metrics.csv")
    if not os.path.exists(path):
        sys.exit("ERRO: data/metrics.csv não encontrado. Rode collect_metrics.py.")
    df = pd.read_csv(path)
    if df.empty:
        sys.exit("ERRO: data/metrics.csv está vazio.")
    for col in ("workflow_duration", "job_duration", "test_count",
                "test_failures"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def grafico_total_por_run(df):
    """Tempo total do pipeline por execução (workflow_duration por run_id)."""
    por_run = (df.groupby("run_id")["workflow_duration"]
               .max().reset_index().sort_values("run_id"))
    fig, ax = plt.subplots(figsize=(10, 5))
    rotulos = por_run["run_id"].astype(str)
    ax.bar(rotulos, por_run["workflow_duration"], color="#4C72B0")
    ax.set_title("Tempo total do pipeline por execução")
    ax.set_xlabel("run_id")
    ax.set_ylabel("Duração (s)")
    plt.xticks(rotation=45, ha="right")
    fig.tight_layout()
    fig.savefig(os.path.join(CHARTS_DIR, "total_duration_per_run.png"), dpi=120)
    plt.close(fig)


def grafico_job_durations(df):
    """Duração por job, agrupada por run (barras agrupadas)."""
    pivot = df.pivot_table(index="run_id", columns="job_name",
                           values="job_duration", aggfunc="max")
    fig, ax = plt.subplots(figsize=(11, 5))
    pivot.plot(kind="bar", ax=ax)
    ax.set_title("Duração por job em cada execução")
    ax.set_xlabel("run_id")
    ax.set_ylabel("Duração (s)")
    ax.legend(title="job", bbox_to_anchor=(1.02, 1), loc="upper left")
    plt.xticks(rotation=45, ha="right")
    fig.tight_layout()
    fig.savefig(os.path.join(CHARTS_DIR, "job_durations.png"), dpi=120)
    plt.close(fig)


def grafico_sucesso_falha(df):
    """Taxa de sucesso vs falha (nível de run, status único por run_id)."""
    status_por_run = df.groupby("run_id")["status"].first()
    sucesso = (status_por_run == "success").sum()
    falha = (status_por_run != "success").sum()
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.pie([sucesso, falha], labels=["sucesso", "falha/outros"],
           autopct=lambda p: f"{p:.0f}%", colors=["#55A868", "#C44E52"],
           startangle=90)
    ax.set_title("Taxa de sucesso vs falha das execuções")
    fig.tight_layout()
    fig.savefig(os.path.join(CHARTS_DIR, "success_failure.png"), dpi=120)
    plt.close(fig)


def grafico_testes_vs_duracao(df):
    """Dispersão: nº de testes x duração total do pipeline (por run)."""
    por_run = df.groupby("run_id").agg(
        test_count=("test_count", "max"),
        workflow_duration=("workflow_duration", "max"),
    ).dropna()
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(por_run["test_count"], por_run["workflow_duration"],
               color="#8172B3", s=60)
    ax.set_title("Nº de testes x duração do pipeline")
    ax.set_xlabel("nº de testes")
    ax.set_ylabel("duração do pipeline (s)")
    fig.tight_layout()
    fig.savefig(os.path.join(CHARTS_DIR, "tests_vs_duration.png"), dpi=120)
    plt.close(fig)


def main():
    os.makedirs(CHARTS_DIR, exist_ok=True)
    df = carregar_metrics()
    grafico_total_por_run(df)
    grafico_job_durations(df)
    grafico_sucesso_falha(df)
    grafico_testes_vs_duracao(df)
    print("Gerados 4 gráficos em charts/:")
    for nome in ("total_duration_per_run.png", "job_durations.png",
                 "success_failure.png", "tests_vs_duration.png"):
        caminho = os.path.join(CHARTS_DIR, nome)
        tam = os.path.getsize(caminho) if os.path.exists(caminho) else 0
        print(f"  - {nome} ({tam} bytes)")


if __name__ == "__main__":
    main()
