"""
M-One Employee Google Doc AI Importer Service (services/employee_doc_importer_service.py)
Captura respostas semanais diretamente de links do Google Docs compartilhados,
valida a aderência ao cargo com IA (Gemini) e popula os relatórios no M-One.
Segregação modular (< 500 linhas).
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from database import db
from services.employee_reports_data import REPORTING_EMPLOYEES, get_reporting_employee_meta
from services.employee_reports_service import _is_pg, ensure_reports_schema, save_or_submit_report
from services.gemini_client import execute_gemini_payload

logger = logging.getLogger(__name__)

DEFAULT_DOC_LINKS = {
    "luiza": "https://docs.google.com/document/d/1wzo1ZRpSOk8ZdfDZIfkEiXUGFv7yMjZatndfcIxHta0/edit",
    "jhon": "https://docs.google.com/document/d/1m7k31TZNiQqjAP9se9zlEaVQ-LUA6x7k4YHPpmTkCDM/edit",
    "marisa": "https://docs.google.com/document/d/1GYquLmLyzCRvlxztj7dlB-zzTMmsZ4ok1VcpsMojPy4/edit",
    "ricardo": "https://docs.google.com/document/d/1GbsWtQ_rn_XHj2h3y44YpnlredXKSa0Chsx4HEOS9ic/edit",
    "leo": "https://docs.google.com/document/d/1t91DotoYwNwYtUGEacx8GqpJABgemLJzwBAIl8JJs4Q/edit",
    "gabriel": "https://docs.google.com/document/d/1cCh_6l2doYJg0FmzImD5Y6g4eAVuMsdJPBgbxxbQGG0/edit",
}


def ensure_doc_links_schema() -> None:
    """Garante a tabela de links de Google Docs e a coluna na tabela de relatórios."""
    ensure_reports_schema()
    with db() as conn:
        pg = _is_pg(conn)
        create_sql = """CREATE TABLE IF NOT EXISTS maj_employee_doc_links (
            employee_key VARCHAR(50) PRIMARY KEY,
            google_doc_url TEXT NOT NULL,
            doc_id VARCHAR(100),
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );""" if pg else """CREATE TABLE IF NOT EXISTS maj_employee_doc_links (
            employee_key TEXT PRIMARY KEY,
            google_doc_url TEXT NOT NULL,
            doc_id TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );"""
        try:
            conn.executescript(create_sql)
            conn.commit()
        except Exception:
            pass

        # Garante coluna google_doc_url em maj_employee_reports
        try:
            conn.execute("ALTER TABLE maj_employee_reports ADD COLUMN google_doc_url TEXT;")
            conn.commit()
        except Exception:
            pass


def extract_doc_id(url: str) -> Optional[str]:
    """Extrai o ID alfanumérico do documento a partir de uma URL do Google Docs."""
    if not url:
        return None
    match = re.search(r"/document/d/([a-zA-Z0-9-_]+)", url.strip())
    return match.group(1) if match else None


def seed_default_doc_links_if_empty() -> None:
    """Pré-cadastra os links oficiais fornecidos caso a tabela esteja vazia."""
    ensure_doc_links_schema()
    with db() as conn:
        for key, url in DEFAULT_DOC_LINKS.items():
            doc_id = extract_doc_id(url)
            if _is_pg(conn):
                conn.execute(
                    """INSERT INTO maj_employee_doc_links (employee_key, google_doc_url, doc_id, updated_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (employee_key) DO NOTHING;""",
                    (key, url, doc_id)
                )
            else:
                conn.execute(
                    """INSERT OR IGNORE INTO maj_employee_doc_links (employee_key, google_doc_url, doc_id, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP);""",
                    (key, url, doc_id)
                )
        conn.commit()


def get_all_doc_links() -> Dict[str, Dict[str, Any]]:
    """Retorna todos os links cadastrados mapeados por chave de colaborador."""
    ensure_doc_links_schema()
    seed_default_doc_links_if_empty()
    with db() as conn:
        rows = conn.execute("SELECT * FROM maj_employee_doc_links").fetchall() or []
        links_map = {}
        for r in rows:
            d = dict(r)
            links_map[d["employee_key"]] = d
        return links_map


def save_doc_link(employee_key: str, url: str) -> bool:
    """Cadastra ou atualiza o link de Google Doc de um colaborador."""
    ensure_doc_links_schema()
    key = employee_key.lower().strip()
    doc_id = extract_doc_id(url)
    if not doc_id:
        return False

    with db() as conn:
        if _is_pg(conn):
            conn.execute(
                """INSERT INTO maj_employee_doc_links (employee_key, google_doc_url, doc_id, updated_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (employee_key) DO UPDATE
                SET google_doc_url = EXCLUDED.google_doc_url, doc_id = EXCLUDED.doc_id, updated_at = NOW();""",
                (key, url.strip(), doc_id)
            )
        else:
            conn.execute(
                """INSERT INTO maj_employee_doc_links (employee_key, google_doc_url, doc_id, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(employee_key) DO UPDATE
                SET google_doc_url = excluded.google_doc_url, doc_id = excluded.doc_id, updated_at = CURRENT_TIMESTAMP;""",
                (key, url.strip(), doc_id)
            )
        conn.commit()
        return True


def fetch_google_doc_text(url_or_id: str, timeout: int = 20) -> Tuple[bool, str, str]:
    """
    Baixa o texto UTF-8 puro do Google Doc via endpoint oficial de exportação direta.
    Retorna (sucesso, texto_ou_erro, doc_id).
    """
    doc_id = extract_doc_id(url_or_id) or url_or_id.strip()
    if not doc_id or len(doc_id) < 15:
        return False, "Link de Google Doc inválido ou ID não reconhecido.", ""

    export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"
    req = urllib.request.Request(
        export_url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 M-One-DocReader/1.0"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw_bytes = resp.read()
            text = raw_bytes.decode("utf-8", errors="replace").strip()
            if not text:
                return False, "O documento está completamente vazio no Google Docs.", doc_id
            return True, text, doc_id
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return False, "Acesso negado: certifique-se de que o documento está com compartilhamento 'Qualquer pessoa com o link pode ler'.", doc_id
        if e.code == 404:
            return False, "Documento não encontrado no Google Docs. Verifique o link.", doc_id
        return False, f"Erro HTTP ao acessar Google Docs: {e.code} {e.reason}", doc_id
    except Exception as ex:
        return False, f"Falha de conexão ao ler Google Doc: {ex}", doc_id


def extract_answers_with_gemini(
    doc_text: str,
    meta: Dict[str, Any],
    cycle_info: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Utiliza o Gemini para auditar a aderência do documento ao cargo/colaborador
    e extrair com precisão as respostas para cada pergunta da cartilha oficial,
    respeitando o ciclo semanal ativo e ignorando histórico de semanas passadas.
    """
    questions_list = meta.get("questions", [])
    questions_fmt = "\n".join([f"- ID: '{q['id']}' | Pergunta: '{q['label']}'" for q in questions_list])

    cycle_ctx = ""
    if cycle_info:
        c_title = cycle_info.get("title") or f"Ciclo {cycle_info.get('cycle_code')}"
        start_d = str(cycle_info.get("start_date") or "")
        deadline_d = str(cycle_info.get("deadline") or "")
        cycle_ctx = f"""
CICLO OFICIAL ALVO NO M-ONE (SEMANA ATIVA):
- Ciclo: {c_title} (Código: {cycle_info.get('cycle_code')})
- Período Oficial: Início em {start_d} até {deadline_d}
"""

    prompt = f"""Você é o Auditor Sênior de Governança e Processos da MAJ Mobilidade Elétrica.
Sua missão é ler o texto bruto extraído de um Google Doc preenchido pelo colaborador e extrair as respostas para o sistema M-One.

COLABORADOR ALVO NO M-ONE:
- Nome: {meta['name']}
- Chave: {meta['key']}
- Cargo/Função: {meta['role_title']}
- Área: {meta['area']}
{cycle_ctx}
PERGUNTAS OFICIAIS QUE DEVEM SER RESPONDIDAS:
{questions_fmt}

TEXTO BRUTO EXTRAÍDO DO GOOGLE DOC:
---
{doc_text[:8000]}
---

REGRAS CRÍTICAS DE AUDITORIA:
1. VALIDAÇÃO DE ADERÊNCIA / FUNÇÃO:
   - Verifique o cabeçalho e o conteúdo do documento.
   - O documento deve claramente pertencer a '{meta['name']}' ou à sua respectiva função ({meta['role_title']}).
   - Se o documento contiver explicitamente o cabeçalho de OUTRO colaborador (ex: é um relatório de Oficina do Ricardo mas estamos importando para Financeiro/Marisa, ou vice-versa), você DEVE definir "valido": false e explicar detalhadamente no campo "motivo_incompatibilidade".
   - Caso seja o documento correto de '{meta['name']}', defina "valido": true.

2. DETECÇÃO DE MODELO EM BRANCO / TEMPLATE VIRGEM:
   - Verifique se o documento é apenas o template de perguntas virgem, ainda NÃO respondido pelo colaborador.
   - Sinais claros de modelo em branco:
     * O texto contém apenas o questionário padrão com tópicos ou placeholders não preenchidos (ex: "Semana: ____/____/______", "Sim / Não" sem resposta assinalada, ou tópicos sem relato subsequente).
     * Não há nenhum dado numérico, fato concreto, relato ou resposta redigida pelo colaborador.
   - Se for apenas o modelo virgem, defina OBRIGATORIAMENTE "documento_em_branco": true, "resumo_doc": "Documento em branco (aguardando preenchimento do colaborador)" e retorne todas as respostas como string vazia "".
   - Se o colaborador de fato preencheu respostas reais, defina "documento_em_branco": false.

3. GERENCIAMENTO DE MÚLTIPLAS SEMANAS E TOLERÂNCIA A ERROS DE DATA:
   - Se o documento contiver MÚLTIPLAS SEMANAS OU PÁGINAS ACUMULADAS (histórico de relatórios anteriores mantido no documento):
     * Extraia única e exclusivamente as respostas para a SEMANA ALVO correspondente ao período oficial informado acima (ou a seção mais recente do documento).
     * Ignore relatos de semanas passadas que já foram arquivadas em ciclos anteriores.
   - TOLERÂNCIA A ERROS DE DIGITAÇÃO DE DATAS:
     * O colaborador pode ter esquecido de atualizar o cabeçalho de datas (ex: deixou '____/____/______' ou digitou uma data com erro). O Ciclo Oficial do M-One é a verdade soberana. Se o relato tratar das atividades recentes, extraia as respostas com fidelidade.

4. EXTRAÇÃO DAS RESPOSTAS:
   - Se "documento_em_branco": true, retorne todas as respostas como "".
   - Se houver respostas reais, capture estritamente o conteúdo que o colaborador redigiu para cada pergunta.
   - NUNCA copie o texto do próprio enunciado ou opções do template (como "• Realizada? Sim / Não", "• Área/modelos conferidos:") como se fossem respostas se não houver texto digitado pelo colaborador.
   - Mantenha fidelidade e clareza ao que o colaborador relatou.

Retorne ESTRITAMENTE um objeto JSON com esta estrutura exata:
{{
  "valido": true,
  "motivo_incompatibilidade": "",
  "documento_em_branco": false,
  "colaborador_detectado": "Nome ou Cargo detectado no cabeçalho do documento",
  "resumo_doc": "Breve resumo em 1 linha do que foi reportado no documento",
  "respostas": {{
    "id_da_pergunta": "Texto da resposta extraída..."
  }}
}}"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }

    try:
        res = execute_gemini_payload(payload, timeout=30)
        parsed = res.get("data")
        if not parsed and res.get("text"):
            try:
                parsed = json.loads(res["text"])
            except Exception:
                parsed = None

        if isinstance(parsed, dict) and "respostas" in parsed:
            return parsed

        return {
            "valido": False,
            "motivo_incompatibilidade": "A IA não conseguiu interpretar a estrutura do documento.",
            "respostas": {}
        }
    except Exception as ex:
        logger.error("Erro na chamada Gemini para extração de Google Doc: %s", ex)
        return {
            "valido": False,
            "motivo_incompatibilidade": f"Erro no processamento da IA: {ex}",
            "respostas": {}
        }


def sync_single_employee_report(
    cycle_id: int,
    employee_key: str,
    custom_url: Optional[str] = None,
    force: bool = False,
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Executa o fluxo completo para um funcionário:
    1. Obtém o link
    2. Lê o Google Doc
    3. Analisa e extrai com IA
    4. Se divergir e not force: bloqueia e avisa
    5. Se válido ou forçado: grava como enviado no banco
    """
    meta = get_reporting_employee_meta(employee_key)
    if not meta:
        return {"status": "error", "message": f"Colaborador '{employee_key}' não encontrado."}

    # Fauzer não usa Google Doc
    if employee_key.lower().strip() == "fauzer":
        return {
            "status": "skipped",
            "message": "Fauzer não utiliza Google Doc (preenchimento direto no formulário M-One).",
            "employee_key": "fauzer"
        }

    # Busca URL
    links = get_all_doc_links()
    doc_url = custom_url or (links.get(employee_key, {}).get("google_doc_url"))
    if not doc_url:
        return {
            "status": "error",
            "message": f"Nenhum link de Google Doc cadastrado para {meta['name']}."
        }

    # Baixa texto
    ok, doc_text, doc_id = fetch_google_doc_text(doc_url)
    if not ok:
        return {
            "status": "error",
            "message": doc_text,
            "doc_url": doc_url,
            "doc_id": doc_id
        }

    # Recupera informações do ciclo ativo para contextualizar a IA
    cycle_info = None
    try:
        with db() as conn:
            ph = "%s" if _is_pg(conn) else "?"
            cur_c = conn.execute(f"SELECT * FROM maj_report_cycles WHERE id = {ph} LIMIT 1", (cycle_id,))
            c_row = cur_c.fetchone()
            if c_row:
                cycle_info = dict(c_row)
    except Exception:
        pass

    # Processa com IA contextualizada com o ciclo
    ai_result = extract_answers_with_gemini(doc_text, meta, cycle_info=cycle_info)
    valido = ai_result.get("valido", True)
    motivo = ai_result.get("motivo_incompatibilidade") or ""
    respostas = ai_result.get("respostas") or {}

    # Bloqueio preventivo se não for válido e force=False
    if not valido and not force:
        return {
            "status": "mismatch",
            "message": f"A IA detectou que este Google Doc não corresponde ao formulário de {meta['name']}!",
            "motivo": motivo,
            "colaborador_detectado": ai_result.get("colaborador_detectado", "Desconhecido"),
            "doc_url": doc_url,
            "employee_name": meta["name"],
            "employee_key": employee_key,
            "sample": doc_text[:400]
        }

    is_blank = ai_result.get("documento_em_branco", False)
    total_resp = sum(1 for v in respostas.values() if (v or "").strip() and not str(v).startswith("[Não preenchido"))

    # Se for detectado como template virgem ou nenhuma resposta preenchida pelo colaborador
    if is_blank or total_resp == 0:
        return {
            "status": "blank",
            "message": f"O documento de {meta['name']} está no modelo padrão em branco (aguardando preenchimento). Nenhuma resposta foi enviada ainda.",
            "employee_name": meta["name"],
            "employee_key": employee_key,
            "total_respostas": 0,
            "resumo_doc": "Documento em branco (aguardando preenchimento do colaborador)",
            "doc_url": doc_url
        }

    # Salva respostas diretamente no formulário do M-One
    saved = save_or_submit_report(
        cycle_id=cycle_id,
        user_id=user_id,
        employee_key=employee_key,
        answers=respostas,
        is_draft=False  # Submissão direta oficial com opção de edição
    )

    # Grava o google_doc_url no registro
    try:
        with db() as conn:
            ph = "%s" if _is_pg(conn) else "?"
            conn.execute(
                f"UPDATE maj_employee_reports SET google_doc_url = {ph} WHERE cycle_id = {ph} AND employee_key = {ph}",
                (doc_url, cycle_id, employee_key)
            )
            conn.commit()
    except Exception:
        pass

    return {
        "status": "success",
        "message": f"Relatório de {meta['name']} sincronizado e entregue com sucesso via Google Doc!",
        "employee_name": meta["name"],
        "employee_key": employee_key,
        "total_respostas": total_resp,
        "resumo_doc": ai_result.get("resumo_doc", ""),
        "doc_url": doc_url,
        "is_forced": force and not valido,
        "report_id": saved.get("id")
    }


def sync_all_configured_docs(cycle_id: int, user_id: Optional[int] = None) -> Dict[str, Any]:
    """Sincroniza todos os colaboradores que possuem link de Google Doc cadastrado."""
    links = get_all_doc_links()
    results = []
    sucessos = 0
    em_branco = 0
    divergencias = 0
    erros = 0

    for key, meta in REPORTING_EMPLOYEES.items():
        if key == "fauzer":
            continue
        if key not in links:
            results.append({
                "employee_key": key,
                "name": meta["name"],
                "status": "skipped",
                "message": "Sem link cadastrado."
            })
            continue

        res = sync_single_employee_report(cycle_id, key, user_id=user_id)
        st = res.get("status")
        if st == "success":
            sucessos += 1
        elif st == "blank":
            em_branco += 1
        elif st == "mismatch":
            divergencias += 1
        else:
            erros += 1

        results.append({
            "employee_key": key,
            "name": meta["name"],
            "status": st,
            "details": res
        })

    return {
        "total": len(results),
        "sucessos": sucessos,
        "em_branco": em_branco,
        "divergencias": divergencias,
        "erros": erros,
        "results": results
    }
