"""Camada T1 por julgamento tipado: o Jev (TypeSafe System One) decide, o código localiza.

Para políticas com `llm.engine: jev` (ADR-GOV-002):
- A regex `llm.candidates` marca as linhas ADICIONADAS a julgar. Linha que não casa não é
  julgada: o recall do Jev nunca passa do recall da regex de candidatos.
- Cada candidata vira uma pergunta Noul (probabilidade de "sim") sobre o mesmo estado:
  o arquivo inteiro e os arquivos do PR que ele cita. As perguntas de um arquivo vão
  juntas numa requisição e são respondidas em paralelo, sem ver umas às outras.
- O modelo não escreve nada: só devolve probabilidades. A mensagem do achado é da
  política, e o limiar (`llm.threshold`) é calibrado no eval.
- Mesmas garantias da camada LLM: conteúdo redigido, entrada acima do orçamento vira
  erro (nada é truncado) e qualquer falha do provedor bloqueia.
"""

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import PurePosixPath

from .llm import (REQUEST_TIMEOUT_MS, ProviderError, _error_message, _with_retries,
                  api_key_env, llm_run_error)
from .model import Finding, GovernanceError, RunError
from .policy import in_scope
from .redact import redact

logger = logging.getLogger("governance.jev")


class JevProvider:
    """POST https://api.typesafe.ai/v1/systemone (https://docs.typesafe.ai/api)."""

    URL = "https://api.typesafe.ai/v1/systemone"

    def __init__(self, config, api_key):
        self._config = config
        self._headers = {"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"}

    def _post(self, payload):
        import urllib.error
        import urllib.request

        request = urllib.request.Request(
            self.URL, data=json.dumps(payload).encode("utf-8"), headers=self._headers,
            method="POST")
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_MS / 1000) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ProviderError(exc.code, _error_message(exc.read())) from None

    def nouls(self, state, questions):
        """{id: instruções} -> {id: probabilidade de sim}. Resposta incompleta é erro."""
        payload = {"model": self._config.model, "state": state,
                   "questions": {qid: {"type": "noul", "instructions": text}
                                 for qid, text in questions.items()}}

        def call():
            answers = self._post(payload).get("answers") or {}
            result = {}
            for qid in questions:
                value = (answers.get(qid) or {}).get("noul")
                if not isinstance(value, (int, float)) or not 0 <= value <= 1:
                    raise ValueError(f"resposta do Jev sem probabilidade para {qid}")
                result[qid] = float(value)
            return result

        return _with_retries(self._config, call)


def build_jev_provider(config, api_key):
    if config.provider == "typesafe":
        return JevProvider(config, api_key)
    raise GovernanceError(f"Provedor do Jev não suportado: {config.provider}")


def _numbered(content):
    lines = content.splitlines()
    width = len(str(max(len(lines), 1)))
    return "\n".join(f"{n:>{width}}| {text}" for n, text in enumerate(lines, 1))


def build_state(changed_file, others):
    """Arquivo revisado e os outros arquivos do PR que ele cita pelo nome (ex.: o record
    `Cliente` com CPF, necessário para julgar `log.info("{}", cliente)`)."""
    cited = {}
    for other in others:
        name = PurePosixPath(other.path).stem
        if other.path != changed_file.path and re.search(rf"\b{re.escape(name)}\b",
                                                          changed_file.content):
            cited[other.path] = redact(other.content)
    return {"arquivo": changed_file.path,
            "codigo": redact(_numbered(changed_file.content)),
            "outros_arquivos": cited}


def candidates(policy, changed_file):
    pattern = re.compile(policy.llm["candidates"])
    return {n: text for n, text in sorted(changed_file.added_lines.items())
            if pattern.search(text)}


def _judge_file(provider, config, policy, changed_file, others):
    lines = candidates(policy, changed_file)
    if not lines:
        return []
    state = build_state(changed_file, others)
    size = len(json.dumps(state, ensure_ascii=False))
    if size > config.max_input_chars:
        raise GovernanceError(
            f"{changed_file.path} (com os arquivos que ele cita) tem {size} caracteres e passa "
            f"do limite do Jev ({config.max_input_chars}). Nada é truncado, então o arquivo "
            "não foi revisado.")
    # replace e não format: a pergunta pode ter chaves literais (ex.: `{}` de log)
    questions = {f"linha_{n}": policy.llm["question"].replace("{line}", str(n))
                 .replace("{text}", text.strip()) for n, text in lines.items()}
    answers = provider.nouls(state, questions)
    findings = []
    for n in lines:
        probability = answers[f"linha_{n}"]
        logger.info("Jev %s %s:%d p=%.2f", policy.id, changed_file.path, n, probability)
        if probability >= policy.llm["threshold"]:
            findings.append(Finding(policy.id, policy.severity, changed_file.path, n,
                                    f"{policy.title} (Jev: p={probability:.2f}). "
                                    f"{policy.remediation.splitlines()[0]}", "llm"))
    return findings


def run_jev(policies, files, provider, config):
    """Retorna (achados, erros). Erros tornam o veredito BLOQUEADO."""
    live = [f for f in files if not f.deleted]
    jobs = [(policy, f) for policy in policies for f in live
            if f.added_lines and in_scope(policy, f.path)]
    findings, errors = [], []
    if not jobs:
        return findings, errors
    with ThreadPoolExecutor(max_workers=min(4, len(jobs))) as pool:
        futures = [(policy, changed_file,
                    pool.submit(_judge_file, provider, config, policy, changed_file,
                                [o for o in live if in_scope(policy, o.path)]))
                   for policy, changed_file in jobs]
        for policy, changed_file, future in futures:
            try:
                findings += future.result()
            except GovernanceError as exc:
                errors.append(RunError(
                    "input_too_large", f"Revisor de IA (Jev, {policy.id}): {exc}",
                    "Divida o arquivo ou peça ao time de plataforma para rever o escopo da "
                    "política."))
            except Exception as exc:  # noqa: BLE001 - bloqueia, sem derrubar os outros
                errors.append(llm_run_error(f"Jev, {policy.id}", exc,
                                            api_key_env(config.provider)))
    return findings, errors
