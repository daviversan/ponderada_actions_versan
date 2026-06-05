#!/usr/bin/env python3
"""Coleta métricas reais das execuções do GitHub Actions via API REST.

Roda LOCALMENTE na máquina do usuário (o gh CLI desta máquina está quebrado).
Usa um Personal Access Token (PAT) com escopo `repo` / `actions:read`.

Variáveis de ambiente:
- GITHUB_TOKEN       (obrigatória) PAT para autenticar na API.
- GITHUB_REPOSITORY  (opcional)    default "daviversan/ponderada_actions_versan".
- WORKFLOW_FILE      (opcional)    default "ci.yml".
- MAX_RUNS           (opcional)    default 50.

Saídas (pasta data/):
- metrics.csv  -> uma linha por job, schema exigido pelo enunciado.
- steps.csv    -> duração por etapa (step) de cada job.
- runs.json    -> payload bruto das runs (para auditoria/reprodução).

Imprime no final uma tabela markdown resumo para colar no relatório.
"""

import csv
import io
import json
import os
import sys
import zipfile
from datetime import datetime

import requests

API = "https://api.github.com"

# Schema exigido pelo enunciado para data/metrics.csv (uma linha por job).
METRICS_HEADER = [
    "run_id",
    "commit_sha",
    "commit_message",
    "status",
    "workflow_duration",
    "job_name",
    "job_duration",
    "test_count",
    "test_failures",
    "timestamp",
]

STEPS_HEADER = ["run_id", "job_name", "step_name", "step_duration"]


# ---------------------------------------------------------------------------
# Funções puras de parsing (testáveis localmente, sem rede)
# ---------------------------------------------------------------------------
def parse_iso(ts):
    """Converte timestamp ISO-8601 do GitHub (…Z) em datetime aware."""
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def duration_seconds(start, end):
    """Diferença em segundos entre dois timestamps ISO; None se faltar dado."""
    a, b = parse_iso(start), parse_iso(end)
    if a is None or b is None:
        return None
    return round((b - a).total_seconds(), 2)


def parse_report_json(report_bytes):
    """Extrai (test_count, test_failures, avg_test_duration) de um report.json
    gerado pelo pytest-json-report. Tolera campos ausentes."""
    try:
        data = json.loads(report_bytes)
    except (ValueError, TypeError):
        return (None, None, None)
    summary = data.get("summary", {})
    test_count = summary.get("total", summary.get("collected"))
    failures = summary.get("failed", 0) or 0
    tests = data.get("tests", []) or []
    durations = [t.get("call", {}).get("duration", 0) or 0 for t in tests]
    avg = round(sum(durations) / len(durations), 4) if durations else None
    return (test_count, failures, avg)


def first_line(text):
    """Primeira linha de uma string (mensagem de commit), sem quebras."""
    if not text:
        return ""
    return text.splitlines()[0]


def build_metric_row(run, job, report_metrics):
    """Monta uma linha de metrics.csv a partir de dicts de run, job e report."""
    test_count, test_failures, _ = report_metrics
    return {
        "run_id": run["id"],
        "commit_sha": (run.get("head_sha") or "")[:12],
        "commit_message": first_line(
            (run.get("head_commit") or {}).get("message", "")
        ),
        "status": run.get("conclusion") or run.get("status") or "",
        "workflow_duration": duration_seconds(
            run.get("run_started_at"), run.get("updated_at")
        ),
        "job_name": job.get("name", ""),
        "job_duration": duration_seconds(
            job.get("started_at"), job.get("completed_at")
        ),
        "test_count": test_count if test_count is not None else "",
        "test_failures": test_failures if test_failures is not None else "",
        "timestamp": run.get("run_started_at") or run.get("created_at") or "",
    }


# ---------------------------------------------------------------------------
# Camada de rede (API do GitHub)
# ---------------------------------------------------------------------------
def gh_get(session, url, **kwargs):
    resp = session.get(url, timeout=30, **kwargs)
    resp.raise_for_status()
    return resp


def list_runs(session, repo, workflow_file, max_runs):
    runs, page = [], 1
    while len(runs) < max_runs:
        url = f"{API}/repos/{repo}/actions/workflows/{workflow_file}/runs"
        resp = gh_get(
            session, url, params={"per_page": 100, "page": page}
        )
        batch = resp.json().get("workflow_runs", [])
        if not batch:
            break
        runs.extend(batch)
        page += 1
    return runs[:max_runs]


def get_jobs(session, repo, run_id):
    url = f"{API}/repos/{repo}/actions/runs/{run_id}/jobs"
    return gh_get(session, url, params={"per_page": 100}).json().get("jobs", [])


def get_report_from_artifacts(session, repo, run_id):
    """Baixa o artefato test-results (ou relatorio-final) e lê report.json."""
    url = f"{API}/repos/{repo}/actions/runs/{run_id}/artifacts"
    artifacts = gh_get(session, url).json().get("artifacts", [])
    wanted = None
    for name in ("test-results", "relatorio-final"):
        for art in artifacts:
            if art["name"] == name and not art.get("expired"):
                wanted = art
                break
        if wanted:
            break
    if not wanted:
        return (None, None, None)
    zresp = gh_get(session, wanted["archive_download_url"])
    try:
        zf = zipfile.ZipFile(io.BytesIO(zresp.content))
    except zipfile.BadZipFile:
        return (None, None, None)
    for member in zf.namelist():
        if member.endswith("report.json"):
            return parse_report_json(zf.read(member))
    return (None, None, None)


# ---------------------------------------------------------------------------
# Escrita das saídas
# ---------------------------------------------------------------------------
def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


def markdown_table(metric_rows):
    cols = ["run_id", "commit_sha", "status", "job_name",
            "workflow_duration", "job_duration", "test_count", "test_failures"]
    lines = ["| " + " | ".join(cols) + " |",
             "| " + " | ".join("---" for _ in cols) + " |"]
    for r in metric_rows:
        lines.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
    return "\n".join(lines)


def main():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("ERRO: defina GITHUB_TOKEN (PAT com escopo repo/actions:read).")
    repo = os.environ.get(
        "GITHUB_REPOSITORY", "daviversan/ponderada_actions_versan"
    )
    workflow_file = os.environ.get("WORKFLOW_FILE", "ci.yml")
    max_runs = int(os.environ.get("MAX_RUNS", "50"))

    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(here, "data")
    os.makedirs(data_dir, exist_ok=True)

    print(f"Coletando runs de {repo} (workflow {workflow_file})…")
    runs = list_runs(session, repo, workflow_file, max_runs)
    print(f"  -> {len(runs)} runs encontradas.")

    metric_rows, step_rows = [], []
    for run in runs:
        run_id = run["id"]
        report_metrics = get_report_from_artifacts(session, repo, run_id)
        jobs = get_jobs(session, repo, run_id)
        for job in jobs:
            metric_rows.append(build_metric_row(run, job, report_metrics))
            for step in job.get("steps", []) or []:
                step_rows.append({
                    "run_id": run_id,
                    "job_name": job.get("name", ""),
                    "step_name": step.get("name", ""),
                    "step_duration": duration_seconds(
                        step.get("started_at"), step.get("completed_at")
                    ),
                })

    write_csv(os.path.join(data_dir, "metrics.csv"), METRICS_HEADER, metric_rows)
    write_csv(os.path.join(data_dir, "steps.csv"), STEPS_HEADER, step_rows)
    with open(os.path.join(data_dir, "runs.json"), "w", encoding="utf-8") as f:
        json.dump(runs, f, ensure_ascii=False, indent=2)

    print(f"\nGravado: data/metrics.csv ({len(metric_rows)} linhas), "
          f"data/steps.csv ({len(step_rows)} linhas), data/runs.json.\n")
    print("Resumo (colar no README):\n")
    print(markdown_table(metric_rows))


if __name__ == "__main__":
    main()
