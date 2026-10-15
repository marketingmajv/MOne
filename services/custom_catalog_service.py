"""
M-One Custom Catalogs Service (services/custom_catalog_service.py)
Gerencia a distribuição de catálogos personalizados para clientes e parceiros (White-label ou Co-branded),
com clonagem de matrizes (Outlet MAJ ou MAJ Atacado CNPJ), precificação flexível (sem preço, valor fixo ou margem %),
controle de estoque, links curtos (/c/<slug>) e mensuração de acessos e cliques no WhatsApp.
Em estrita conformidade com as diretrizes modulares (< 500 linhas) do M-One.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
from datetime import datetime
from typing import Any, Dict, List, Optional

from database import db
from services.atacado_service import get_all_atacado_items
from services.outlet_service import get_all_outlet_items

logger = logging.getLogger(__name__)

_custom_catalogs_schema_ensured = False


def _is_pg(conn) -> bool:
    return hasattr(conn, "conn") or type(conn).__name__ == "PGConnWrapper"


def ensure_custom_catalogs_schema():
    """Garante a existência da tabela de catálogos personalizados no Supabase/SQLite."""
    global _custom_catalogs_schema_ensured
    if _custom_catalogs_schema_ensured:
        return

    with db() as conn:
        pg = _is_pg(conn)
        table_sql = """
        CREATE TABLE IF NOT EXISTS maj_custom_catalogs (
            id SERIAL PRIMARY KEY,
            slug VARCHAR(100) UNIQUE NOT NULL,
            title VARCHAR(150) NOT NULL,
            client_name VARCHAR(150) NOT NULL DEFAULT '',
            source_matrix VARCHAR(30) NOT NULL DEFAULT 'outlet',
            pricing_mode VARCHAR(30) NOT NULL DEFAULT 'fixed_matrix',
            percentage_markup NUMERIC(5,2) DEFAULT 0.00,
            sync_stock BOOLEAN DEFAULT TRUE,
            is_white_label BOOLEAN DEFAULT TRUE,
            logo_url TEXT DEFAULT '',
            whatsapp_number VARCHAR(30) NOT NULL DEFAULT '',
            whatsapp_message_template TEXT DEFAULT '',
            custom_item_overrides_json TEXT DEFAULT '{}',
            is_active BOOLEAN DEFAULT TRUE,
            expires_at TIMESTAMP WITHOUT TIME ZONE,
            views_count INTEGER DEFAULT 0,
            whatsapp_clicks_count INTEGER DEFAULT 0,
            created_by INTEGER,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_custom_catalogs_slug ON maj_custom_catalogs(slug);
        """ if pg else """
        CREATE TABLE IF NOT EXISTS maj_custom_catalogs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            client_name TEXT NOT NULL DEFAULT '',
            source_matrix TEXT NOT NULL DEFAULT 'outlet',
            pricing_mode TEXT NOT NULL DEFAULT 'fixed_matrix',
            percentage_markup REAL DEFAULT 0.00,
            sync_stock BOOLEAN DEFAULT 1,
            is_white_label BOOLEAN DEFAULT 1,
            logo_url TEXT DEFAULT '',
            whatsapp_number TEXT NOT NULL DEFAULT '',
            whatsapp_message_template TEXT DEFAULT '',
            custom_item_overrides_json TEXT DEFAULT '{}',
            is_active BOOLEAN DEFAULT 1,
            expires_at TIMESTAMP,
            views_count INTEGER DEFAULT 0,
            whatsapp_clicks_count INTEGER DEFAULT 0,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_custom_catalogs_slug ON maj_custom_catalogs(slug);
        """
        try:
            conn.executescript(table_sql)
            conn.commit()
        except Exception as e:
            logger.debug("Schema stmt notice: %s", e)

        _custom_catalogs_schema_ensured = True


def sanitize_slug(text: str) -> str:
    """Sanitiza string para criar slug limpo de URL (ex: 'Loja do Pedro' -> 'loja-do-pedro')."""
    s = text.lower().strip()
    s = re.sub(r"[àáâãäå]", "a", s)
    s = re.sub(r"[èéêë]", "e", s)
    s = re.sub(r"[ìíîï]", "i", s)
    s = re.sub(r"[òóôõö]", "o", s)
    s = re.sub(r"[ùúûü]", "u", s)
    s = re.sub(r"[ç]", "c", s)
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "catalogo"


def list_custom_catalogs(active_only: bool = False) -> List[Dict[str, Any]]:
    """Retorna a lista de todos os catálogos personalizados cadastrados."""
    ensure_custom_catalogs_schema()
    with db() as conn:
        pg = _is_pg(conn)
        sql = "SELECT * FROM maj_custom_catalogs"
        if active_only:
            sql += " WHERE is_active = TRUE" if pg else " WHERE is_active = 1"
        sql += " ORDER BY id DESC"
        rows = conn.execute(sql).fetchall()
        catalogs = []
        for r in rows:
            d = dict(r)
            try:
                d["overrides"] = json.loads(d.get("custom_item_overrides_json") or "{}")
            except Exception:
                d["overrides"] = {}
            catalogs.append(d)
        return catalogs


def get_custom_catalog_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    """Recupera um catálogo personalizado pelo slug público."""
    ensure_custom_catalogs_schema()
    clean_slug = sanitize_slug(slug)
    with db() as conn:
        pg = _is_pg(conn)
        ph = "%s" if pg else "?"
        cur = conn.execute(f"SELECT * FROM maj_custom_catalogs WHERE slug = {ph} LIMIT 1", (clean_slug,))
        row = cur.fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["overrides"] = json.loads(d.get("custom_item_overrides_json") or "{}")
        except Exception:
            d["overrides"] = {}
        return d


def get_custom_catalog_by_id(catalog_id: int) -> Optional[Dict[str, Any]]:
    """Recupera um catálogo personalizado pelo ID numérico."""
    ensure_custom_catalogs_schema()
    with db() as conn:
        pg = _is_pg(conn)
        ph = "%s" if pg else "?"
        cur = conn.execute(f"SELECT * FROM maj_custom_catalogs WHERE id = {ph} LIMIT 1", (catalog_id,))
        row = cur.fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["overrides"] = json.loads(d.get("custom_item_overrides_json") or "{}")
        except Exception:
            d["overrides"] = {}
        return d


def save_or_update_custom_catalog(data: Dict[str, Any], catalog_id: Optional[int] = None) -> Dict[str, Any]:
    """Cria ou atualiza um catálogo personalizado no banco."""
    ensure_custom_catalogs_schema()
    slug = sanitize_slug(data.get("slug") or data.get("title") or "catalogo")
    title = (data.get("title") or "Catálogo Personalizado").strip()
    client_name = (data.get("client_name") or "").strip()
    source_matrix = (data.get("source_matrix") or "outlet").strip().lower()
    if source_matrix not in ("outlet", "atacado"):
        source_matrix = "outlet"
    pricing_mode = (data.get("pricing_mode") or "fixed_matrix").strip().lower()
    percentage_markup = float(data.get("percentage_markup") or 0.0)
    sync_stock = bool(data.get("sync_stock", True))
    is_white_label = bool(data.get("is_white_label", True))
    logo_url = (data.get("logo_url") or "").strip()
    whatsapp_number = re.sub(r"\D", "", data.get("whatsapp_number") or "")
    if whatsapp_number and not whatsapp_number.startswith("55") and len(whatsapp_number) <= 11:
        whatsapp_number = f"55{whatsapp_number}"
    whatsapp_message_template = (data.get("whatsapp_message_template") or "").strip()
    overrides_json = data.get("custom_item_overrides_json") or "{}"
    if isinstance(overrides_json, dict):
        overrides_json = json.dumps(overrides_json, ensure_ascii=False)
    is_active = bool(data.get("is_active", True))
    expires_at = data.get("expires_at") or None
    created_by = data.get("created_by")

    with db() as conn:
        pg = _is_pg(conn)
        ph = "%s" if pg else "?"

        # Validação de unicidade de slug
        check_sql = f"SELECT id FROM maj_custom_catalogs WHERE slug = {ph}" + (f" AND id != {catalog_id}" if catalog_id else "")
        exists = conn.execute(check_sql, (slug,)).fetchone()
        if exists:
            # Anexa sufixo incremental se já existir
            slug = f"{slug}-{datetime.now().strftime('%M%S')}"

        if catalog_id:
            update_sql = f"""
            UPDATE maj_custom_catalogs SET
                slug = {ph}, title = {ph}, client_name = {ph}, source_matrix = {ph},
                pricing_mode = {ph}, percentage_markup = {ph}, sync_stock = {ph},
                is_white_label = {ph}, logo_url = {ph}, whatsapp_number = {ph},
                whatsapp_message_template = {ph}, custom_item_overrides_json = {ph},
                is_active = {ph}, expires_at = {ph}, updated_at = CURRENT_TIMESTAMP
            WHERE id = {ph}
            """
            conn.execute(update_sql, (
                slug, title, client_name, source_matrix, pricing_mode, percentage_markup,
                sync_stock, is_white_label, logo_url, whatsapp_number, whatsapp_message_template,
                overrides_json, is_active, expires_at, catalog_id
            ))
            saved_id = catalog_id
        else:
            insert_sql = f"""
            INSERT INTO maj_custom_catalogs (
                slug, title, client_name, source_matrix, pricing_mode, percentage_markup,
                sync_stock, is_white_label, logo_url, whatsapp_number, whatsapp_message_template,
                custom_item_overrides_json, is_active, expires_at, created_by
            ) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
            """
            if pg:
                cur = conn.execute(insert_sql + " RETURNING id", (
                    slug, title, client_name, source_matrix, pricing_mode, percentage_markup,
                    sync_stock, is_white_label, logo_url, whatsapp_number, whatsapp_message_template,
                    overrides_json, is_active, expires_at, created_by
                ))
                saved_id = cur.fetchone()["id"]
            else:
                conn.execute(insert_sql, (
                    slug, title, client_name, source_matrix, pricing_mode, percentage_markup,
                    sync_stock, is_white_label, logo_url, whatsapp_number, whatsapp_message_template,
                    overrides_json, is_active, expires_at, created_by
                ))
                saved_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        conn.commit()

    return get_custom_catalog_by_id(saved_id) or {}


def toggle_custom_catalog_status(catalog_id: int) -> bool:
    """Alterna o status ativo/pausado de um catálogo."""
    ensure_custom_catalogs_schema()
    with db() as conn:
        pg = _is_pg(conn)
        ph = "%s" if pg else "?"
        cur = conn.execute(f"SELECT is_active FROM maj_custom_catalogs WHERE id = {ph}", (catalog_id,))
        row = cur.fetchone()
        if not row:
            return False
        curr_active = bool(row["is_active"] if isinstance(row, dict) else row[0])
        new_active = not curr_active
        conn.execute(f"UPDATE maj_custom_catalogs SET is_active = {ph}, updated_at = CURRENT_TIMESTAMP WHERE id = {ph}", (new_active, catalog_id))
        conn.commit()
        return True


def delete_custom_catalog(catalog_id: int) -> bool:
    """Remove permanentemente um catálogo personalizado."""
    ensure_custom_catalogs_schema()
    with db() as conn:
        pg = _is_pg(conn)
        ph = "%s" if pg else "?"
        conn.execute(f"DELETE FROM maj_custom_catalogs WHERE id = {ph}", (catalog_id,))
        conn.commit()
        return True


def increment_catalog_views(catalog_id: int):
    """Incrementa telemetria de visualizações do catálogo."""
    try:
        with db() as conn:
            pg = _is_pg(conn)
            ph = "%s" if pg else "?"
            conn.execute(f"UPDATE maj_custom_catalogs SET views_count = views_count + 1 WHERE id = {ph}", (catalog_id,))
            conn.commit()
    except Exception as e:
        logger.debug("View tracking err: %s", e)


def increment_catalog_whatsapp_clicks(catalog_id: int):
    """Incrementa telemetria de cliques no WhatsApp CTA."""
    try:
        with db() as conn:
            pg = _is_pg(conn)
            ph = "%s" if pg else "?"
            conn.execute(f"UPDATE maj_custom_catalogs SET whatsapp_clicks_count = whatsapp_clicks_count + 1 WHERE id = {ph}", (catalog_id,))
            conn.commit()
    except Exception as e:
        logger.debug("WhatsApp click tracking err: %s", e)


def get_matrix_raw_items(matrix: str) -> List[Dict[str, Any]]:
    """Retorna os itens originais da matriz solicitada (Outlet ou Atacado)."""
    if matrix.lower() == "atacado":
        return get_all_atacado_items(status="active")
    return get_all_outlet_items(status="active")


def resolve_custom_catalog_products(catalog: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Processa e resolve os produtos da matriz de origem aplicando as regras de precificação,
    estoque, overrides específicos e links de WhatsApp CTA inteligentes.
    """
    matrix = catalog.get("source_matrix") or "outlet"
    pricing_mode = catalog.get("pricing_mode") or "fixed_matrix"
    markup_pct = float(catalog.get("percentage_markup") or 0.0)
    overrides = catalog.get("overrides") or {}
    whatsapp_num = catalog.get("whatsapp_number") or ""
    catalog_title = catalog.get("title") or "Catálogo"
    custom_msg_tpl = catalog.get("whatsapp_message_template") or ""

    raw_items = get_matrix_raw_items(matrix)
    processed = []

    for item in raw_items:
        item_id_str = str(item.get("id"))
        override = overrides.get(item_id_str, {})
        # Se o produto foi desativado explicitamente para este cliente, pula
        if override.get("disabled"):
            continue

        base_price = float(item.get("price_outlet") or item.get("price_original") or 0.0)
        show_price = True
        final_price = base_price

        # 1. Sem preço
        if pricing_mode == "no_price":
            show_price = False
            final_price = 0.0
        # 2. Margem percentual
        elif pricing_mode == "percentage_markup":
            if markup_pct != 0.0:
                final_price = round(base_price * (1.0 + (markup_pct / 100.0)), 2)
        # 3. Preço fixo personalizado por produto (override prioritário)
        if override.get("custom_price") is not None and pricing_mode in ("custom_prices", "percentage_markup", "fixed_matrix"):
            try:
                final_price = float(override["custom_price"])
                show_price = True
            except Exception:
                pass

        # Parcelamento estimado se houver preço
        inst_12 = round((final_price * 1.15) / 12.0, 2) if (show_price and final_price > 0) else 0.0
        inst_18 = round((final_price * 1.22) / 18.0, 2) if (show_price and final_price > 0) else 0.0

        # Estoque
        stock_qty = item.get("stock_qty", 0)
        if not catalog.get("sync_stock", True):
            # Se não sincronizar estoque, usa valor manual configurado no override ou mantém fixo
            stock_qty = override.get("stock_qty", stock_qty)

        # Montagem da Mensagem do WhatsApp CTA
        product_name = item.get("name", "Veículo Elétrico")
        if custom_msg_tpl:
            msg = custom_msg_tpl.replace("{produto}", product_name).replace("{preco}", f"R$ {final_price:,.2f}" if show_price else "").replace("{loja}", catalog_title)
        else:
            if show_price and final_price > 0:
                msg = (
                    f"Olá! Vi o modelo *{product_name}* (R$ {final_price:,.2f}) no catálogo *{catalog_title}* "
                    f"e gostaria de consultar a disponibilidade e condições de pagamento! ⚡"
                )
            else:
                msg = (
                    f"Olá! Vi o modelo *{product_name}* no catálogo *{catalog_title}* "
                    f"e gostaria de consultar valores e prazos de entrega! ⚡"
                )

        encoded_msg = urllib.parse.quote(msg)
        wa_url = f"https://wa.me/{whatsapp_num}?text={encoded_msg}" if whatsapp_num else "#"

        p_item = dict(item)
        p_item.update({
            "computed_price": final_price,
            "show_price": show_price,
            "computed_installment_12": inst_12,
            "computed_installment_18": inst_18,
            "stock_qty": stock_qty,
            "whatsapp_cta_url": wa_url,
            "whatsapp_message": msg,
        })
        processed.append(p_item)

    return processed
