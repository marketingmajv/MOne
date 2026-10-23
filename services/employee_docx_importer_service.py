"""
M-One Employee DOCX AI Importer Service (services/employee_docx_importer_service.py)
Processa uploads de relatórios semanais enviados via arquivo Microsoft Word (.docx),
extrai o texto integral, valida aderência ao cargo com IA (Gemini) e popula o relatório no M-One.
Armazena o arquivo original com segurança para auditoria e download da Diretoria.
Segregação modular estrita (< 500 linhas).
"""

from __future__ import annotations

import io
import json
import logging
import os
import re
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from database import db
from services.employee_doc_importer_service import extract_answers_with_gemini
from services.employee_reports_data import REPORTING_EMPLOYEES, get_reporting_employee_meta
from services.employee_reports_service import _is_pg, ensure_reports_schema, save_or_submit_report

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
if os.environ.get("VERCEL"):
    DOCX_UPLOADS_DIR = Path("/tmp/uploads/relatorios_docx")
else:
    DOCX_UPLOADS_DIR = BASE_DIR / "uploads" / "relatorios_docx"
try:
    DOCX_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass


def ensure_docx_schema() -> None:
    """Garante a coluna docx_filename na tabela maj_employee_reports."""
    ensure_reports_schema()
    with db() as conn:
        try:
            conn.execute("ALTER TABLE maj_employee_reports ADD COLUMN docx_filename TEXT;")
            conn.commit()
        except Exception:
            pass


def extract_text_from_file_bytes(file_bytes: bytes, filename: str = "") -> Tuple[bool, str]:
    """
    Extrai o texto integral de um arquivo .docx (OpenXML) ou .txt (UTF-8 / Latin-1).
    Retorna (sucesso, texto_ou_mensagem_erro).
    """
    if not file_bytes or len(file_bytes) < 3:
        return False, "O arquivo enviado está vazio ou corrompido."

    lower_fn = (filename or "").lower()
    is_txt = lower_fn.endswith(".txt") or (not file_bytes.startswith(b"PK") and not lower_fn.endswith(".docx"))

    if is_txt:
        try:
            try:
                full_text = file_bytes.decode("utf-8").strip()
            except UnicodeDecodeError:
                full_text = file_bytes.decode("latin-1", errors="replace").strip()
            if not full_text:
                return False, "O arquivo de texto (.txt) está em branco."
            return True, full_text
        except Exception as ex:
            logger.error("Erro ao ler arquivo .txt: %s", ex)
            return False, f"Falha ao decodificar arquivo de texto (.txt): {ex}"

    # Processamento padrão de .docx (OpenXML ZIP)
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
            if "word/document.xml" not in z.namelist():
                return False, "O arquivo não possui a estrutura interna padrão de um documento Word (.docx)."

            xml_data = z.read("word/document.xml")
            tree = ET.fromstring(xml_data)
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

            paragraphs = []
            for p in tree.iterfind(".//w:p", ns):
                texts = []
                for node in p.iterfind(".//w:t", ns):
                    if node.text:
                        texts.append(node.text)
                p_text = "".join(texts).strip()
                if p_text:
                    paragraphs.append(p_text)

            full_text = "\n\n".join(paragraphs).strip()
            if not full_text:
                return False, "O documento Word (.docx) está em branco ou sem texto legível."

            return True, full_text
    except zipfile.BadZipFile:
        return False, "Formato inválido: o arquivo não é um documento .docx nem .txt legível."
    except Exception as ex:
        logger.error("Erro ao extrair texto do arquivo docx: %s", ex)
        return False, f"Falha ao ler documento: {ex}"


def extract_text_from_docx_bytes(docx_bytes: bytes) -> Tuple[bool, str]:
    """Alias de compatibilidade retroativa para código legado."""
    return extract_text_from_file_bytes(docx_bytes)


def get_docx_storage_path(cycle_code: str, employee_key: str, original_filename: str) -> Tuple[Path, str]:
    """Gera o caminho seguro no disco e o nome final do arquivo (.docx ou .txt) salvo."""
    safe_cycle = re.sub(r"[^a-zA-Z0-9-_]", "", cycle_code) or "ciclo"
    safe_key = re.sub(r"[^a-zA-Z0-9-_]", "", employee_key) or "emp"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = ".txt" if (original_filename or "").lower().endswith(".txt") else ".docx"
    final_filename = f"{safe_cycle}_{safe_key}_{timestamp}{ext}"

    target_dir = DOCX_UPLOADS_DIR / safe_cycle
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except Exception as ex:
        logger.warning("Falha ao criar diretório %s (usando fallback /tmp): %s", target_dir, ex)
        target_dir = Path("/tmp")
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
    return target_dir / final_filename, final_filename


def process_docx_upload(
    cycle_id: int,
    employee_key: str,
    file_bytes: bytes,
    original_filename: str = "",
    user_id: Optional[int] = None,
    force: bool = False
) -> Dict[str, Any]:
    """
    Processa o upload de um arquivo de relatório (.docx ou .txt):
    1. Valida colaborador e formato.
    2. Extrai texto puro.
    3. Audita e extrai respostas via IA (Gemini).
    4. Se divergente e não forçado, aciona o modal de divergência.
    5. Se válido, salva o arquivo físico e grava o relatório no M-One.
    """
    try:
        ensure_docx_schema()
        emp_key = employee_key.lower().strip()
        meta = get_reporting_employee_meta(emp_key)
        if not meta:
            return {"status": "error", "message": f"Colaborador '{emp_key}' não encontrado no sistema."}

        # 1. Extração de texto (suporta .docx e .txt)
        ok, doc_text = extract_text_from_file_bytes(file_bytes, original_filename)
        if not ok:
            return {"status": "error", "message": doc_text}

        # 2. Informações do ciclo
        cycle_info = None
        cycle_code = f"ciclo_{cycle_id}"
        try:
            with db() as conn:
                ph = "%s" if _is_pg(conn) else "?"
                cur_c = conn.execute(f"SELECT * FROM maj_report_cycles WHERE id = {ph} LIMIT 1", (cycle_id,))
                c_row = cur_c.fetchone()
                if c_row:
                    cycle_info = dict(c_row)
                    cycle_code = cycle_info.get("cycle_code") or cycle_code
        except Exception as e:
            logger.debug("Erro ao obter ciclo: %s", e)

        # 3. Processamento via IA
        ai_result = extract_answers_with_gemini(doc_text, meta, cycle_info=cycle_info)
        valido = ai_result.get("valido", True)
        motivo = ai_result.get("motivo_incompatibilidade") or ""
        respostas = ai_result.get("respostas") or {}

        # Bloqueio preventivo se não for válido e force=False
        if not valido and not force:
            return {
                "status": "mismatch",
                "message": f"A IA detectou que este arquivo não corresponde ao cargo de {meta['name']}!",
                "motivo": motivo,
                "colaborador_detectado": ai_result.get("colaborador_detectado", "Desconhecido"),
                "employee_name": meta["name"],
                "employee_key": emp_key,
                "source_type": "docx",
                "sample": doc_text[:400]
            }

        is_blank = ai_result.get("documento_em_branco", False)
        total_resp = sum(1 for v in respostas.values() if (v or "").strip() and not str(v).startswith("[Não preenchido"))

        if is_blank or total_resp == 0:
            return {
                "status": "blank",
                "message": f"O arquivo de {meta['name']} está no modelo padrão em branco (sem respostas preenchidas).",
                "employee_name": meta["name"],
                "employee_key": emp_key,
                "total_respostas": 0,
                "source_type": "docx"
            }

        # 4. Salva arquivo físico original para auditoria e download (resiliente a read-only filesystem)
        stored_filename = original_filename or f"{emp_key}.docx"
        try:
            target_path, stored_filename = get_docx_storage_path(cycle_code, emp_key, original_filename)
            target_path.write_bytes(file_bytes)
        except Exception as ex:
            logger.warning("Falha ao gravar arquivo no disco local/efêmero: %s", ex)

        # 5. Salva respostas no banco de dados M-One
        saved = save_or_submit_report(
            cycle_id=cycle_id,
            user_id=user_id,
            employee_key=emp_key,
            answers=respostas,
            is_draft=False
        )

        # 6. Grava nome do arquivo no relatório
        try:
            with db() as conn:
                ph = "%s" if _is_pg(conn) else "?"
                conn.execute(
                    f"UPDATE maj_employee_reports SET docx_filename = {ph} WHERE cycle_id = {ph} AND employee_key = {ph}",
                    (stored_filename, cycle_id, emp_key)
                )
                conn.commit()
        except Exception as ex:
            logger.error("Erro ao registrar docx_filename no banco: %s", ex)

        ext_label = "TXT" if stored_filename.lower().endswith(".txt") else "DOCX"
        return {
            "status": "success",
            "message": f"Relatório ({ext_label}) de {meta['name']} auditado e entregue com sucesso!",
            "employee_name": meta["name"],
            "employee_key": emp_key,
            "total_respostas": total_resp,
            "resumo_doc": ai_result.get("resumo_doc", ""),
            "docx_filename": stored_filename,
            "is_forced": force and not valido,
            "report_id": saved.get("id")
        }
    except Exception as ex:
        logger.error("Erro crítico ao processar upload de documento: %s", ex, exc_info=True)
        return {"status": "error", "message": f"Erro interno ao processar relatório: {str(ex)}"}


def find_docx_file(cycle_code: str, filename: str) -> Optional[Path]:
    """Localiza o arquivo .docx ou .txt físico para download."""
    if not filename:
        return None
    safe_filename = os.path.basename(filename)
    safe_cycle = re.sub(r"[^a-zA-Z0-9-_]", "", cycle_code) if cycle_code else ""

    candidates = [
        DOCX_UPLOADS_DIR / safe_cycle / safe_filename,
        DOCX_UPLOADS_DIR / safe_filename,
        Path("/tmp/uploads/relatorios_docx") / safe_cycle / safe_filename,
        Path("/tmp/uploads/relatorios_docx") / safe_filename,
        Path("/tmp") / safe_filename,
        BASE_DIR / "uploads" / "relatorios_docx" / safe_cycle / safe_filename,
        BASE_DIR / "uploads" / "relatorios_docx" / safe_filename,
    ]
    for c in candidates:
        try:
            if c.exists() and c.is_file():
                return c
        except Exception:
            pass
    return None

