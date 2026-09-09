"""
M-One Sales & Invoicing Blueprint (routes/sales_routes.py)
Rotas de Registro de Vendas, Verificação de Chassis por IA e Exportação de Vendas.
"""

from __future__ import annotations

import base64
import csv
import io
import json
from datetime import date

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for

from database import db
from gemini_service import extract_and_match_chassis
from routes.helpers import (
    ALLOWED_EXTENSIONS,
    UPLOAD_DIR,
    audit,
    login_required,
    money,
    roles_required,
    save_base64_upload,
    save_upload,
)

sales_bp = Blueprint("sales", __name__)


def ensure_sales_columns():
    try:
        with db() as conn:
            for col in [
                "danfe_file", "delivery_term_files", "ai_chassis_verified",
                "ai_extracted_chassis", "vehicle_model", "chassis_photo_file",
                "warranty_term_file", "signed_stub_file"
            ]:
                try:
                    conn.execute(f"ALTER TABLE sales ADD COLUMN {col} TEXT")
                except Exception:
                    pass
            conn.commit()
    except Exception:
        pass


@sales_bp.route("/sales", methods=["GET", "POST"])
@login_required
@roles_required("admin", "finance", "sales", "support")
def sales():
    ensure_sales_columns()

    if request.method == "POST":
        order_number = request.form.get("order_number", "").strip()
        invoice_number = request.form.get("invoice_number", "").strip()
        channel = request.form.get("channel", "varejo")
        customer = request.form.get("customer", "").strip()
        sold_at = request.form.get("sold_at") or date.today().isoformat()
        notes = request.form.get("notes", "").strip()
        raw_chassis = request.form.get("chassis", "")
        chassis_list = [x.strip().upper() for x in raw_chassis.replace(";", ",").split(",") if x.strip()]

        if not order_number or not invoice_number:
            flash("Pedido e Nota Fiscal são campos obrigatórios.", "danger")
            return redirect(url_for("sales"))

        if not chassis_list and notes:
            with db() as conn:
                db_chassis = [r["chassis"].upper() for r in conn.execute("SELECT chassis FROM stock_units").fetchall() if r["chassis"]]
            found = [c for c in db_chassis if c in notes.upper()]
            if found:
                chassis_list = list(set(found))

        if not chassis_list:
            flash("Bloqueado: A Nota Fiscal (NF) deve conter obrigatoriamente um número de chassi válido na descrição e no cadastro da venda. Nenhuma nota é faturada sem chassi.", "danger")
            return redirect(url_for("sales"))

        if len(chassis_list) != len(set(chassis_list)):
            flash("Bloqueado: Há chassi duplicado na própria Nota Fiscal.", "danger")
            return redirect(url_for("sales"))

        chassis_str = ", ".join(chassis_list)
        if not notes:
            notes = f"Chassi(s) da NF: {chassis_str}"
        elif not any(c in notes.upper() for c in chassis_list):
            notes = f"{notes} | Chassi(s) da NF: {chassis_str}"

        with db() as conn:
            if conn.execute("SELECT 1 FROM sales WHERE invoice_number=?", (invoice_number,)).fetchone():
                flash("Essa Nota Fiscal já foi cadastrada no sistema.", "danger")
                return redirect(url_for("sales"))

            units = []
            errors = []
            for ch in chassis_list:
                u = conn.execute(
                    """SELECT st.*,p.name product_name,p.retail_price,p.wholesale_price,i.status import_status
                       FROM stock_units st JOIN products p ON p.id=st.product_id LEFT JOIN imports i ON i.id=st.import_id
                       WHERE UPPER(st.chassis)=?""", (ch,)
                ).fetchone()
                if not u:
                    errors.append(f"{ch}: chassi não encontrado no estoque. Importe o lote antes de faturar a Nota Fiscal.")
                elif u["status"] != "available":
                    if u["status"] == "unreleased":
                        errors.append(f"{ch}: este chassi pertence a uma importação em conferência (não liberada pela Diretoria).")
                    else:
                        errors.append(f"{ch}: este chassi já consta como vendido ou indisponível (status: {u['status']}).")
                elif u["import_status"] != "released":
                    errors.append(f"{ch}: importação deste chassi ainda não foi liberada pela Diretoria.")
                else:
                    units.append(u)

            if errors:
                for e in errors:
                    flash(f"Bloqueio de Nota Fiscal — {e}", "danger")
                return redirect(url_for("sales"))

            danfe_file_obj = request.files.get("danfe_file")
            danfe_captured = request.form.get("danfe_captured_image")
            danfe_filename = None
            if danfe_captured:
                danfe_filename = save_base64_upload(danfe_captured, "danfe")
            elif danfe_file_obj and danfe_file_obj.filename:
                try:
                    danfe_filename = save_upload(danfe_file_obj, "danfe")
                except ValueError as e:
                    flash(f"Arquivo de comprovante da DANFE inválido: {str(e)}", "danger")
                    return redirect(url_for("sales"))

            warranty_term_file_obj = request.files.get("warranty_term_file")
            warranty_term_captured = request.form.get("warranty_term_captured_image")
            warranty_term_filename = None
            if warranty_term_captured:
                warranty_term_filename = save_base64_upload(warranty_term_captured, "garantia")
            elif warranty_term_file_obj and warranty_term_file_obj.filename:
                try:
                    warranty_term_filename = save_upload(warranty_term_file_obj, "garantia")
                except ValueError as e:
                    flash(f"Termo de Garantia inválido: {str(e)}", "danger")
                    return redirect(url_for("sales"))

            signed_stub_file_obj = request.files.get("signed_stub_file")
            signed_stub_captured = request.form.get("signed_stub_captured_image")
            signed_stub_filename = None
            if signed_stub_captured:
                signed_stub_filename = save_base64_upload(signed_stub_captured, "canhoto")
            elif signed_stub_file_obj and signed_stub_file_obj.filename:
                try:
                    signed_stub_filename = save_upload(signed_stub_file_obj, "canhoto")
                except ValueError as e:
                    flash(f"Canhoto da NF inválido: {str(e)}", "danger")
                    return redirect(url_for("sales"))

            if channel == "varejo" and not warranty_term_filename:
                flash("Para vendas no Varejo, é obrigatório anexar o Termo de Ciência da Garantia.", "danger")
                return redirect(url_for("sales"))
            elif channel == "atacado" and not signed_stub_filename:
                flash("Para vendas no Atacado, é obrigatório anexar o Canhoto da NF Assinado.", "danger")
                return redirect(url_for("sales"))

            term_filenames = []
            term_file_objs = request.files.getlist("delivery_term_files")
            for tf in term_file_objs:
                if tf and tf.filename:
                    try:
                        saved_name = save_upload(tf, "termo")
                        if saved_name:
                            term_filenames.append(saved_name)
                    except ValueError:
                        pass

            term_captured_raw = request.form.get("delivery_term_captured_images", "")
            if term_captured_raw:
                try:
                    cap_list = json.loads(term_captured_raw) if term_captured_raw.startswith("[") else [term_captured_raw]
                    for cap_b64 in cap_list:
                        if cap_b64 and "," in cap_b64:
                            saved_name = save_base64_upload(cap_b64, "termo")
                            if saved_name:
                                term_filenames.append(saved_name)
                except Exception:
                    pass

            chassis_photo_file_obj = request.files.get("chassis_photo_file")
            chassis_photo_captured = request.form.get("chassis_photo_captured_image")
            chassis_photo_filename = None
            if chassis_photo_captured:
                chassis_photo_filename = save_base64_upload(chassis_photo_captured, "chassis_veiculo")
            elif chassis_photo_file_obj and chassis_photo_file_obj.filename:
                try:
                    chassis_photo_filename = save_upload(chassis_photo_file_obj, "chassis_veiculo")
                except ValueError as e:
                    flash(f"Foto de chassi do veículo/caixa inválida: {str(e)}", "danger")
                    return redirect(url_for("sales"))

            if not danfe_filename and not term_filenames and not chassis_photo_filename:
                flash("É obrigatório anexar a Foto do Chassi do Veículo/Caixa, a DANFE ou o Termo de Entrega.", "danger")
                return redirect(url_for("sales"))

            term_files_json = json.dumps(term_filenames) if term_filenames else None
            vehicle_model = request.form.get("vehicle_model", "").strip()

            ai_verified = request.form.get("ai_chassis_verified") == "1"
            ai_extracted = request.form.get("ai_extracted_chassis", "").strip()

            if not ai_verified:
                target_filename = chassis_photo_filename or danfe_filename or warranty_term_filename or signed_stub_filename or (term_filenames[0] if term_filenames else None)
                if target_filename:
                    doc_path = UPLOAD_DIR / target_filename
                    if doc_path.exists():
                        ext = target_filename.rsplit(".", 1)[-1].lower()
                        mime = "application/pdf" if ext == "pdf" else f"image/{ext if ext != 'jpg' else 'jpeg'}"
                        v_res = extract_and_match_chassis(doc_path.read_bytes(), mime, chassis_list, expected_model=vehicle_model)
                        if not v_res.get("is_valid"):
                            flash(f"Bloqueio da IA: {v_res.get('summary', 'O chassi do documento não confere com o digitado.')}", "danger")
                            return redirect(url_for("sales"))
                        ai_verified = True
                        ai_extracted = ", ".join(v_res.get("extracted_chassis", []))

            default_total = sum(float(u["wholesale_price"] if channel == "atacado" else u["retail_price"]) for u in units)
            total_value = float(request.form.get("total_value") or default_total)
            cur = conn.execute(
                """INSERT INTO sales(order_number,invoice_number,channel,customer,sold_at,total_value,notes,danfe_file,delivery_term_files,vehicle_model,chassis_photo_file,warranty_term_file,signed_stub_file,ai_chassis_verified,ai_extracted_chassis,created_by)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (order_number, invoice_number, channel, customer, sold_at, total_value, notes, danfe_filename, term_files_json, vehicle_model, chassis_photo_filename, warranty_term_filename, signed_stub_filename, ai_verified, ai_extracted, session["user_id"]),
            )
            sale_id = cur.lastrowid
            per_unit = total_value / len(units) if units else 0
            for u in units:
                conn.execute("INSERT INTO sale_units(sale_id,stock_unit_id,product_id,unit_value) VALUES(?,?,?,?)", (sale_id, u["id"], u["product_id"], per_unit))
                conn.execute("UPDATE stock_units SET status='sold',sold_at=?,sale_id=? WHERE id=?", (sold_at, sale_id, u["id"]))

            methods = request.form.getlist("payment_method[]")
            accounts = request.form.getlist("payment_account[]")
            amounts = request.form.getlist("payment_amount[]")
            receipt_files = request.files.getlist("payment_receipt[]")

            sale_photo_receipt = save_base64_upload(request.form.get("captured_image_data"), "venda")
            if not sale_photo_receipt:
                try:
                    sale_photo_receipt = save_upload(request.files.get("sale_receipt_file"), "venda")
                except ValueError:
                    sale_photo_receipt = None

            receipt_total = 0.0
            for idx, amount_str in enumerate(amounts):
                if not amount_str:
                    continue
                amount = float(amount_str)
                receipt_total += amount
                receipt = None
                if idx < len(receipt_files) and receipt_files[idx] and receipt_files[idx].filename:
                    try:
                        receipt = save_upload(receipt_files[idx], "recebimento")
                    except ValueError:
                        receipt = None
                if not receipt and idx == 0 and sale_photo_receipt:
                    receipt = sale_photo_receipt

                method = methods[idx] if idx < len(methods) else "À vista"
                account = accounts[idx] if idx < len(accounts) else ""
                conn.execute("INSERT INTO sale_receipts(sale_id,method,account,amount,received_at,receipt_file) VALUES(?,?,?,?,?,?)", (sale_id, method, account, amount, sold_at, receipt))

            if not amounts and sale_photo_receipt:
                conn.execute("INSERT INTO sale_receipts(sale_id,method,account,amount,received_at,receipt_file) VALUES(?,?,?,?,?,?)", (sale_id, "À vista", "Geral", total_value, sold_at, sale_photo_receipt))

            conn.commit()
        audit("sale.created", f"sale_id={sale_id}; invoice={invoice_number}; chassis={','.join(chassis_list)}")
        if abs(receipt_total - total_value) > 0.01:
            flash(f"Venda registrada, mas os recebimentos somam {money(receipt_total)} e a venda {money(total_value)}. Confira.", "warning")
        else:
            flash("Venda registrada e chassis baixados sem duplicidade.", "success")
        return redirect(url_for("sales"))

    with db() as conn:
        sales_rows = conn.execute(
            """
            SELECT s.*, u.name created_by_name, COUNT(DISTINCT su.id) units, COALESCE(SUM(sr.amount),0) received
            FROM sales s 
            LEFT JOIN users u ON u.id=s.created_by
            LEFT JOIN sale_units su ON su.sale_id=s.id
            LEFT JOIN sale_receipts sr ON sr.sale_id=s.id
            GROUP BY s.id, u.name ORDER BY s.sold_at DESC, s.id DESC LIMIT 200
            """
        ).fetchall()
        sales_data = []
        if sales_rows:
            sale_ids = [s["id"] for s in sales_rows]
            ids_str = ",".join(str(x) for x in sale_ids)
            chassis_rows = conn.execute(
                f"""SELECT su.sale_id, st.chassis, p.name product_name FROM sale_units su
                   JOIN stock_units st ON st.id=su.stock_unit_id
                   JOIN products p ON p.id=su.product_id
                   WHERE su.sale_id IN ({ids_str})"""
            ).fetchall()
            receipts_rows = conn.execute(
                f"""SELECT * FROM sale_receipts WHERE sale_id IN ({ids_str})"""
            ).fetchall()

            chassis_by_sale = {}
            for c in chassis_rows:
                chassis_by_sale.setdefault(c["sale_id"], []).append(dict(c))

            receipts_by_sale = {}
            for r in receipts_rows:
                receipts_by_sale.setdefault(r["sale_id"], []).append(dict(r))

            for s in sales_rows:
                sd = dict(s)
                c_list = chassis_by_sale.get(sd["id"], [])
                r_list = receipts_by_sale.get(sd["id"], [])
                sd["chassis_details"] = c_list
                sd["chassis_str"] = ", ".join(c["chassis"] for c in c_list)
                sd["receipts"] = r_list
                t_files = []
                if sd.get("delivery_term_files"):
                    try:
                        raw_t = sd["delivery_term_files"]
                        t_files = json.loads(raw_t) if isinstance(raw_t, str) and raw_t.startswith("[") else ([raw_t] if raw_t else [])
                    except Exception:
                        t_files = []
                sd["term_files_list"] = t_files
                sales_data.append(sd)
    return render_template("sales.html", sales=sales_data)


@sales_bp.route("/sales/export")
@login_required
def export_sales():
    audit("sales.exported", "")
    with db() as conn:
        rows = conn.execute(
            """SELECT s.sold_at, s.order_number, s.invoice_number, s.channel, s.customer, s.total_value,
                      (SELECT GROUP_CONCAT(st.chassis, ', ') FROM sale_units su JOIN stock_units st ON st.id=su.stock_unit_id WHERE su.sale_id=s.id) chassis_list
               FROM sales s ORDER BY s.sold_at DESC"""
        ).fetchall()
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";")
    writer.writerow(["DATA", "PEDIDO_BLING", "NOTA_FISCAL", "CANAL", "CLIENTE", "VALOR_TOTAL", "CHASSIS"])
    for r in rows:
        writer.writerow([r["sold_at"], r["order_number"], r["invoice_number"], r["channel"], r["customer"] or "", f"{r['total_value']:.2f}".replace(".", ","), r["chassis_list"] or ""])
    return out.getvalue(), 200, {"Content-Type": "text/csv; charset=utf-8-sig", "Content-Disposition": "attachment; filename=vendas_m_one.csv"}


@sales_bp.route("/api/sales/verify-chassis", methods=["POST"])
@login_required
def verify_sales_chassis():
    chassis_raw = request.form.get("chassis", "")
    chassis_list = [x.strip() for x in chassis_raw.replace(";", ",").split(",") if x.strip()]
    if not chassis_list:
        return jsonify({
            "success": False,
            "is_valid": False,
            "message": "Nenhum número de chassi informado. Digite o(s) chassi(s) no formulário antes de conferir o comprovante."
        }), 400

    captured_data = request.form.get("captured_image")
    captured_list_raw = request.form.get("captured_images")

    items_to_check = []

    if captured_data and "," in captured_data:
        try:
            header, data_str = captured_data.split(",", 1)
            b = base64.b64decode(data_str)
            m = "image/png" if "png" in header else ("image/webp" if "webp" in header else "image/jpeg")
            items_to_check.append((b, m))
        except Exception:
            pass

    if captured_list_raw:
        try:
            cap_arr = json.loads(captured_list_raw) if captured_list_raw.startswith("[") else [captured_list_raw]
            for c_str in cap_arr:
                if c_str and "," in c_str:
                    header, data_str = c_str.split(",", 1)
                    b = base64.b64decode(data_str)
                    m = "image/png" if "png" in header else ("image/webp" if "webp" in header else "image/jpeg")
                    items_to_check.append((b, m))
        except Exception:
            pass

    chassis_photo_file = request.files.get("chassis_photo_file")
    chassis_photo_captured = request.form.get("chassis_photo_captured_image")

    if chassis_photo_captured and "," in chassis_photo_captured:
        try:
            header, data_str = chassis_photo_captured.split(",", 1)
            b = base64.b64decode(data_str)
            m = "image/png" if "png" in header else ("image/webp" if "webp" in header else "image/jpeg")
            items_to_check.append((b, m))
        except Exception:
            pass

    if chassis_photo_file and chassis_photo_file.filename:
        ext = chassis_photo_file.filename.rsplit(".", 1)[-1].lower()
        if ext in ALLOWED_EXTENSIONS:
            b = chassis_photo_file.read()
            m = "application/pdf" if ext == "pdf" else ("image/png" if ext == "png" else "image/jpeg")
            items_to_check.append((b, m))

    for key_file, key_cap in [("warranty_term_file", "warranty_term_captured_image"), ("signed_stub_file", "signed_stub_captured_image")]:
        cap_val = request.form.get(key_cap)
        if cap_val and "," in cap_val:
            try:
                header, data_str = cap_val.split(",", 1)
                b = base64.b64decode(data_str)
                m = "image/png" if "png" in header else ("image/webp" if "webp" in header else "image/jpeg")
                items_to_check.append((b, m))
            except Exception:
                pass
        f_val = request.files.get(key_file)
        if f_val and f_val.filename:
            ext = f_val.filename.rsplit(".", 1)[-1].lower()
            if ext in ALLOWED_EXTENSIONS:
                b = f_val.read()
                m = "application/pdf" if ext == "pdf" else ("image/png" if ext == "png" else "image/jpeg")
                items_to_check.append((b, m))

    if not items_to_check:
        return jsonify({"success": False, "is_valid": False, "message": "Nenhum arquivo ou foto foi anexado para a conferência."}), 400

    vehicle_model = request.form.get("vehicle_model", "").strip()
    res = extract_and_match_chassis(items_to_check, chassis_list, expected_model=vehicle_model)
    return jsonify(res)
