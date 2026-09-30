"""Validadores de identificadores: reduzem o falso positivo das regras regex.

Uma regex acha "11 dígitos"; o validador confirma que é um CPF possível (dígito
verificador). Usados pelas regras determinísticas (`validator:` na política) e pela
remoção de dados pessoais antes do envio a um provedor de LLM (redact.py).
"""

import re

# Números de teste publicados pelas bandeiras e adquirentes: não são dado de titular.
TEST_PANS = frozenset({
    "4111111111111111", "4012888888881881", "4222222222222", "4242424242424242",
    "4000056655665556", "5555555555554444", "5105105105105100", "2223003122003222",
    "378282246310005", "371449635398431", "6011111111111117", "6011000990139424",
    "30569309025904", "38520000023237", "3530111333300000", "3566002020360505",
})


def digits(text):
    return re.sub(r"\D", "", text)


def _dv(numbers, weights):
    rest = sum(n * w for n, w in zip(numbers, weights)) % 11
    return 0 if rest < 2 else 11 - rest


def is_cpf(text):
    d = [int(c) for c in digits(text)]
    if len(d) != 11 or len(set(d)) == 1:
        return False
    return (_dv(d[:9], range(10, 1, -1)) == d[9]
            and _dv(d[:10], range(11, 1, -1)) == d[10])


def is_cnpj(text):
    d = [int(c) for c in digits(text)]
    if len(d) != 14 or len(set(d)) == 1:
        return False
    first = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    return _dv(d[:12], first) == d[12] and _dv(d[:13], [6, *first]) == d[13]


def luhn(number):
    total = 0
    for i, c in enumerate(reversed(number)):
        n = int(c)
        if i % 2:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0


def is_pan(text):
    """Número de cartão plausível: 13 a 19 dígitos, prefixo de bandeira, Luhn, fora da lista de teste."""
    number = digits(text)
    return (13 <= len(number) <= 19 and number[0] in "3456" and luhn(number)
            and number not in TEST_PANS)


VALIDATORS = {"cpf": is_cpf, "cnpj": is_cnpj, "pan": is_pan}
