"""
M-One Freight & Carrier Blueprint (routes/freight_routes.py)
Rotas de Cálculo de Frete, Cotações, Arquivamento, Envio WhatsApp e Gestão de Tabelas.
"""

from __future__ import annotations

import json
import random
import time
from datetime import datetime

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

import freight_service
from database import db
from routes.helpers import ROLE_LABELS, UPLOAD_DIR, audit, current_user, login_required, roles_required

freight_bp = Blueprint("freight", __name__)


@freight_bp.route("/freight")
@login_required
def freight():
    """Interface principal do Módulo de Fretes."""
    me = current_user()
    with db() as conn:
        freight_service.ensure_freight_tables(conn)

        cur_p = conn.execute("SELECT id, name, wholesale_price, retail_price FROM products ORDER BY name ASC")
        products_raw = cur_p.fetchall()
        products = []
        for p in products_raw:
            w_price = float(p.get("wholesale_price") or 0)
            p_name_upper = (p.get("name") or "").upper()
            if "MINI" in p_name_upper:
                w_kg, l_cm, wi_cm, h_cm = 55.0, 150.0, 60.0, 95.0
            elif "V20" in p_name_upper or "RIDE" in p_name_upper or "M9" in p_name_upper or "M50" in p_name_upper or "V80" in p_name_upper:
                w_kg, l_cm, wi_cm, h_cm = 65.0, 165.0, 65.0, 100.0
            elif "CLASSIC" in p_name_upper or "FLOW" in p_name_upper or "DB" in p_name_upper or "M2" in p_name_upper or "RZ" in p_name_upper:
                w_kg, l_cm, wi_cm, h_cm = 80.0, 175.0, 70.0, 105.0
            elif "MAX" in p_name_upper or "NOVA" in p_name_upper or "VITTORIA" in p_name_upper or "SPORT" in p_name_upper:
                w_kg, l_cm, wi_cm, h_cm = 88.0, 180.0, 70.0, 110.0
            elif "GP" in p_name_upper:
                w_kg, l_cm, wi_cm, h_cm = 95.0, 185.0, 75.0, 115.0
            else:
                w_kg, l_cm, wi_cm, h_cm = 85.0, 180.0, 70.0, 110.0

            products.append({
                "id": p.get("id"),
                "name": p.get("name"),
                "wholesale_price": w_price,
                "one_third_wholesale": round(w_price / 3.0, 2),
                "retail_price": float(p.get("retail_price") or 0),
                "weight_kg": w_kg,
                "length_cm": l_cm,
                "width_cm": wi_cm,
                "height_cm": h_cm
            })

        sql_t = """
            SELECT 
                t.id AS table_id,
                t.name AS table_name,
                t.file_url,
                t.created_at,
                c.id AS carrier_id,
                c.name AS carrier_name,
                c.active AS carrier_active,
                (SELECT COUNT(*) FROM freight_rates r WHERE r.table_id = t.id) AS rates_count
            FROM freight_tables t
            JOIN carriers c ON c.id = t.carrier_id
            ORDER BY c.name ASC, t.created_at DESC
        """
        cur_t = conn.execute(sql_t)
        tables = cur_t.fetchall()

        cur_c = conn.execute("SELECT id, name, active FROM carriers ORDER BY name ASC")
        carriers = cur_c.fetchall()

        cur_fq = conn.execute(
            """SELECT fq.*, u.name created_by_name 
               FROM freight_quotes fq 
               LEFT JOIN users u ON u.id = fq.created_by 
               ORDER BY fq.id DESC LIMIT 50"""
        )
        archived_quotes = cur_fq.fetchall()

    return render_template(
        "freight.html",
        me=me,
        role_labels=ROLE_LABELS,
        products=products,
        tables=tables,
        carriers=carriers,
        archived_quotes=archived_quotes,
        default_cep=freight_service.DEFAULT_MAJ_CEP
    )


@freight_bp.route("/freight/calculate", methods=["POST"])
@login_required
def freight_calculate():
    """API para cálculo de frete por CEP, peso e múltiplos produtos com arquivamento de cotação."""
    try:
        data = request.get_json() if request.is_json else request.form
        cep_dest = data.get("cep_dest", "").strip()
        customer_name = data.get("customer_name", "").strip()
        cpf_cnpj = data.get("cpf_cnpj", "").strip()
        company_name = data.get("company_name", "").strip()
        contact_phone = data.get("contact_phone", "").strip()
        contact_person = data.get("contact_person", "").strip()
        full_address = data.get("full_address", "").strip()

        weight_kg = float(data.get("weight_kg", 0) or 0)
        product_id = data.get("product_id")
        if product_id:
            try:
                product_id = int(product_id)
            except Exception:
                product_id = None
        declared_value = float(data.get("declared_value", 0) or 0)
        cep_orig = data.get("cep_orig", "").strip() or freight_service.DEFAULT_MAJ_CEP
        items = data.get("items", [])

        with db() as conn:
            freight_service.ensure_freight_tables(conn)
            res = freight_service.calculate_freight(
                db_conn=conn,
                cep_dest=cep_dest,
                items=items,
                weight_kg=weight_kg,
                declared_value=declared_value,
                product_id=product_id,
                cep_orig=cep_orig
            )

            if res.get("success"):
                quote_number = f"COT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{random.randint(100, 999)}"
                items_json = json.dumps(items, ensure_ascii=False)
                carrier_results_json = json.dumps(res.get("options", []), ensure_ascii=False)
                best_opt = res.get("best_option") or {}

                conn.execute(
                    """INSERT INTO freight_quotes(
                        quote_number, customer_name, cpf_cnpj, company_name, contact_phone,
                        contact_person, full_address, cep_dest, cep_orig, items_summary,
                        carrier_results_json, selected_carrier, selected_price, status, created_by
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'cotado', %s)""",
                    (
                        quote_number, customer_name, cpf_cnpj, company_name, contact_phone,
                        contact_person, full_address, cep_dest, cep_orig, items_json,
                        carrier_results_json,
                        best_opt.get("carrier_name", ""),
                        best_opt.get("final_cost", 0),
                        session.get("user_id")
                    )
                )
                conn.commit()
                res["quote_number"] = quote_number
                audit("freight.calculated", f"quote={quote_number}; customer={customer_name}; cep={cep_dest}")

            return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@freight_bp.route("/freight/quotes/<int:qid>/status", methods=["POST"])
@login_required
def freight_quote_status(qid):
    """Atualiza o status de envio de uma cotação de frete arquivada."""
    status = request.form.get("status", "").strip().lower()
    if status not in ["cotado", "aprovado", "enviado", "cancelado"]:
        flash("Status de frete inválido.", "warning")
        return redirect(url_for("freight"))
    with db() as conn:
        conn.execute("UPDATE freight_quotes SET status = %s WHERE id = %s", (status, qid))
        conn.commit()
    audit("freight.status_updated", f"quote_id={qid}; status={status}")
    flash(f"Status da cotação de frete atualizado para '{status.upper()}'.", "success")
    return redirect(url_for("freight"))


@freight_bp.route("/freight/whatsapp", methods=["POST"])
@login_required
def freight_whatsapp():
    """Gera o texto formatado para envio no WhatsApp."""
    try:
        data = request.get_json() if request.is_json else request.form
        customer_name = data.get("customer_name", "")
        cep_dest = data.get("cep_dest", "")
        product_name = data.get("product_name", "")
        options = data.get("options", [])
        msg = freight_service.generate_whatsapp_budget(
            customer_name=customer_name,
            cep_dest=cep_dest,
            product_name=product_name,
            options=options
        )
        audit("freight.whatsapp", f"customer={customer_name}; dest={cep_dest}")
        return jsonify({"success": True, "message": msg})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@freight_bp.route("/freight/tables/upload", methods=["POST"])
@login_required
@roles_required("admin", "support")
def freight_table_upload():
    """Upload e parsing por IA (Gemini) de novas tabelas de frete."""
    try:
        carrier_name = request.form.get("carrier_name", "").strip()
        table_name = request.form.get("table_name", "").strip()
        file = request.files.get("table_file")

        if not carrier_name or not table_name or not file or not file.filename:
            flash("⚠️ Preencha o nome da transportadora, nome da tabela e selecione o arquivo.", "warning")
            return redirect(url_for("freight"))

        filename = secure_filename(file.filename)
        file_path = UPLOAD_DIR / f"freight_{int(time.time())}_{filename}"
        file.save(file_path)

        rates = freight_service.parse_freight_table_with_gemini(file_path, carrier_name)

        with db() as conn:
            freight_service.ensure_freight_tables(conn)

            cur_c = conn.execute("SELECT id FROM carriers WHERE LOWER(name) = LOWER(%s)", (carrier_name,))
            row_c = cur_c.fetchone()
            if row_c:
                carrier_id = row_c["id"]
            else:
                cur_ins = conn.execute("INSERT INTO carriers (name) VALUES (%s) RETURNING id", (carrier_name,))
                carrier_id = cur_ins.fetchone()["id"]

            cur_t = conn.execute(
                "INSERT INTO freight_tables (carrier_id, name, file_url) VALUES (%s, %s, %s) RETURNING id",
                (carrier_id, table_name, str(file_path.name))
            )
            table_id = cur_t.fetchone()["id"]

            inserted_count = 0
            for r in rates:
                conn.execute(
                    """
                    INSERT INTO freight_rates (
                        table_id, uf, city, cep_start, cep_end, 
                        min_weight, max_weight, fixed_price, weight_price_per_kg, 
                        ad_valorem_percent, gris_percent, min_freight_price, delivery_days, notes
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        table_id,
                        r.get("uf"),
                        r.get("city"),
                        freight_service.clean_cep(r.get("cep_start")),
                        freight_service.clean_cep(r.get("cep_end")),
                        float(r.get("min_weight") or 0),
                        float(r.get("max_weight") or 999999),
                        float(r.get("fixed_price") or 0),
                        float(r.get("weight_price_per_kg") or 0),
                        float(r.get("ad_valorem_percent") or 0),
                        float(r.get("gris_percent") or 0),
                        float(r.get("min_freight_price") or 0),
                        int(r.get("delivery_days") or 1),
                        r.get("notes") or ""
                    )
                )
                inserted_count += 1

        flash(f"✅ Tabela '{table_name}' da transportadora '{carrier_name}' importada com sucesso! ({inserted_count} regras processadas pela IA)", "success")
    except Exception as e:
        flash(f"Erro ao importar tabela de frete: {str(e)}", "danger")

    return redirect(url_for("freight"))


@freight_bp.route("/freight/tables/delete/<int:table_id>", methods=["POST"])
@login_required
@roles_required("admin", "support")
def freight_table_delete(table_id: int):
    """Exclui uma tabela de frete cadastrada."""
    try:
        with db() as conn:
            conn.execute("DELETE FROM freight_tables WHERE id = %s", (table_id,))
        flash("✅ Tabela de frete excluída com sucesso.", "success")
    except Exception as e:
        flash(f"Erro ao excluir tabela: {str(e)}", "danger")
    return redirect(url_for("freight"))
