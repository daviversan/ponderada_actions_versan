"""Operações aritméticas básicas da calculadora do experimento CI/CD."""


def soma(a, b):
    """Retorna a soma de a e b."""
    return a + b


def subtrai(a, b):
    """Retorna a diferença entre a e b."""
    return a - b


def multiplica(a, b):
    """Retorna o produto de a e b."""
    return a * b


def divide(a, b):
    """Retorna a divisão de a por b.

    Levanta ValueError quando b é zero, evitando ZeroDivisionError.
    """
    if b == 0:
        raise ValueError("Divisão por zero não é permitida.")
    return a / b
