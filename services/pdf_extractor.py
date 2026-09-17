"""
M-One PDF Text Extractor Service (services/pdf_extractor.py)
Extração em memória de textos digitais de documentos PDF (BL, Invoice, NF-e, Romaneio)
utilizando pypdf para enriquecer prompts de visão e servir de contingência rápida.
"""

from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)


def extract_text_from_pdf(content: bytes, max_pages: int = 15, max_chars: int = 40000) -> str:
    """Extrai texto legível de um fluxo de bytes PDF de forma segura.
    
    Args:
        content: Bytes brutos do arquivo PDF.
        max_pages: Número máximo de páginas a processar.
        max_chars: Limite total de caracteres para evitar estouro de tokens.

    Returns:
        String com o conteúdo textual extraído, ou vazia se for puramente digitalizado/imagem.
    """
    if not content or not content.startswith(b"%PDF"):
        return ""

    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        total_pages = len(reader.pages)
        if total_pages == 0:
            return ""

        extracted_pages: list[str] = []
        total_length = 0

        for idx in range(min(total_pages, max_pages)):
            try:
                page = reader.pages[idx]
                page_text = page.extract_text() or ""
                cleaned = page_text.strip()
                if cleaned:
                    page_header = f"=== PÁGINA {idx + 1} DE {total_pages} ===\n"
                    chunk = page_header + cleaned
                    extracted_pages.append(chunk)
                    total_length += len(chunk)
                    if total_length >= max_chars:
                        break
            except Exception as page_err:
                logger.debug("Erro ao extrair página %d: %s", idx, page_err)
                continue

        return "\n\n".join(extracted_pages).strip()
    except Exception as e:
        logger.warning("Falha ao analisar estrutura do PDF para texto: %s", e)
        return ""
