import os
import json
import base64
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta

BLING_OAUTH_AUTH_URL = "https://www.bling.com.br/Api/v3/oauth/authorize"
BLING_OAUTH_TOKEN_URL = "https://www.bling.com.br/Api/v3/oauth/token"
BLING_API_BASE_URL = "https://www.bling.com.br/Api/v3"

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

def make_bling_api_request(endpoint: str, params: dict = None, method: str = "GET") -> dict:
    """Executa requisição autenticada à API v3 do Bling."""
    token = get_valid_access_token()
    url = f"{BLING_API_BASE_URL}{endpoint}"
    if params:
        url += f"?{urllib.parse.urlencode(params)}"

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
            msg = err_json.get("error", {}).get("message") or err_json.get("message") or err_body
        except Exception:
            msg = err_body
        raise RuntimeError(f"Erro API Bling ({e.code}): {msg}")

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

def parse_bling_order_data(order: dict) -> dict:
    """Normaliza os dados do pedido do Bling para o formulário do M-One."""
    contato = order.get("contato", {})
    cliente_nome = contato.get("nome", "")
    numero_pedido = str(order.get("numero", ""))
    total_venda = float(order.get("total", 0) or 0)
    data_venda = order.get("data", "")
    obs = order.get("observacoes", "") or ""

    # Verifica se há nota fiscal gerada no pedido
    nota_fiscal = ""
    nfe_data = order.get("notaFiscal") or {}
    if nfe_data and nfe_data.get("numero"):
        nota_fiscal = f"NF-{nfe_data['numero']}"
    elif "transporte" in order and order["transporte"].get("etiqueta"):
        pass

    # Se não veio número de NF no pedido, tenta buscar se tem nfe vinculada
    order_id = order.get("id")
    if not nota_fiscal and order_id:
        try:
            nfe_resp = make_bling_api_request("/nfe", params={"idContato": contato.get("id"), "limit": 5})
            for nf in nfe_resp.get("data", []):
                if nf.get("numero"):
                    nota_fiscal = f"NF-{nf['numero']}"
                    break
        except Exception:
            pass

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

    return {
        "found": True,
        "order_id": order_id,
        "order_number": numero_pedido,
        "customer": cliente_nome,
        "total_value": total_venda,
        "sold_at": data_venda,
        "invoice_number": nota_fiscal,
        "notes": obs,
        "items": itens
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
