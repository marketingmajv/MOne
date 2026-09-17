"""
M-One Gemini AI Service (gemini_service.py)
Serviços de IA para Copilot Operacional, Triangulação de Chassis, Análise de Comprovantes
e Leitura de Documentos de Importação (BL, Invoices, NF-e) com failover resiliente.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
from typing import Any

from services.copilot_context import build_operational_context
from services.gemini_client import (
    DEFAULT_GEMINI_KEY,
    execute_gemini_payload,
    get_candidate_models,
    get_gemini_api_key,
)
from services.pdf_extractor import extract_text_from_pdf

logger = logging.getLogger(__name__)

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")

PAYMENT_CATEGORIES = [
    "Importações & Desembaraço",
    "Lojas & Aluguéis",
    "Oficina & Peças",
    "Folha & Pró-Labore",
    "Marketing & Anúncios",
    "Impostos & Taxas",
    "Utilidades & Serviços",
    "Frete & Logística",
    "Manutenção & Infraestrutura",
    "Outras Despesas Operacionais",
]

ACCOUNTS_LIST = [
    "PhntonPay",
    "Conta Davi",
    "Sicoob Maj Colatina",
    "Sicoob Maj Antiga em Vitória",
    "Sicoob Maj Vitória",
    "Sicoob Maj Veículos",
    "Sicoob MAP Colatina",
    "Conta Jam",
    "Conta Geysa",
    "Caixa Dinheiro Marisa",
    "Cartão Warley",
    "Outro Cartão / Conta",
]

PAYMENT_METHODS = [
    "Pix",
    "Transferência Bancária (TED/DOC)",
    "Cartão de Crédito",
    "Cartão de Débito",
    "Dinheiro em Espécie",
]


def ask_gemini_copilot(user_message: str, history: list, db_conn, user_role: str, user_name: str) -> dict:
    """Envia a consulta ao Gemini com injeção segura de contexto operacional e failover resiliente."""
    api_key = get_gemini_api_key()
    if not api_key:
        return {
            "success": False,
            "error_type": "MISSING_KEY",
            "message": (
                "A chave da API do Google Gemini (`GEMINI_API_KEY`) ainda não foi configurada no ambiente do sistema.\n\n"
                "### Como ativar o Copilot com sua chave gratuita em 1 minuto:\n"
                "1. Acesse o **[Google AI Studio](https://aistudio.google.com/)**.\n"
                "2. Faça login com qualquer conta Google.\n"
                "3. Clique em **Get API key** (Obter chave) e selecione **Create API key**.\n"
                "4. Insira a chave no arquivo `.env` do servidor:\n"
                "   ```bash\n"
                "   GEMINI_API_KEY=sua_chave_gerada_aqui\n"
                "   ```\n"
                "5. E nas variáveis de ambiente do projeto na Vercel para produção."
            ),
        }

    context = build_operational_context(db_conn, user_role, user_name)

    system_instruction = f"""
Você é o "M-One Copilot", o assistente de inteligência operacional de alta precisão da MAJ Mobilidade Elétrica (fabricante e distribuidora de motos, triciclos e veículos elétricos).
Seu objetivo é fornecer respostas claras, estruturadas, profissionais e acionáveis sobre as operações da empresa.

DIRETRIZES DE ATUAÇÃO E SEGURANÇA:
1. Use APENAS os dados operacionais reais fornecidos abaixo no contexto. Se não encontrar uma informação ou se o dado for ambíguo, diga educadamente que não consta no banco de dados.
2. NUNCA invente números, vendas, chassis ou produtos que não existam nas tabelas.
3. Se o perfil for 'seller' ou 'finance', NÃO revele custos de compra das importações ou custos unitários de fábrica. Apenas informe preços de tabela e estoque liberado.
4. Responda em português fluente do Brasil, formatando em Markdown amigável (tabelas, bullet points, valores em R$).
5. Seja direto e objetivo, sem enrolação. Sempre indique os números consolidados.
6. Você pode fornecer análises, resumos de vendas do dia, sugestões de reposição de estoque e comparativos de modelos.

--- DADOS OPERACIONAIS EM TEMPO REAL ---
{context}
"""

    contents = []
    for h in (history or [])[-10:]:
        role = "user" if h.get("role") == "user" else "model"
        text = h.get("text", "")
        if text:
            contents.append({"role": role, "parts": [{"text": text}]})

    contents.append({"role": "user", "parts": [{"text": user_message}]})

    payload = {
        "contents": contents,
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2048},
    }

    res = execute_gemini_payload(payload, api_key=api_key, timeout=30)
    if res.get("success"):
        return {"success": True, "message": res.get("text", "")}

    return {
        "success": False,
        "error_type": res.get("error_type", "HTTP_ERROR"),
        "message": res.get("message", "Falha na requisição para o Gemini."),
    }


def extract_and_match_chassis(
    items_data,
    expected_chassis_list: list,
    expected_model: str = "",
    mime_type: str = "image/jpeg",
) -> dict:
    """Analisa imagem(ns) / PDF(s) da DANFE, Termo e Foto do Chassi com Gemini.
    Realiza a auditoria de triangulação confirmando se o chassi da foto do veículo é idêntico ao da DANFE.
    """
    api_key = get_gemini_api_key()
    if not api_key:
        return {
            "success": False,
            "is_valid": False,
            "error_type": "MISSING_KEY",
            "message": "A chave `GEMINI_API_KEY` não está configurada no sistema.",
            "details": "Chave da API do Google Gemini ausente.",
        }

    if isinstance(items_data, (bytes, bytearray)):
        items_list = [(bytes(items_data), mime_type if isinstance(mime_type, str) else "image/jpeg")]
    elif isinstance(items_data, list):
        items_list = items_data
    else:
        items_list = []

    if not items_list:
        return {
            "success": False,
            "is_valid": False,
            "error_type": "NO_DOCUMENTS",
            "message": "Nenhum arquivo ou foto foi enviado para a auditoria.",
        }

    clean_expected = []
    for c in expected_chassis_list:
        clean = re.sub(r"[^A-Z0-9]", "", str(c).upper())
        if clean:
            clean_expected.append(clean)

    if not clean_expected:
        return {
            "success": False,
            "is_valid": False,
            "error_type": "NO_CHASSIS_PROVIDED",
            "message": "Nenhum número de chassi foi informado para conferência.",
            "details": "Preencha o campo de chassis antes de validar os comprovantes.",
        }

    parts = []
    for b_bytes, m_type in items_list:
        if b_bytes:
            parts.append({
                "inlineData": {
                    "mimeType": m_type or "image/jpeg",
                    "data": base64.b64encode(b_bytes).decode("utf-8"),
                }
            })

    prompt = f"""
Você é um auditor de documentação veicular e conferência fiscal da MAJ Mobilidade Elétrica.
Analise as imagens e documentos PDF anexos (DANFE da Nota Fiscal, Foto da Plaqueta/Etiqueta do Veículo ou Caixa, e Termo de Entrega).

OBJETIVO DA AUDITORIA DE TRIANGULAÇÃO:
1. Rastrear o número do chassi gravado/estampado na FOTO DO VEÍCULO / CAIXA e o número do chassi impresso na DANFE da Nota Fiscal.
2. Confirmar se o chassi da FOTO DO VEÍCULO/CAIXA é EXATAMENTE O MESMO CHASSI da DANFE e da lista de chassis digitada pelo vendedor.
3. Rastrear o modelo do veículo na DANFE e conferir se corresponde ao modelo informado no pedido.

CHASSIS INFORMADOS NA VENDA QUE DEVEM CONSTAR NOS COMPROVANTES:
{json.dumps(clean_expected, indent=2)}

MODELO DE VEÍCULO ESPERADO NO PEDIDO / CADASTRO:
"{expected_model or 'Não especificado'}"

DIRETRIZES DE RESPOSTA JSON ESTRITA:
Responda ESTRITAMENTE em formato JSON com o seguinte schema:
{{
  "document_type": "Descrição dos comprovantes analisados (ex: DANFE NF-e + Foto do Chassi do Veículo)",
  "extracted_chassis": ["lista de todos os chassis veiculares encontrados nas fotos e na DANFE"],
  "matched_chassis": ["chassis esperados que foram localizados nos comprovantes"],
  "missing_chassis": ["chassis esperados que NÃO foram encontrados nos comprovantes"],
  "vehicle_photo_chassis": "Número do chassi lido na foto da plaqueta do veículo ou caixa",
  "danfe_chassis": "Número do chassi lido na DANFE",
  "chassis_match_confirmed": true,
  "extracted_model": "Modelo do produto identificado na DANFE",
  "model_matched": true,
  "is_valid": true,
  "summary": "Resumo claro e objetivo em português do resultado da triangulação"
}}
"""
    parts.append({"text": prompt})

    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
    }

    res = execute_gemini_payload(payload, api_key=api_key, timeout=40)
    if not res.get("success"):
        return {"success": False, "is_valid": False, "message": res.get("message", "Falha na auditoria.")}

    parsed = res.get("data") or {}
    extracted_raw = parsed.get("extracted_chassis", [])
    extracted_norm = [re.sub(r"[^A-Z0-9]", "", str(x).upper()) for x in extracted_raw]

    matched = []
    missing = []
    for exp in clean_expected:
        if any(exp == ext or exp in ext or ext in exp for ext in extracted_norm):
            matched.append(exp)
        else:
            missing.append(exp)

    is_valid = len(missing) == 0 and len(matched) == len(clean_expected)
    if parsed.get("is_valid") is True and len(clean_expected) > 0:
        is_valid = True

    return {
        "success": True,
        "is_valid": is_valid,
        "document_type": parsed.get("document_type", "Comprovante / Documento"),
        "extracted_chassis": extracted_raw,
        "matched_chassis": matched if matched else parsed.get("matched_chassis", []),
        "missing_chassis": missing if not is_valid else [],
        "vehicle_photo_chassis": parsed.get("vehicle_photo_chassis", ""),
        "danfe_chassis": parsed.get("danfe_chassis", ""),
        "chassis_match_confirmed": parsed.get("chassis_match_confirmed", True),
        "extracted_model": parsed.get("extracted_model", ""),
        "model_matched": parsed.get("model_matched", True),
        "summary": parsed.get("summary", "Conferência de triangulação de chassis e modelo concluída."),
        "all_matched": is_valid,
    }


def analyze_payment_receipt(image_bytes: bytes, mime_type: str = "image/jpeg", form_data: dict | None = None) -> dict:
    """Analisa comprovante de pagamento / Nota Fiscal / Recibo com Gemini e failover resiliente."""
    api_key = get_gemini_api_key()
    if not api_key:
        return {"success": False, "message": "A chave GEMINI_API_KEY não está configurada no servidor."}

    form_data = form_data or {}
    b64_data = base64.b64encode(image_bytes).decode("utf-8")

    categories_str = ", ".join([f'"{c}"' for c in PAYMENT_CATEGORIES])
    accounts_str = ", ".join([f'"{a}"' for a in ACCOUNTS_LIST])
    methods_str = ", ".join([f'"{m}"' for m in PAYMENT_METHODS])

    prompt = f"""
Você é o auditor de notas fiscais e comprovantes de pagamento do grupo MAJ Mobilidade Elétrica.
EXAMINE O COMPROVANTE / NOTA FISCAL / RECIBO ANEXO E EXTRAIA TODOS OS DADOS COM PRECISÃO:

1. CATEGORIA SUGERIDA DO NEGÓCIO:
Escolha exatamente UMA das categorias abaixo que melhor corresponda à despesa:
[{categories_str}]

2. CONTA / ORIGEM SUGERIDA:
Escolha exatamente UMA das opções abaixo ou identifique a conta/banco/cartão se legível:
[{accounts_str}]

3. FORMA DE PAGAMENTO SUGERIDA:
Escolha exatamente UMA das opções abaixo:
[{methods_str}]

4. FINAL DO CARTÃO (SE APLICÁVEL):
Se for pagamento em cartão de crédito/débito, extraia os 4 últimos dígitos do cartão. Caso contrário, retorne "".

5. FORNECEDOR / RAZÃO SOCIAL:
Nome da empresa/fornecedor ou favorecido do pagamento.

6. NÚMERO DA NOTA FISCAL / RECIBO:
Número da NF-e, NFS-e, comprovante Pix ou recibo.

7. VALOR TOTAL PAGO (R$):
Valor numérico do pagamento (ex: 1250.00).

8. DATA DO PAGAMENTO:
Data no formato YYYY-MM-DD.

9. AUDITORIA DE DIVERGÊNCIAS CRUZADAS:
- Valor no formulário: {form_data.get('amount', 'Não informado')}
- Data no formulário: {form_data.get('paid_at', 'Não informada')}
- Categoria no formulário: {form_data.get('category', 'Não informada')}
- Conta no formulário: {form_data.get('account', 'Não informada')}
- Forma no formulário: {form_data.get('payment_method', 'Não informada')}
- Final cartão no formulário: {form_data.get('card_last4', 'Não informado')}

FORMATO DA RESPOSTA (JSON ESTRITO):
{{
  "suggested_category": "Categoria da lista acima",
  "suggested_account": "Conta/Origem identificada",
  "payment_method": "Pix / Transferência Bancária (TED/DOC) / Cartão de Crédito / Cartão de Débito / Dinheiro em Espécie",
  "card_last4": "últimos 4 dígitos ou vazio",
  "supplier": "Nome do Fornecedor / Favorecido",
  "document_no": "Número da NF ou Recibo",
  "extracted_amount": 0.00,
  "extracted_date": "YYYY-MM-DD",
  "has_divergence": false,
  "divergences": [],
  "summary": "Resumo executivo do comprovante em português"
}}
"""

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"inlineData": {"mimeType": mime_type or "image/jpeg", "data": b64_data}},
                    {"text": prompt},
                ],
            }
        ],
        "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
    }

    res = execute_gemini_payload(payload, api_key=api_key, timeout=35)
    if res.get("success") and res.get("data"):
        return {"success": True, "data": res["data"]}

    return {"success": False, "message": res.get("message", "Falha na análise do comprovante.")}


def analyze_import_documents(doc_items: list) -> dict:
    """Analisa documentos de importação (Invoice, BL, NF Entrada, Planilha de Chassis) via Gemini com failover resiliente.
    Extrai identificador/ref contêiner, número da invoice, fornecedor, vendedor, valor USD, número BL, NF Entrada, data de chegada e chassis.
    """
    if not doc_items:
        return {"success": False, "message": "Nenhum documento fornecido para análise da IA."}

    parts: list[dict[str, Any]] = []
    extracted_text_blocks: list[str] = []

    for doc in doc_items:
        raw_bytes = doc.get("bytes") or b""
        mime = doc.get("mime_type") or "application/pdf"
        fname = doc.get("filename") or "documento"

        # Extração de texto digital em memória com pypdf se for PDF
        if mime == "application/pdf" or fname.lower().endswith(".pdf"):
            pdf_text = extract_text_from_pdf(raw_bytes)
            if pdf_text:
                extracted_text_blocks.append(f"--- TEXTO EXTRAÍDO DO PDF ({fname}) ---\n{pdf_text}")

        # Anexa dados visuais multimodais
        b64_data = base64.b64encode(raw_bytes).decode("utf-8")
        parts.append({
            "inlineData": {
                "mimeType": mime,
                "data": b64_data,
            }
        })

    prompt_context = ""
    if extracted_text_blocks:
        prompt_context = (
            "\n\n--- DADOS TEXTUAIS EXTRAÍDOS NATIVAMENTE DOS ARQUIVOS (REFERÊNCIA DE MÁXIMA PRECISÃO) ---\n"
            + "\n\n".join(extracted_text_blocks)
            + "\n-----------------------------------------------------------------------------------------\n"
        )

    prompt = f"""
Você é o especialista sênior de comércio exterior e auditoria aduaneira da MAJ Mobilidade Elétrica.
EXAMINE CUIDADOSAMENTE OS DOCUMENTOS DE IMPORTAÇÃO ANEXADOS (Bill of Lading - BL, Commercial Invoice, Nota Fiscal de Entrada ou Planilha de Chassis) E EXTRAIA TODOS OS CAMPOS COM MÁXIMA PRECISÃO:
{prompt_context}
DIRETRIZES FUNDAMENTAIS DE EXTRAÇÃO:

1. NÚMERO DO BL (BILL OF LADING):
   Localize o campo "Bill of Lading No.", "B/L No." ou "Bill of Lading Number" (exemplo: "DWSE26070035", "COSU6321908230").
   Extraia esse código exato sem espaços adicionais.

2. REFERÊNCIA / IDENTIFICADOR DO CONTÊINER / IMPORTAÇÃO:
   - Se houver um código de lote ou contêiner específico (ex: "CONT-2026-01", "MSKU9876543"), use-o.
   - REGRA MANDATÓRIA: Se for um Bill of Lading (BL) ou não houver um código de contêiner separado, UTILIZE O PRÓPRIO NÚMERO DO BILL OF LADING (ex: "DWSE26070035") como Identificador / Referência da importação!

3. NÚMERO DA INVOICE:
   Extraia o número oficial da Commercial Invoice (ex: "INV-2026-8899", "PI2026-01").

4. NOME DO FORNECEDOR / FABRICANTE:
   Razão social completa da fábrica/empresa exportadora (ex: "Zhejiang Leike Electric Vehicle Co., Ltd.", "Shipper / Exporter").

5. NOME DO VENDEDOR / CONTATO COMERCIAL:
   Nome do vendedor, representante ou contato que assina/consta na invoice (ex: "Chen", "Linda", "Jack").

6. VALOR TOTAL DA INVOICE EM DÓLAR (USD):
   Valor numérico total em dólares americanos (ex: 48500.00).

7. NÚMERO DA NOTA FISCAL DE ENTRADA:
   Número da NF-e de entrada ou chave de acesso legível (ex: "00987").

8. DATA PREVISTA DE CHEGADA OU DATA DO DOCUMENTO (YYYY-MM-DD):
   Data de emissão da invoice, embarque do BL ("Date of Issue" / "Shipped on Board") ou chegada estimada no formato YYYY-MM-DD.

9. LISTA DE CHASSIS LOCALIZADOS:
   Lista com todos os números de chassi legíveis nos documentos.

FORMATO DA RESPOSTA (RETORNE APENAS JSON ESTRITO):
{{
  "reference": "Referência do contêiner ou o próprio número do BL (ex: DWSE26070035)",
  "invoice_no": "Número da Invoice",
  "supplier_name": "Nome do Fornecedor / Fabricante",
  "seller_name": "Nome do Vendedor / Contato Comercial",
  "invoice_amount_usd": 0.00,
  "bl_no": "Número do BL (ex: DWSE26070035)",
  "nf_entry": "Número da NF Entrada",
  "arrival_date": "YYYY-MM-DD",
  "extracted_chassis": ["CHASSI1", "CHASSI2"],
  "summary": "Resumo sintético em português dos dados extraídos dos documentos"
}}
"""
    parts_with_prompt = list(parts)
    parts_with_prompt.append({"text": prompt})

    payload = {
        "contents": [{"role": "user", "parts": parts_with_prompt}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }

    # Executa com failover automático e retries
    res = execute_gemini_payload(payload, timeout=40)

    # Se falhou e tínhamos texto digital extraído, tenta fallback de emergência usando apenas texto
    if not res.get("success") and extracted_text_blocks:
        logger.info("Acionando fallback de análise puramente textual para documentos de importação...")
        text_only_payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }
        res = execute_gemini_payload(text_only_payload, timeout=25)

    if not res.get("success"):
        return {"success": False, "message": f"Erro na análise de documentos da importação: {res.get('message')}"}

    data = res.get("data")
    if not data and res.get("text"):
        try:
            data = json.loads(res["text"])
        except Exception:
            data = None

    if not data:
        return {"success": False, "message": "O modelo Gemini não retornou resposta estruturada dos documentos."}

    # Garantia de consistência da regra do usuário: se reference estiver vazio e bl_no estiver presente, usa bl_no
    if not data.get("reference") and data.get("bl_no"):
        data["reference"] = data["bl_no"]

    return {
        "success": True,
        "data": data,
        "model_used": res.get("model_used"),
    }
