"""
M-One Imports Hub Blueprint (routes/import_routes.py)
Gerenciamento de compras da China, lotes, contêineres, painel de 7 abas,
liberação de chassis e controle de etapas do processo.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from decimal import Decimal

from flask import Blueprint, flash, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from database import db
from routes.helpers import audit, current_user, login_required, roles_required, save_upload
from services.chassis_service import parse_chassis_file
from services.import_ai_service import DOC_TYPES_MAP
from services.import_audit_service import run_import_audit_checks
from services.import_calculator import calculate_import_financials, to_dec

logger = logging.getLogger(__name__)

import_bp = Blueprint("imports", __name__)

STEPS_ORDER = [
    ("compra", "1. Compra"),
    ("pagamentos_producao", "2. Pagamentos e Produção"),
    ("embarque", "3. Embarque"),
    ("desembaraco", "4. Desembaraço"),
    ("entrega", "5. Entrega"),
    ("prestacao_contas", "6. Prestação de Contas"),
    ("fechado", "7. Fechamento"),
]


@import_bp.route("/imports", methods=["GET"])
@login_required
@roles_required("admin", "support")
def imports():
    """Listagem geral de importações com cartões estatísticos e status das etapas."""
    me = current_user() or {}
    with db() as conn:
        rows = conn.execute(
            """
            SELECT i.*,
                   COUNT(DISTINCT su.id) as chassis_count,
                   COUNT(DISTINCT idoc.id) as documents_count,
                   COUNT(DISTINCT itm.id) as items_count
            FROM imports i
            LEFT JOIN stock_units su ON su.import_id = i.id
            LEFT JOIN import_documents idoc ON idoc.import_id = i.id
            LEFT JOIN import_items itm ON itm.import_id = i.id
            GROUP BY i.id
            ORDER BY i.id DESC
            """
        ).fetchall()

        import_list = []
        tot_usd = Decimal("0.00")
        tot_chassis = 0

        for r in rows:
            item = dict(r)
            # Calcular indicadores financeiros rápidos
            fin = calculate_import_financials(item["id"], conn)
            item["financials"] = fin
            tot_usd += to_dec(item.get("pi_amount_usd") or item.get("ci_amount_usd"))
            tot_chassis += int(item.get("chassis_count") or 0)
            import_list.append(item)

        products = conn.execute("SELECT id, name FROM products ORDER BY name").fetchall()

    return render_template(
        "imports.html",
        me=me,
        imports=import_list,
        products=products,
        steps_order=STEPS_ORDER,
        total_usd=float(tot_usd),
        total_chassis=tot_chassis,
    )


@import_bp.route("/imports/create", methods=["POST"])
@login_required
@roles_required("admin", "support")
def create_import():
    """Cria novo lote/processo de importação."""
    ref = request.form.get("reference", "").strip() or f"IMP-{date.today().year}-{date.today().strftime('%m%d')}"
    importer = request.form.get("importer_company", "MAJ Mobilidade").strip()
    supplier = request.form.get("supplier_name", "").strip()
    contact = request.form.get("supplier_contact", "").strip()
    currency = request.form.get("currency", "USD").strip()
    incoterm = request.form.get("incoterm", "FOB").strip()
    forwarder = request.form.get("freight_forwarder", "").strip()
    broker = request.form.get("customs_broker", "").strip()
    pi_usd = request.form.get("pi_amount_usd", "0")
    ci_usd = request.form.get("ci_amount_usd", "0")
    bl_no = request.form.get("bl_no", "").strip()
    invoice_no = request.form.get("invoice_no", "").strip()
    freight_ci = bool(request.form.get("freight_included_in_ci"))
    freight_pi = bool(request.form.get("freight_included_in_pi"))
    insurance_inc = bool(request.form.get("insurance_included"))
    arr_est = request.form.get("arrival_date_estimated") or None
    dep_est = request.form.get("departure_date_estimated") or None
    notes = request.form.get("notes", "").strip()
    me = current_user() or {}

    with db() as conn:
        new_row = conn.execute(
            """
            INSERT INTO imports (
                reference, importer_company, supplier_name, supplier_contact, currency, incoterm,
                freight_forwarder, customs_broker, pi_amount_usd, ci_amount_usd, bl_no, invoice_no,
                freight_included_in_ci, freight_included_in_pi, insurance_included,
                arrival_date, arrival_date_estimated, departure_date_estimated, notes, step, status, created_by
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'compra', 'draft', %s
            ) RETURNING id
            """,
            (
                ref,
                importer,
                supplier,
                contact,
                currency,
                incoterm,
                forwarder,
                broker,
                pi_usd,
                ci_usd,
                bl_no,
                invoice_no,
                freight_ci,
                freight_pi,
                insurance_inc,
                arr_est,
                arr_est,
                dep_est,
                notes,
                me.get("id"),
            ),
        ).fetchone()
        new_id = new_row["id"]

        # Salva documentos anexados durante a criação e vincula chassis
        from services.import_ai_service import persist_creation_documents
        persist_creation_documents(new_id, request, conn, me.get("id"))

        # Registra lançamentos de Outros Lançamentos (suporta 1 ou múltiplos lances)
        raw_debits_json = request.form.get("initial_debits_json", "").strip()
        debit_items = []
        if raw_debits_json:
            try:
                parsed = json.loads(raw_debits_json)
                if isinstance(parsed, list):
                    debit_items = parsed
            except Exception:
                pass

        if not debit_items:
            d_u = request.form.get("initial_debit_amount_usd", "0").strip() or "0"
            d_b = request.form.get("initial_debit_amount_brl", "0").strip() or "0"
            try:
                if float(d_u) > 0 or float(d_b) > 0:
                    debit_items.append({
                        "description": request.form.get("initial_debit_description", "").strip() or "Outros Lançamentos",
                        "amount_usd": float(d_u),
                        "amount_brl": float(d_b),
                        "exchange_rate": request.form.get("initial_debit_exchange_rate") or None,
                    })
            except Exception:
                pass

        for deb in debit_items:
            try:
                d_usd, d_brl = float(deb.get("amount_usd") or 0), float(deb.get("amount_brl") or 0)
                if d_usd > 0 or d_brl > 0:
                    dr = deb.get("exchange_rate") or (str(round(d_brl / d_usd, 4)) if d_usd > 0 and d_brl > 0 else None)
                    conn.execute(
                        """
                        INSERT INTO import_payments_china (
                            import_id, payment_category, description, amount_usd, amount_brl,
                            exchange_rate, bank_fees_brl, paid_at, is_verified
                        ) VALUES (%s, 'other_debit', %s, %s, %s, %s, 0.0, CURRENT_DATE, TRUE)
                        """,
                        (new_id, str(deb.get("description") or "Outros Lançamentos").strip(), d_usd, d_brl, dr),
                    )
            except Exception as deb_err:
                logger.warning("Falha ao registrar débito inicial: %s", deb_err)

        calculate_import_financials(new_id, conn)
        run_import_audit_checks(new_id, conn)
        audit("import.created", f"import_id={new_id}, ref={ref}")

    flash(f"Importação {ref} cadastrada com sucesso!", "success")
    return redirect(url_for("imports.import_detail", iid=new_id))


@import_bp.route("/imports/create-demo", methods=["POST"])
@login_required
@roles_required("admin", "support")
def create_demo():
    """Cria um processo de importação completo com dados de exemplo para navegação rápida."""
    from services.demo_import import create_demo_import_data
    me = current_user() or {}
    new_id = create_demo_import_data(me)
    flash("Importação de demonstração criada com sucesso! Todas as 7 abas foram configuradas.", "success")
    return redirect(url_for("imports.import_detail", iid=new_id))



@import_bp.route("/imports/<int:iid>", methods=["GET"])
@login_required
@roles_required("admin", "support")
def import_detail(iid: int):
    """Painel completo da importação dividido em abas."""
    me = current_user() or {}
    active_tab = request.args.get("tab", "summary")

    with db() as conn:
        imp = conn.execute("SELECT * FROM imports WHERE id = %s", (iid,)).fetchone()
        if not imp:
            flash("Importação não encontrada.", "error")
            return redirect(url_for("imports.imports"))

        financials = calculate_import_financials(iid, conn)
        checks = run_import_audit_checks(iid, conn)

        # Buscar dados de todas as abas
        items = conn.execute(
            """
            SELECT itm.*, p.name as product_name_catalog, p.sku
            FROM import_items itm
            LEFT JOIN products p ON p.id = itm.product_id
            WHERE itm.import_id = %s
            ORDER BY itm.id ASC
            """,
            (iid,),
        ).fetchall()

        chassis_units = conn.execute(
            """
            SELECT su.*, p.name as product_name
            FROM stock_units su
            LEFT JOIN products p ON p.id = su.product_id
            WHERE su.import_id = %s
            ORDER BY su.id ASC
            """,
            (iid,),
        ).fetchall()

        china_payments = conn.execute(
            """
            SELECT p.*, d.title as doc_title, d.file_url as doc_url
            FROM import_payments_china p
            LEFT JOIN import_documents d ON d.id = p.document_id
            WHERE p.import_id = %s
            ORDER BY p.paid_at ASC, p.id ASC
            """,
            (iid,),
        ).fetchall()

        brazil_expenses = conn.execute(
            """
            SELECT e.*, d.title as doc_title, d.file_url as doc_url
            FROM import_brazil_expenses e
            LEFT JOIN import_documents d ON d.id = e.document_id
            WHERE e.import_id = %s
            ORDER BY e.category ASC, e.due_date ASC
            """,
            (iid,),
        ).fetchall()

        numerario_entries = conn.execute(
            """
            SELECT n.*, d.title as doc_title, d.file_url as doc_url
            FROM import_numerario n
            LEFT JOIN import_documents d ON d.id = n.document_id
            WHERE n.import_id = %s
            ORDER BY n.entry_date ASC, n.id ASC
            """,
            (iid,),
        ).fetchall()

        documents = conn.execute(
            """
            SELECT d.*, u.name as uploader_name
            FROM import_documents d
            LEFT JOIN users u ON u.id = d.uploaded_by
            WHERE d.import_id = %s
            ORDER BY d.doc_type ASC, d.id DESC
            """,
            (iid,),
        ).fetchall()

        products = conn.execute("SELECT id, name FROM products ORDER BY name").fetchall()
        unique_chassis_count = len({u["chassis"].strip().upper() for u in chassis_units if u.get("chassis") and u["chassis"].strip()})
        imp_dict = dict(imp)
        imp_dict["chassis_count"] = unique_chassis_count

    return render_template(
        "import_detail.html",
        me=me,
        i=imp_dict,
        unique_chassis_count=unique_chassis_count,
        financials=financials,
        checks=checks,
        items=items,
        chassis_units=chassis_units,
        china_payments=china_payments,
        brazil_expenses=brazil_expenses,
        numerario_entries=numerario_entries,
        documents=documents,
        products=products,
        doc_types=DOC_TYPES_MAP,
        steps_order=STEPS_ORDER,
        active_tab=active_tab,
        today=date.today().isoformat(),
    )


@import_bp.route("/imports/<int:iid>/edit", methods=["POST"])
@login_required
@roles_required("admin", "support")
def edit_import(iid: int):
    """Atualiza dados cadastrais da importação."""
    ref = request.form.get("reference", "").strip()
    importer = request.form.get("importer_company", "").strip()
    supplier = request.form.get("supplier_name", "").strip()
    currency = request.form.get("currency", "USD").strip()
    incoterm = request.form.get("incoterm", "FOB").strip()
    forwarder = request.form.get("freight_forwarder", "").strip()
    broker = request.form.get("customs_broker", "").strip()
    pi_usd = request.form.get("pi_amount_usd", "0")
    ci_usd = request.form.get("ci_amount_usd", "0")
    bl_no = request.form.get("bl_no", "").strip()
    invoice_no = request.form.get("invoice_no", "").strip()
    notes = request.form.get("notes", "").strip()

    with db() as conn:
        conn.execute(
            """
            UPDATE imports
            SET reference=%s, importer_company=%s, supplier_name=%s, currency=%s, incoterm=%s,
                freight_forwarder=%s, customs_broker=%s, pi_amount_usd=%s, ci_amount_usd=%s,
                bl_no=%s, invoice_no=%s, notes=%s
            WHERE id=%s
            """,
            (ref, importer, supplier, currency, incoterm, forwarder, broker, pi_usd, ci_usd, bl_no, invoice_no, notes, iid),
        )
        calculate_import_financials(iid, conn)
        run_import_audit_checks(iid, conn)
        audit("import.updated", f"import_id={iid}")

    flash("Dados da importação atualizados com sucesso!", "success")
    return redirect(url_for("imports.import_detail", iid=iid))


@import_bp.route("/imports/<int:iid>/step", methods=["POST"])
@login_required
@roles_required("admin", "support")
def update_step(iid: int):
    """Avança ou altera a etapa do processo de importação."""
    new_step = request.form.get("step")
    valid_steps = [s[0] for s in STEPS_ORDER]
    if new_step not in valid_steps:
        flash("Etapa inválida.", "error")
        return redirect(url_for("imports.import_detail", iid=iid))

    with db() as conn:
        conn.execute("UPDATE imports SET step=%s WHERE id=%s", (new_step, iid))
        audit("import.step_changed", f"import_id={iid}, step={new_step}")

    flash(f"Etapa atualizada para: {dict(STEPS_ORDER).get(new_step, new_step)}", "success")
    return redirect(url_for("imports.import_detail", iid=iid))


@import_bp.route("/imports/<int:iid>/close", methods=["POST"])
@login_required
@roles_required("admin", "support")
def close_import(iid: int):
    """Realiza o fechamento formal e conciliação final do lote."""
    me = current_user() or {}
    with db() as conn:
        calculate_import_financials(iid, conn)
        conn.execute(
            """
            UPDATE imports 
            SET status='closed', step='fechado', cost_factor_status='final', 
                closed_at=CURRENT_TIMESTAMP, closed_by=%s
            WHERE id=%s
            """,
            (me.get("id"), iid),
        )
        audit("import.closed", f"import_id={iid}, user={me.get('username')}")

    flash("Importação fechada com sucesso! Fator de custo consolidado como FINAL.", "success")
    return redirect(url_for("imports.import_detail", iid=iid))


@import_bp.route("/imports/<int:iid>/reopen", methods=["POST"])
@login_required
@roles_required("admin", "support")
def reopen_import(iid: int):
    """Reabre importação mediante justificativa obrigatória registrada em log."""
    justification = (request.form.get("reopen_reason") or request.form.get("justification", "")).strip()
    if not justification or len(justification) < 5:
        flash("É obrigatório informar uma justificativa clara para reabrir a importação.", "error")
        return redirect(url_for("imports.import_detail", iid=iid))

    me = current_user() or {}
    with db() as conn:
        conn.execute(
            """
            UPDATE imports 
            SET status='in_progress', step='prestacao_contas', cost_factor_status='provisional'
            WHERE id=%s
            """,
            (iid,),
        )
        audit("import.reopened", f"import_id={iid}, user={me.get('username')}, just={justification}")

    flash("Importação reaberta com sucesso. Registrado no log de auditoria.", "success")
    return redirect(url_for("imports.import_detail", iid=iid))


@import_bp.route("/imports/<int:iid>/release", methods=["POST"], endpoint="release_import")
@import_bp.route("/imports/<int:iid>/release-stock", methods=["POST"], endpoint="release_import_stock")
@login_required
@roles_required("admin", "support")
def release_import_stock(iid: int):
    """Libera os chassis da importação para venda imediata no estoque."""
    with db() as conn:
        conn.execute("UPDATE imports SET status='released' WHERE id=%s", (iid,))
        conn.execute("UPDATE stock_units SET status='available' WHERE import_id=%s AND status='unreleased'", (iid,))
        audit("import.stock_released", f"import_id={iid}")

    flash("Chassis liberados com sucesso para venda no estoque!", "success")
    return redirect(url_for("imports.import_detail", iid=iid, tab="products"))


@import_bp.route("/imports/<int:iid>/chassis", methods=["POST"], endpoint="upload_chassis")
@import_bp.route("/imports/<int:iid>/chassis-upload", methods=["POST"], endpoint="upload_chassis_sheet")
@login_required
@roles_required("admin", "support")
def upload_chassis_sheet(iid: int):

    """Upload e vinculação de planilha de chassis (.csv, .xlsx)."""
    f = request.files.get("chassis_file")
    if not f or not f.filename:
        flash("Nenhum arquivo de chassis selecionado.", "error")
        return redirect(url_for("imports.import_detail", iid=iid, tab="products"))

    try:
        rows = parse_chassis_file(f)
    except Exception as e:
        flash(f"Erro na leitura da planilha: {str(e)}", "error")
        return redirect(url_for("imports.import_detail", iid=iid, tab="products"))

    with db() as conn:
        products_map = {p["name"].strip().lower(): p["id"] for p in conn.execute("SELECT id, name FROM products").fetchall()}
        inserted = 0
        for r in rows:
            p_id = products_map.get(r["model"].strip().lower())
            if not p_id:
                # Criar produto no catálogo se não existir
                res = conn.execute("INSERT INTO products (name, category) VALUES (%s, 'Motos Elétricas') RETURNING id", (r["model"].strip(),)).fetchone()
                p_id = res["id"]
                products_map[r["model"].strip().lower()] = p_id

            # Inserir unidade no estoque vinculado à importação
            conn.execute(
                """
                INSERT INTO stock_units (product_id, chassis, motor_no, color, import_id, status)
                VALUES (%s, %s, %s, %s, %s, 'unreleased')
                ON CONFLICT (chassis) DO UPDATE 
                SET motor_no = EXCLUDED.motor_no, 
                    color = EXCLUDED.color, 
                    import_id = EXCLUDED.import_id
                """,
                (p_id, r["chassis"].strip(), r["motor"].strip(), r["color"].strip(), iid),
            )
            inserted += 1

        calculate_import_financials(iid, conn)
        run_import_audit_checks(iid, conn)
        audit("import.chassis_imported", f"import_id={iid}, count={inserted}")

    flash(f"{inserted} chassis processados e vinculados a esta importação!", "success")
    return redirect(url_for("imports.import_detail", iid=iid, tab="products"))

