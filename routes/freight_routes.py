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
                t.notes,
                t.origin_city,
                t.cubing_factor,
                t.tec_percent,
                t.tas_fixed,
                t.pos_fixed,
                t.created_at,
                c.id AS carrier_id,
                c.name AS carrier_name,
                c.trade_name,
                c.cnpj,
                c.phone,
                c.sales_rep_name,
                c.active AS carrier_active,
                (SELECT COUNT(*) FROM freight_rates r WHERE r.table_id = t.id) AS rates_count
            FROM freight_tables t
            JOIN carriers c ON c.id = t.carrier_id
            ORDER BY c.name ASC, t.created_at DESC
        """
        cur_t = conn.execute(sql_t)
        tables = cur_t.fetchall()

        cur_c = conn.execute(
            """SELECT DISTINCT c.id, c.name, c.active 
               FROM carriers c 
               JOIN freight_tables t ON t.carrier_id = c.id 
               WHERE c.active = 1 AND t.active = 1 
               ORDER BY c.name ASC"""
        )
        carriers = cur_c.fetchall()

        cur_fq = conn.execute(
            """SELECT fq.*, u.name created_by_name 
               FROM freight_quotes fq 
               LEFT JOIN users u ON u.id = fq.created_by 
               ORDER BY fq.id DESC LIMIT 50"""
        )
        archived_quotes = cur_fq.fetchall()

    active_tab = request.args.get("tab", "simulator").strip().lower()
    if active_tab not in ["simulator", "carriers", "quotes"]:
        active_tab = "simulator"

    return render_template(
        "freight.html",
        me=me,
        role_labels=ROLE_LABELS,
        products=products,
        tables=tables,
        carriers=carriers,
        archived_quotes=archived_quotes,
        active_tab=active_tab,
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
        return redirect(url_for("freight", tab="quotes"))
    with db() as conn:
        conn.execute("UPDATE freight_quotes SET status = %s WHERE id = %s", (status, qid))
        conn.commit()
    audit("freight.status_updated", f"quote_id={qid}; status={status}")
    flash(f"Status da cotação de frete atualizado para '{status.upper()}'.", "success")
    return redirect(url_for("freight", tab="quotes"))


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

        parsed_result = freight_service.parse_freight_table_with_gemini(file_path, carrier_name)
        rates = parsed_result.get("rates", []) if isinstance(parsed_result, dict) else (parsed_result if isinstance(parsed_result, list) else [])
        issues = parsed_result.get("issues", []) if isinstance(parsed_result, dict) else []
        is_valid = parsed_result.get("is_valid", len(rates) > 0) if isinstance(parsed_result, dict) else (len(rates) > 0)

        if not is_valid or len(rates) == 0:
            issues_msg = " • ".join(issues) if issues else "Não foram identificadas faixas tarifárias ou preços válidos no arquivo enviado."
            flash(
                f"⚠️ Pendências na planilha da transportadora '{carrier_name}': {issues_msg}. "
                f"A tabela NÃO foi ativada para evitar simulações incorretas. Solicite estes dados à transportadora.",
                "warning"
            )
            return redirect(url_for("freight"))

        with db() as conn:
            freight_service.ensure_freight_tables(conn)

            cur_c = conn.execute("SELECT id FROM carriers WHERE LOWER(name) = LOWER(%s)", (carrier_name,))
            row_c = cur_c.fetchone()
            if row_c:
                carrier_id = row_c["id"]
            else:
                cur_ins = conn.execute("INSERT INTO carriers (name) VALUES (%s) RETURNING id", (carrier_name,))
                carrier_id = cur_ins.fetchone()["id"]

            report_text = " • ".join(issues) if issues else "Tabela importada e auditada com 100% de conformidade operacional."
            cur_t = conn.execute(
                "INSERT INTO freight_tables (carrier_id, name, file_url, notes) VALUES (%s, %s, %s, %s) RETURNING id",
                (carrier_id, table_name, str(file_path.name), report_text)
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

        obs_msg = f" (Observações: {' • '.join(issues)})" if issues else ""
        flash(f"✅ Tabela '{table_name}' da transportadora '{carrier_name}' importada com sucesso! ({inserted_count} regras cadastradas){obs_msg}", "success")
    except Exception as e:
        flash(f"Erro ao importar tabela de frete: {str(e)}", "danger")

    return redirect(url_for("freight", tab="carriers"))


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
    return redirect(url_for("freight", tab="carriers"))


@freight_bp.route("/freight/tables/<int:table_id>/details")
@login_required
def freight_table_details(table_id: int):
    """Retorna detalhes cadastrais, contratuais, relatório IA e faixas tarifárias da tabela."""
    with db() as conn:
        cur_t = conn.execute(
            """
            SELECT 
                t.id AS table_id, t.name AS table_name, t.file_url, t.notes, t.created_at,
                t.origin_city, t.cubing_factor, t.tec_percent, t.tas_fixed,
                t.pos_fixed, t.min_gris_value, t.expiration_days,
                c.id AS carrier_id, c.name AS carrier_name, c.trade_name, c.cnpj,
                c.address, c.city AS carrier_city, c.uf AS carrier_uf,
                c.phone, c.website, c.sales_rep_name, c.payment_terms
            FROM freight_tables t
            JOIN carriers c ON c.id = t.carrier_id
            WHERE t.id = %s
            """,
            (table_id,)
        )
        t_row = cur_t.fetchone()
        if not t_row:
            return jsonify({"success": False, "message": "Tabela não encontrada."}), 404

        table_data = dict(t_row)
        table_data["created_at_fmt"] = t_row["created_at"].strftime("%d/%m/%Y %H:%M") if t_row.get("created_at") else ""

        cur_r = conn.execute(
            """
            SELECT 
                id, uf, city, cep_start, cep_end, min_weight, max_weight,
                fixed_price, weight_price_per_kg, ad_valorem_percent,
                gris_percent, delivery_days, toll_per_100kg, dispatch_fixed, notes
            FROM freight_rates
            WHERE table_id = %s
            ORDER BY uf ASC, city ASC, min_weight ASC
            LIMIT 200
            """,
            (table_id,)
        )
        rates = [dict(r) for r in cur_r.fetchall()]

        return jsonify({
            "success": True,
            "table": table_data,
            "rates": rates,
            "total_rates": len(rates)
        })


@freight_bp.route("/freight/carriers/<int:carrier_id>/update", methods=["POST"])
@login_required
@roles_required("admin", "support")
def freight_carrier_update(carrier_id: int):
    """Atualiza dados cadastrais, comerciais e operacionais da transportadora pelo modal."""
    try:
        data = request.get_json() if request.is_json else request.form
        with db() as conn:
            conn.execute(
                """
                UPDATE carriers SET
                    trade_name = %s, cnpj = %s, address = %s, city = %s, uf = %s,
                    phone = %s, website = %s, sales_rep_name = %s, payment_terms = %s
                WHERE id = %s
                """,
                (
                    data.get("trade_name") or "", data.get("cnpj") or "",
                    data.get("address") or "", data.get("city") or "",
                    data.get("uf") or "", data.get("phone") or "",
                    data.get("website") or "", data.get("sales_rep_name") or "",
                    data.get("payment_terms") or "", carrier_id
                )
            )
            table_id = data.get("table_id")
            if table_id:
                conn.execute(
                    """
                    UPDATE freight_tables SET
                        origin_city = %s, cubing_factor = %s, tec_percent = %s,
                        tas_fixed = %s, pos_fixed = %s, min_gris_value = %s,
                        expiration_days = %s
                    WHERE id = %s AND carrier_id = %s
                    """,
                    (
                        data.get("origin_city") or "Cariacica",
                        float(data.get("cubing_factor") or 300.0),
                        float(data.get("tec_percent") or 0.0),
                        float(data.get("tas_fixed") or 0.0),
                        float(data.get("pos_fixed") or 0.0),
                        float(data.get("min_gris_value") or 0.0),
                        int(data.get("expiration_days") or 90),
                        int(table_id), carrier_id
                    )
                )
            if hasattr(conn, "commit"):
                conn.commit()
            audit("carrier.updated", f"carrier_id={carrier_id}; trade_name={data.get('trade_name')}")
            return jsonify({"success": True, "message": "Dados da transportadora atualizados com sucesso!"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@freight_bp.route("/freight/quotes/select-carrier", methods=["POST"])
@login_required
def freight_quote_select_carrier():
    """Atualiza a transportadora e valor selecionados pelo vendedor na cotação arquivada."""
    try:
        data = request.get_json() or {}
        quote_number = data.get("quote_number")
        quote_id = data.get("quote_id")
        carrier_name = data.get("selected_carrier") or data.get("carrier_name")
        price = data.get("selected_price")
        if (not quote_number and not quote_id) or not carrier_name:
            return jsonify({"success": False, "message": "Dados insuficientes"}), 400

        with db() as conn:
            if quote_number:
                conn.execute(
                    "UPDATE freight_quotes SET selected_carrier = %s, selected_price = %s WHERE quote_number = %s",
                    (carrier_name, float(price or 0), str(quote_number))
                )
            elif quote_id:
                conn.execute(
                    "UPDATE freight_quotes SET selected_carrier = %s, selected_price = %s WHERE id = %s",
                    (carrier_name, float(price or 0), int(quote_id))
                )
            audit("FREIGHT_QUOTE_CARRIER_SELECT", f"Cotação {quote_number or quote_id} marcada com {carrier_name} (R$ {price})")

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

