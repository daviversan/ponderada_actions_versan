"""Testes da calculadora.

Inclui testes-base e variações dirigidas por variáveis de ambiente, de modo que
um único commit consiga gerar todas as variações do experimento via inputs do
`workflow_dispatch`:

- FORCE_FAIL=1     -> adiciona um teste que falha de propósito.
- SLOW_TEST=1      -> adiciona um teste lento (time.sleep).
- TEST_MULTIPLIER=N -> expande casos parametrizados para aumentar o nº de testes.
"""

import os
import time

import pytest

from app.math_ops import soma, subtrai, multiplica, divide


# ---------------------------------------------------------------------------
# Testes-base (sempre rodam)
# ---------------------------------------------------------------------------
def test_soma():
    assert soma(2, 3) == 5
    assert soma(-1, 1) == 0


def test_subtrai():
    assert subtrai(5, 3) == 2
    assert subtrai(0, 4) == -4


def test_multiplica():
    assert multiplica(4, 3) == 12
    assert multiplica(-2, 5) == -10


def test_divide():
    assert divide(10, 2) == 5
    assert divide(9, 3) == 3


def test_divide_por_zero_levanta_erro():
    with pytest.raises(ValueError):
        divide(1, 0)


# ---------------------------------------------------------------------------
# Variação: aumento do nº de testes via TEST_MULTIPLIER
# ---------------------------------------------------------------------------
_MULTIPLIER = int(os.environ.get("TEST_MULTIPLIER", "1"))


@pytest.mark.parametrize("i", range(_MULTIPLIER))
def test_soma_parametrizada(i):
    # Cada caso valida a propriedade soma(i, i) == 2*i; o nº de casos cresce
    # com TEST_MULTIPLIER para inflar a contagem de testes do relatório.
    assert soma(i, i) == 2 * i


# ---------------------------------------------------------------------------
# Variação: teste lento via SLOW_TEST
# ---------------------------------------------------------------------------
@pytest.mark.skipif(
    os.environ.get("SLOW_TEST") != "1",
    reason="SLOW_TEST não habilitado",
)
def test_lento():
    time.sleep(5)
    assert soma(1, 1) == 2


# ---------------------------------------------------------------------------
# Variação: falha proposital via FORCE_FAIL
# ---------------------------------------------------------------------------
@pytest.mark.skipif(
    os.environ.get("FORCE_FAIL") != "1",
    reason="FORCE_FAIL não habilitado",
)
def test_falha_proposital():
    assert soma(2, 2) == 5, "Falha proposital para o experimento (FORCE_FAIL=1)"
