import os
import json
import re
import base64
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta

BLING_OAUTH_AUTH_URL = "https://www.bling.com.br/Api/v3/oauth/authorize"
BLING_OAUTH_TOKEN_URL = "https://www.bling.com.br/Api/v3/oauth/token"
BLING_API_BASE_URL = "https://api.bling.com.br/v3"

def get_db_connection():
    from app import db
    return db()

def get_bling_integration_record():
    """Busca o registro de integração do Bling no banco de dados ou variáveis de ambiente."""
    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM integrations WHERE service_name = 'bling'").fetchone()
        if row:
            return dict(row)
    
    # Fallback para variáveis de ambiente
    cid = os.environ.get("BLING_CLIENT_ID", "").strip()
    csec = os.environ.get("BLING_CLIENT_SECRET", "").strip()
    if cid and csec:
        return {
            "service_name": "bling",
            "client_id": cid,
            "client_secret": csec,
            "access_token": os.environ.get("BLING_ACCESS_TOKEN", "").strip(),
            "refresh_token": os.environ.get("BLING_REFRESH_TOKEN", "").strip(),
            "token_expires_at": None,
            "settings_json": {}
        }
    return None

def save_bling_credentials(client_id: str, client_secret: str):
    """Grava as credenciais básicas do aplicativo Bling."""
    with get_db_connection() as conn:
        existing = conn.execute("SELECT id FROM integrations WHERE service_name = 'bling'").fetchone()
        if existing:
            conn.execute(
                "UPDATE integrations SET client_id = ?, client_secret = ?, updated_at = CURRENT_TIMESTAMP WHERE service_name = 'bling'",
                (client_id.strip(), client_secret.strip())
            )
        else:
            conn.execute(
                "INSERT INTO integrations (service_name, client_id, client_secret) VALUES ('bling', ?, ?)",
                (client_id.strip(), client_secret.strip())
            )
        conn.commit()

def save_bling_tokens(token_data: dict):
    """Armazena os tokens de acesso e refresh no banco de dados."""
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in = int(token_data.get("expires_in", 21600))
    expires_at = datetime.now() + timedelta(seconds=expires_in - 300) # 5 min margem

    with get_db_connection() as conn:
        existing = conn.execute("SELECT id FROM integrations WHERE service_name = 'bling'").fetchone()
        if existing:
            conn.execute(
                """UPDATE integrations 
                   SET access_token = ?, refresh_token = ?, token_expires_at = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE service_name = 'bling'""",
                (access_token, refresh_token, expires_at.isoformat())
            )
        else:
            conn.execute(
                """INSERT INTO integrations (service_name, access_token, refresh_token, token_expires_at)
                   VALUES ('bling', ?, ?, ?)""",
                (access_token, refresh_token, expires_at.isoformat())
            )
        conn.commit()

def get_bling_auth_url(redirect_uri: str, state: str = "m_one_auth") -> str:
    """Gera a URL de autorização OAuth 2.0 do Bling."""
    rec = get_bling_integration_record()
    client_id = rec.get("client_id") if rec else os.environ.get("BLING_CLIENT_ID", "")
    if not client_id:
        raise ValueError("Client ID do Bling não configurado.")
    
    params = {
        "response_type": "code",
        "client_id": client_id,
        "state": state
    }
    return f"{BLING_OAUTH_AUTH_URL}?{urllib.parse.urlencode(params)}"

def exchange_code_for_token(code: str, redirect_uri: str) -> dict:
    """Troca o authorization code pelo access token inicial do Bling."""
    rec = get_bling_integration_record()
    if not rec or not rec.get("client_id") or not rec.get("client_secret"):
        raise ValueError("Credenciais do Bling (Client ID / Client Secret) não encontradas.")

    client_id = rec["client_id"]
    client_secret = rec["client_secret"]
    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("utf-8")

    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code
    }).encode("utf-8")

    req = urllib.request.Request(
        BLING_OAUTH_TOKEN_URL,
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "Authorization": f"Basic {auth_header}"
        },
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        token_data = json.loads(resp.read().decode("utf-8"))
        save_bling_tokens(token_data)
        return token_data

def refresh_access_token(refresh_token: str, client_id: str, client_secret: str) -> str:
    """Atualiza o access token utilizando o refresh token."""
    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("utf-8")
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }).encode("utf-8")

    req = urllib.request.Request(
        BLING_OAUTH_TOKEN_URL,
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "Authorization": f"Basic {auth_header}"
        },
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        token_data = json.loads(resp.read().decode("utf-8"))
        save_bling_tokens(token_data)
        return token_data["access_token"]

def get_valid_access_token() -> str:
    """Retorna um access token válido, renovando automaticamente se expirado."""
    rec = get_bling_integration_record()
    if not rec or not rec.get("access_token"):
        raise ValueError("M-One não está conectado ao Bling. Clique em 'Conectar com Bling' primeiro.")

    access_token = rec["access_token"]
    refresh_token = rec.get("refresh_token")
    expires_at_str = rec.get("token_expires_at")
    client_id = rec.get("client_id")
    client_secret = rec.get("client_secret")

    # Verifica se precisa de refresh
    needs_refresh = False
    if expires_at_str:
        try:
            if isinstance(expires_at_str, str):
                expires_at = datetime.fromisoformat(expires_at_str.replace("Z", ""))
            else:
                expires_at = expires_at_str
            if datetime.now() >= expires_at:
                needs_refresh = True
        except Exception:
            pass

    if needs_refresh and refresh_token and client_id and client_secret:
        try:
            return refresh_access_token(refresh_token, client_id, client_secret)
        except Exception as e:
            print(f"Erro no refresh token do Bling: {e}")
            # Retorna o token atual e tenta chamada
            return access_token

    return access_token

def make_bling_api_request(endpoint: str, params = None, method: str = "GET") -> dict:
    """Executa requisição autenticada à API v3 do Bling."""
    token = get_valid_access_token()
    url = f"{BLING_API_BASE_URL}{endpoint}"
    if params:
        if isinstance(params, str):
            url += f"?{params}"
        else:
            url += f"?{urllib.parse.urlencode(params, doseq=True)}"

    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        },
        method=method
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        try:
            err_json = json.loads(err_body)
            raw_msg = err_json.get("error", {}).get("message") or err_json.get("message") or err_body
            if "insufficient_scope" in str(err_json).lower() or "insufficient_scope" in err_body.lower():
                msg = "Permissões de 'Pedidos de Venda' ou 'Notas Fiscais' pendentes no Bling (403: insufficient_scope).\n\nPara liberar em 1 minuto:\n1. No Bling, acesse: Preferências ⚙ -> Integrações -> Aplicativos -> Seu App\n2. Na aba 'Permissões', marque as opções: 'Pedidos de Venda' e 'Notas Fiscais'\n3. Salve no Bling e volte no M-One (Bling ERP) para clicar em 'Conectar com Bling' novamente."
            else:
                msg = f"Erro API Bling ({e.code}): {raw_msg}"
        except Exception:
            msg = f"Erro API Bling ({e.code}): {err_body}"
        raise RuntimeError(msg)

def search_bling_order(order_number: str) -> dict:
    """Busca um pedido de venda no Bling pelo número digitado."""
    num_str = str(order_number).strip()
    data = make_bling_api_request("/pedidos/vendas", params={"numero": num_str})
    pedidos = data.get("data", [])
    if not pedidos:
        # Tenta buscar sem filtro se for ID direto
        try:
            order_id = int(num_str)
            data_single = make_bling_api_request(f"/pedidos/vendas/{order_id}")
            if data_single and "data" in data_single:
                return parse_bling_order_data(data_single["data"])
        except Exception:
            pass
        return {"found": False, "message": f"Nenhum pedido encontrado no Bling com número '{num_str}'."}

    # Pega o primeiro e busca detalhes completos
    order_id = pedidos[0].get("id")
    detail_data = make_bling_api_request(f"/pedidos/vendas/{order_id}")
    return parse_bling_order_data(detail_data.get("data", pedidos[0]))

def find_matching_nfe_for_order(order: dict) -> str:
    """
    Busca a Nota Fiscal referente ao Pedido de Venda no Bling.
    Prioridades:
    1. Vínculo direto no objeto notaFiscal do pedido
    2. Vínculo direto ou menção ao número do pedido (ex: '2714') na NFe ou observações
    3. Comparação de cliente, valor e data para NFs não vinculadas expressamente
    """
    order_num = str(order.get("numero", "")).strip()
    order_id = str(order.get("id", "") or "").strip()
    order_total = float(order.get("total", 0) or 0)
    order_date_str = str(order.get("data", "")).strip()[:10]

    # 1. Se o próprio pedido já possui notaFiscal com número válido
    nfe_direct = order.get("notaFiscal") or {}
    direct_num = str(nfe_direct.get("numero", "")).strip()
    if direct_num and direct_num != "0":
        return f"NF-{direct_num}"

    contato = order.get("contato", {})
    contato_id = contato.get("id")

    # Lista de candidatos a NF no Bling
    candidates = []

    # 2. Busca NFes do cliente (limite 10)
    if contato_id:
        try:
            nfe_resp = make_bling_api_request("/nfe", params={"idContato": contato_id, "limite": 10})
            candidates.extend(nfe_resp.get("data", []))
        except Exception:
            pass

    # 3. Busca NFe pelo próprio número do pedido (caso a NF tenha o mesmo número do pedido)
    if order_num:
        try:
            nfe_num_resp = make_bling_api_request("/nfe", params={"numero": order_num})
            candidates.extend(nfe_num_resp.get("data", []))
        except Exception:
            pass

    if not candidates:
        return ""

    # Remover duplicados
    seen = set()
    unique_candidates = []
    for c in candidates:
        cid = c.get("id") or c.get("numero")
        if cid and cid not in seen:
            seen.add(cid)
            unique_candidates.append(c)

    scored_candidates = []

    for c in unique_candidates[:10]:
        cid = c.get("id")
        c_num = str(c.get("numero", "")).strip()
        if not c_num or c_num == "0":
            continue

        # Busca detalhes completos para ler 'venda' e 'observacoes'
        c_detail = c
        if cid:
            try:
                res_det = make_bling_api_request(f"/nfe/{cid}")
                if res_det and "data" in res_det:
                    c_detail = res_det["data"]
            except Exception:
                pass

        c_venda = c_detail.get("venda") or {}
        c_venda_id = str(c_venda.get("id", "") or "").strip()
        c_venda_num = str(c_venda.get("numero", "") or "").strip()
        c_obs = str(c_detail.get("observacoes", "") or "") + " " + str(c_detail.get("observacoesSistema", "") or "")
        c_total = float(c_detail.get("valorNota", 0) or c_detail.get("total", 0) or 0)
        c_date_str = str(c_detail.get("dataEmissao") or c_detail.get("data", "")).strip()[:10]

        # PRIO 1 EXPLICITA: Se a NFe está vinculada ao pedido ou menciona o número do pedido no texto
        if order_num:
            if (c_venda_num and c_venda_num == order_num) or (order_id and c_venda_id == order_id):
                return f"NF-{c_num}"
            if re.search(r'\b' + re.escape(order_num) + r'\b', c_obs, re.IGNORECASE):
                return f"NF-{c_num}"

        # PRIO 2: Comparação de valor e data para NFs sem vínculo textual explícito
        score = 0
        if order_date_str and c_date_str:
            try:
                d_order = datetime.strptime(order_date_str, "%Y-%m-%d")
                d_nf = datetime.strptime(c_date_str, "%Y-%m-%d")
                if d_nf < d_order:
                    continue  # Desqualifica apenas NFs sem vínculo textual que foram emitidas antes do pedido
            except Exception:
                pass

        if order_total > 0 and c_total > 0 and abs(order_total - c_total) <= 0.05:
            score += 50

        scored_candidates.append((score, c_num))

    if scored_candidates:
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        best_score, best_num = scored_candidates[0]
        if best_score >= 40:
            return f"NF-{best_num}"

    return ""


def parse_bling_order_data(order: dict) -> dict:
    """Normaliza os dados do pedido do Bling para o formulário do M-One."""
    contato = order.get("contato", {})
    cliente_nome = contato.get("nome", "")
    numero_pedido = str(order.get("numero", ""))
    total_venda = float(order.get("total", 0) or 0)
    data_venda = order.get("data", "")
    obs = order.get("observacoes", "") or ""

    # Varredura inteligente da Nota Fiscal vinculada ao Pedido
    nota_fiscal = find_matching_nfe_for_order(order)

    # Itens do pedido
    itens = []
    itens_raw = order.get("itens", [])
    for it in itens_raw:
        itens.append({
            "codigo": it.get("codigo", ""),
            "descricao": it.get("descricao", ""),
            "quantidade": it.get("quantidade", 1),
            "valor": float(it.get("valor", 0) or 0)
        })

    modelos_lista = [it["descricao"] for it in itens if it.get("descricao")]
    vehicle_model = ", ".join(modelos_lista) if modelos_lista else ""

    order_id = order.get("id")

    return {
        "found": True,
        "order_id": order_id,
        "order_number": numero_pedido,
        "customer": cliente_nome,
        "total_value": total_venda,
        "sold_at": data_venda,
        "invoice_number": nota_fiscal,
        "notes": obs,
        "items": itens,
        "vehicle_model": vehicle_model
    }

def search_bling_invoice(invoice_number: str) -> dict:
    """Busca uma Nota Fiscal no Bling pelo número."""
    clean_num = invoice_number.upper().replace("NF-", "").replace("NF", "").strip()
    data = make_bling_api_request("/nfe", params={"numero": clean_num})
    notas = data.get("data", [])
    if not notas:
        return {"found": False, "message": f"Nenhuma Nota Fiscal encontrada no Bling com número '{clean_num}'."}

    nfe_id = notas[0].get("id")
    detail = make_bling_api_request(f"/nfe/{nfe_id}")
    nfe = detail.get("data", notas[0])

    contato = nfe.get("contato", {})
    cliente = contato.get("nome", "")
    numero = f"NF-{nfe.get('numero', clean_num)}"
    total = float(nfe.get("valorNota", 0) or 0)
    data_emissao = (nfe.get("dataEmissao") or "")[:10]
    obs = nfe.get("observacoes", "") or ""

    return {
        "found": True,
        "invoice_id": nfe_id,
        "invoice_number": numero,
        "customer": cliente,
        "total_value": total,
        "sold_at": data_emissao,
        "notes": obs
    }

def sync_bling_products_stock() -> dict:
    """
    Sincroniza o estoque disponível de produtos cadastrados no M-One com a API v3 do Bling.
    Atualiza a coluna bling_stock no banco de dados do M-One.
    """
    # 1. Buscar produtos do Bling (até 10 páginas = 1000 produtos)
    all_bling_prods = []
    for page in range(1, 11):
        try:
            res = make_bling_api_request("/produtos", params={"limite": 100, "pagina": page, "criterio": 1})
            data = res.get("data", [])
            if not data:
                break
            all_bling_prods.extend(data)
            if len(data) < 100:
                break
        except Exception as e:
            print(f"Erro ao buscar produtos Bling (pagina {page}): {e}")
            break

    if not all_bling_prods:
        return {"success": False, "message": "Nenhum produto ativo encontrado no Bling.", "updated": 0}

    # 2. Buscar saldos de estoque em lotes de 50 produtos
    bling_stock_map = {}
    for i in range(0, len(all_bling_prods), 50):
        batch = all_bling_prods[i:i+50]
        ids = [p["id"] for p in batch if p.get("id")]
        if not ids:
            continue
        try:
            saldos_resp = make_bling_api_request("/estoques/saldos", params={"idsProdutos[]": ids})
            saldos = saldos_resp.get("data", [])
            for s in saldos:
                pid = s.get("produto", {}).get("id")
                sku = s.get("produto", {}).get("codigo")
                bling_stock_map[pid] = {
                    "sku": sku,
                    "physical": int(s.get("saldoFisicoTotal", 0) or 0),
                    "virtual": int(s.get("saldoVirtualTotal", 0) or 0)
                }
        except Exception as e:
            print(f"Erro ao buscar saldos do lote Bling: {e}")

    part_keywords = ['assento', 'motor', 'acelerador', 'display', 'pastilha', 'banco', 'peca', 'peça', 'roda', 'bateria', 'carregador', 'capacete', 'chassi', 'retrovisor']

    # 3. Atualizar no banco de dados do M-One
    updated_count = 0
    now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    details = []

    with get_db_connection() as conn:
        m_prods = conn.execute("SELECT id, name, sku FROM products").fetchall()
        for mp in m_prods:
            pid = mp["id"]
            m_name = str(mp["name"] or "").strip()
            m_sku = str(mp["sku"] or "").strip()
            matched_stock = 0
            matched_items = []

            for bp in all_bling_prods:
                b_id = bp.get("id")
                b_name = str(bp.get("nome", "") or "").strip()
                b_sku = str(bp.get("codigo", "") or "").strip()
                st_qty = bling_stock_map.get(b_id, {}).get("virtual", 0)

                b_name_lower = b_name.lower()
                m_name_lower = m_name.lower()

                # Ignora peças/acessórios se o produto M-One for modelo/veículo principal
                if any(kw in b_name_lower for kw in part_keywords) and not any(kw in m_name_lower for kw in part_keywords):
                    continue

                is_match = False
                if m_sku and b_sku and m_sku.lower() == b_sku.lower():
                    is_match = True
                elif m_name_lower in b_name_lower or b_name_lower in m_name_lower:
                    is_match = True
                elif m_name_lower.replace(" ", "") in b_name_lower.replace(" ", ""):
                    is_match = True

                if is_match:
                    matched_stock += st_qty
                    matched_items.append(f"{b_name} (Estoque: {st_qty})")

            conn.execute(
                "UPDATE products SET bling_stock = ?, bling_updated_at = ? WHERE id = ?",
                (matched_stock, now_iso, pid)
            )
            updated_count += 1
            details.append({"id": pid, "name": m_name, "stock": matched_stock, "matches": matched_items})

        conn.commit()

    return {
        "success": True,
        "message": f"Estoque de {updated_count} produtos sincronizado com o Bling com sucesso!",
        "updated": updated_count,
        "synced_at": now_iso,
        "details": details
    }

