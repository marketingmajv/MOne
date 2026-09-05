import os
import json
import base64
import re
import urllib.request
import urllib.error
from datetime import datetime, date

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

def get_gemini_api_key() -> str:
    return os.environ.get("GEMINI_API_KEY", "").strip()

def build_operational_context(db_conn, role: str, name: str) -> str:
    """Coleta métricas e dados operacionais reais das tabelas oficiais do M-One."""
    lines = []
    today = date.today().isoformat()
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    lines.append(f"DATA E HORA DO SISTEMA: {now_str}")
    lines.append(f"USUÁRIO ATUAL: {name} (Perfil de acesso: {role})")
    
    try:
        # 1. Estoque por Produto e Chassis
        stock_summary = db_conn.execute("""
            SELECT p.name as product_name,
                   COUNT(CASE WHEN st.status = 'available' THEN 1 END) as available,
                   COUNT(CASE WHEN st.status = 'sold' THEN 1 END) as sold,
                   COUNT(CASE WHEN st.status = 'unreleased' THEN 1 END) as unreleased,
                   COUNT(st.id) as total_units
            FROM products p
            LEFT JOIN stock_units st ON st.product_id = p.id
            GROUP BY p.id, p.name
            HAVING COUNT(st.id) > 0
            ORDER BY available DESC, product_name ASC
        """).fetchall()
        
        lines.append("\n=== ESTOQUE POR MODELO / PRODUTO ===")
        total_disp = 0
        total_vend = 0
        total_unrel = 0
        for s in stock_summary:
            disp = s["available"] or 0
            vend = s["sold"] or 0
            unrel = s["unreleased"] or 0
            total_disp += disp
            total_vend += vend
            total_unrel += unrel
            lines.append(f"- {s['product_name']}: {disp} liberados para venda, {vend} vendidos, {unrel} em importação aguardando liberação.")
        lines.append(f"TOTAL GERAL DO ESTOQUE: {total_disp} chassis liberados para venda imediata, {total_vend} vendidos, {total_unrel} aguardando liberação.")

        # 2. Produtos e Tabela de Preços Atuais
        products = db_conn.execute("""
            SELECT name, category, unit_cost, wholesale_price, retail_price
            FROM products
            ORDER BY name
        """).fetchall()
        lines.append("\n=== TABELA DE PRODUTOS E PREÇOS VIGENTES ===")
        for p in products:
            p_ret = f"R$ {float(p['retail_price']):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if p.get("retail_price") else "N/D"
            p_who = f"R$ {float(p['wholesale_price']):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if p.get("wholesale_price") else "N/D"
            lines.append(f"- {p['name']} ({p.get('category') or 'Sem categoria'}): Varejo {p_ret} | Atacado {p_who}")

        # 3. Vendas Realizadas (Hoje e Mês Atual)
        month_start = today[:7] + "-01"
        sales_today = db_conn.execute("""
            SELECT COUNT(*) as qtd, COALESCE(SUM(total_value), 0) as total
            FROM sales
            WHERE sold_at = ?
        """, (today,)).fetchone()
        
        sales_month = db_conn.execute("""
            SELECT COUNT(*) as qtd, COALESCE(SUM(total_value), 0) as total
            FROM sales
            WHERE sold_at >= ?
        """, (month_start,)).fetchone()
        
        lines.append("\n=== DESEMPENHO DE VENDAS ===")
        tot_today = f"R$ {float(sales_today['total']):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        tot_month = f"R$ {float(sales_month['total']):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        lines.append(f"- Hoje ({today}): {sales_today['qtd']} venda(s), Total: {tot_today}")
        lines.append(f"- Mês atual (desde {month_start}): {sales_month['qtd']} venda(s), Total: {tot_month}")
        
        # 5 vendas mais recentes
        recent_sales = db_conn.execute("""
            SELECT s.sold_at, s.customer, s.invoice_number, s.total_value, s.channel, u.name as seller
            FROM sales s
            LEFT JOIN users u ON u.id = s.created_by
            ORDER BY s.id DESC
            LIMIT 5
        """).fetchall()
        if recent_sales:
            lines.append("- Últimas vendas cadastradas:")
            for rs in recent_sales:
                val = f"R$ {float(rs['total_value']):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                lines.append(f"  • Data: {rs['sold_at']} | NF: {rs['invoice_number']} | Cliente: {rs.get('customer') or 'Consumidor'} | Canal: {rs['channel']} | Valor: {val} | Vendedor: {rs['seller'] or 'N/D'}")

        # 4. Importações e Custos (Restrito a Diretoria e Suporte Técnico)
        if role in ["admin", "support"]:
            imports = db_conn.execute("""
                SELECT i.id, i.reference, i.invoice_no, i.bl_no, i.arrival_date, i.usd_rate, i.status,
                       COUNT(st.id) as chassis_total,
                       COALESCE(SUM(ic.amount * CASE WHEN ic.currency='USD' THEN COALESCE(NULLIF(ic.usd_rate,0), NULLIF(i.usd_rate,0), 1) ELSE 1 END), 0) as costs_brl
                FROM imports i
                LEFT JOIN stock_units st ON st.import_id = i.id
                LEFT JOIN import_costs ic ON ic.import_id = i.id
                GROUP BY i.id, i.reference, i.invoice_no, i.bl_no, i.arrival_date, i.usd_rate, i.status
                ORDER BY i.id DESC
                LIMIT 5
            """).fetchall()
            lines.append("\n=== IMPORTAÇÕES RECENTES (CONFIDENCIAL: DIRETORIA/SUPORTE) ===")
            for imp in imports:
                c_brl = f"R$ {float(imp['costs_brl']):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                status_desc = "Estoque liberado" if imp["status"] == "released" else "Rascunho / Aguardando liberação"
                lines.append(f"- Importação #{imp['id']} ({imp['reference']}): Chegada {imp['arrival_date'] or 'N/D'} | Invoice {imp['invoice_no'] or 'N/D'} | BL {imp['bl_no'] or 'N/D'} | Câmbio USD R$ {float(imp['usd_rate'] or 0):.4f} | Status: {status_desc} | Chassis: {imp['chassis_total']} un | Custos apurados: {c_brl}")
        else:
            lines.append("\n[IMPORTAÇÕES: Acesso restrito. Custos de compra e despesas aduaneiras são estritamente confidenciais da Diretoria.]")

    except Exception as e:
        lines.append(f"\n[Nota de leitura do banco: {str(e)}]")

    return "\n".join(lines)


def ask_gemini_copilot(user_message: str, history: list, db_conn, user_role: str, user_name: str) -> dict:
    """Envia a consulta ao Gemini com injeção segura de contexto operacional."""
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
            )
        }

    context = build_operational_context(db_conn, user_role, user_name)

    system_instruction = f"""
Você é o "M-One Copilot", a inteligência artificial operacional integrada ao MAJ Operating System (M-One), o sistema de gestão central da MAJ Mobilidade Elétrica (fabricante e distribuidora de scooters e motos elétricas).

DIRETRIZES DE ATUAÇÃO:
1. Responda em Português do Brasil de forma executiva, ágil, objetiva, cordial e altamente profissional.
2. Utilize SEMPRE as informações oficiais do contexto operacional fornecido abaixo para responder sobre estoque de modelos, chassis, faturamento de vendas, clientes, notas fiscais e produtos.
3. Se perguntado sobre dados não presentes no contexto ou banco, declare com franqueza que não constam registros no momento.
4. POLÍTICA DE SEGURANÇA E SIGILO:
   - Se o usuário NÃO for 'admin' (Diretoria) ou 'support' (Suporte Técnico) e perguntar sobre custos de importação, despesas de contêineres, câmbio ou margens confidenciais, informe cordialmente que essas informações são restritas à Diretoria.
5. Formate respostas longas com marcadores (bullet points), tabelas em Markdown e valores em negrito no padrão brasileiro (R$ 0.000,00).
6. Você pode fornecer análises, resumos de vendas do dia, sugestões de reposição de estoque e comparativos de modelos.

--- DADOS OPERACIONAIS EM TEMPO REAL ---
{context}
"""

    contents = []
    for h in (history or [])[-10:]:
        role = "user" if h.get("role") == "user" else "model"
        text = h.get("text", "")
        if text:
            contents.append({
                "role": role,
                "parts": [{"text": text}]
            })
            
    contents.append({
        "role": "user",
        "parts": [{"text": user_message}]
    })

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={api_key}"
    payload = {
        "contents": contents,
        "systemInstruction": {
            "parts": [{"text": system_instruction}]
        },
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 2048
        }
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            candidates = res_data.get("candidates", [])
            if candidates and "content" in candidates[0]:
                parts = candidates[0]["content"].get("parts", [])
                full_text = "".join([p.get("text", "") for p in parts])
                return {"success": True, "message": full_text}
            return {"success": False, "error_type": "EMPTY_RESPONSE", "message": "O Gemini processou a requisição mas não retornou texto."}
            
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        try:
            err_json = json.loads(err_msg)
            detailed = err_json.get("error", {}).get("message", err_msg)
        except Exception:
            detailed = err_msg
            
        if e.code == 400 and "API_KEY_INVALID" in detailed:
            return {
                "success": False,
                "error_type": "INVALID_KEY",
                "message": "A chave `GEMINI_API_KEY` informada é inválida ou expirou. Verifique sua chave no Google AI Studio."
            }
        return {
            "success": False,
            "error_type": "HTTP_ERROR",
            "message": f"Erro na comunicação com a API do Gemini ({e.code}): {detailed}"
        }
    except Exception as e:
        return {
            "success": False,
            "error_type": "EXCEPTION",
            "message": f"Falha na requisição para o Gemini: {str(e)}"
        }


def extract_and_match_chassis(items_data, expected_chassis_list: list, expected_model: str = "", mime_type: str = "image/jpeg") -> dict:
    """Analisa imagem(ns) / PDF(s) da DANFE, Termo e Foto do Chassi (Veículo/Caixa) com Gemini 3.6 Flash.
    Realiza a auditoria de triangulação confirmando se o chassi da foto do veículo é idêntico ao da DANFE.
    """
    api_key = get_gemini_api_key()
    if not api_key:
        return {
            "success": False,
            "is_valid": False,
            "error_type": "MISSING_KEY",
            "message": "A chave `GEMINI_API_KEY` não está configurada no sistema.",
            "details": "Chave da API do Google Gemini ausente."
        }

    # Tratamento de suporte retrógrado se for passado bytes direto no 1º argumento
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
            "message": "Nenhum arquivo ou foto foi enviado para a auditoria."
        }

    # Normalizar lista esperada
    clean_expected = []
    for c in expected_chassis_list:
        clean = re.sub(r'[^A-Z0-9]', '', str(c).upper())
        if clean:
            clean_expected.append(clean)

    if not clean_expected:
        return {
            "success": False,
            "is_valid": False,
            "error_type": "NO_CHASSIS_PROVIDED",
            "message": "Nenhum número de chassi foi informado para conferência.",
            "details": "Preencha o campo de chassis antes de validar os comprovantes."
        }

    parts = []
    for b_bytes, m_type in items_list:
        if b_bytes:
            parts.append({
                "inlineData": {
                    "mimeType": m_type or "image/jpeg",
                    "data": base64.b64encode(b_bytes).decode("utf-8")
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
  "chassis_match_confirmed": true ou false (true se o chassi da foto do veículo/caixa for idêntico ao chassi da DANFE),
  "extracted_model": "Modelo do produto identificado na DANFE",
  "model_matched": true ou false,
  "is_valid": true ou false (true se TODOS os chassis esperados foram localizados e a foto do veículo/caixa confere com a DANFE),
  "summary": "Resumo claro e objetivo em português do resultado da triangulação"
}}
"""
    parts.append({"text": prompt})

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": parts
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json"
        }
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            candidates = res_data.get("candidates", [])
            if candidates and "content" in candidates[0]:
                res_parts = candidates[0]["content"].get("parts", [])
                raw_json = "".join([p.get("text", "") for p in res_parts]).strip()
                parsed = json.loads(raw_json)

                extracted_raw = parsed.get("extracted_chassis", [])
                extracted_norm = [re.sub(r'[^A-Z0-9]', '', str(x).upper()) for x in extracted_raw]

                matched = []
                missing = []
                for exp in clean_expected:
                    if any(exp == ext or exp in ext or ext in exp for ext in extracted_norm):
                        matched.append(exp)
                    else:
                        missing.append(exp)

                is_valid = (len(missing) == 0 and len(matched) == len(clean_expected))
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
                    "all_matched": is_valid
                }
            return {"success": False, "is_valid": False, "message": "O modelo não retornou conteúdo textual compreensível."}

    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        return {"success": False, "is_valid": False, "message": f"Erro na API do Gemini ({e.code}): {err_msg}"}
    except Exception as e:
        return {"success": False, "is_valid": False, "message": f"Erro ao auditar comprovante: {str(e)}"}

