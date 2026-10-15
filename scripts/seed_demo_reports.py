#!/usr/bin/env python3
"""
scripts/seed_demo_reports.py
Cria 4 ciclos semanais consecutivos e 4 relatórios semanais completos para Marisa,
permitindo avaliar a evolução histórica e organização de múltiplos relatórios no M-One.
"""
import json
from datetime import datetime
from database import db
from services.employee_reports_service import ensure_reports_schema, _is_pg


def seed_demo_reports():
    ensure_reports_schema()
    print("Criando 4 ciclos semanais e 4 relatórios fictícios para Marisa...")

    cycles_data = [
        {
            "cycle_code": "2026-W39",
            "title": "Ciclo Semanal 39/2026",
            "start_date": "2026-09-21",
            "deadline": datetime(2026, 9, 25, 18, 0, 0),
            "submitted_at": datetime(2026, 9, 25, 16, 40, 15),
            "status": "submitted_on_time",
            "answers": {
                "faturamento_nfs": "Emissão de 11 NFs no atacado para revendas parceiras do interior do ES e RJ. Faturamento de 6 motos no varejo da loja Consolação. Total faturado da semana: R$ 142.800,00.",
                "entradas_pendentes": "Dois boletos de atacado com atraso de 48h (Revenda MotoSul). Caixa físico fechado diariamente com Jhon com diferença de R$ 12,00 por falta de troco, já saneada e lançada.",
                "contas_vencimentos": "Encaminhadas 6 contas operacionais (energia Galpão MAJ, internet, fornecedor de embalagens e frete fracionado) totalizando R$ 8.450,00 aprovadas por Geysa e Jam.",
                "docs_faltantes": "Pendente envio do comprovante fiscal da transportadora TransSat referente à entrega em Cachoeiro.",
                "recibos_pendentes": "Três canhotos de entrega em rota com o motorista Carlos aguardando retorno físico na segunda-feira.",
                "piloto_mercado_pago": "Semana inicial de parametrização da conta PJ e testes com maquininha Point Pro na loja física.",
                "prioridades_proxima_semana": "Focar na conciliação dos fechamentos diários com o extrato bancário no Bling e zerar pendências de canhotos de entrega."
            }
        },
        {
            "cycle_code": "2026-W40",
            "title": "Ciclo Semanal 40/2026",
            "start_date": "2026-09-28",
            "deadline": datetime(2026, 10, 2, 18, 0, 0),
            "submitted_at": datetime(2026, 10, 2, 17, 15, 30),
            "status": "submitted_on_time",
            "answers": {
                "faturamento_nfs": "Fechamento de mês com 22 NFs emitidas. Destaque para pedido corporativo de 10 unidades X15 Pro para cliente corporativo. Total faturado da semana: R$ 268.400,00.",
                "entradas_pendentes": "Entrada de R$ 95.000,00 via PIX confirmada. Conciliação de caixa diário 100% batendo com contagem física de numerário com Jhon nos 5 dias úteis.",
                "contas_vencimentos": "Repassados aluguéis dos dois galpões (M-One e MAJ Antiga) e guia do Simples Nacional para autorização da Diretoria Geral (Jam).",
                "docs_faltantes": "Todos os comprovantes de despesas da semana recebidos com nota fiscal e arquivados por centro de custo.",
                "recibos_pendentes": "Todos os canhotos das entregas locais devolvidos e arquivados por ordem cronológica.",
                "piloto_mercado_pago": "Apurada primeira semana completa de vendas no cartão: R$ 38.200,00 processados, taxa média líquida apurada em 3.4%.",
                "prioridades_proxima_semana": "Início do fechamento mensal com a contabilidade externa e auditoria das ordens de serviço pendentes com Ricardo."
            }
        },
        {
            "cycle_code": "2026-W41",
            "title": "Ciclo Semanal 41/2026",
            "start_date": "2026-10-05",
            "deadline": datetime(2026, 10, 9, 18, 0, 0),
            "submitted_at": datetime(2026, 10, 9, 17, 45, 10),
            "status": "submitted_on_time",
            "answers": {
                "faturamento_nfs": "14 NFs de atacado e 9 de varejo showroom. Operação triangular de remessa para conserto faturada conforme orientação fiscal. Total semanal: R$ 189.600,00.",
                "entradas_pendentes": "Cobrança ativa realizada junto com Geysa para 3 clientes em atraso: 2 quitaram via PIX imediato. Inadimplência operacional reduzida em 75%.",
                "contas_vencimentos": "5 faturas de fornecedores locais de peças e manutenções prediais (R$ 4.200,00 autorizadas diretamente por Geysa dentro de sua alçada).",
                "docs_faltantes": "Aguardando NF de simples remessa de mercadoria em demonstração enviada para evento comercial.",
                "recibos_pendentes": "Apenas um recibo pendente do frete de entrega intermunicipal com retorno previsto para segunda-feira cedo.",
                "piloto_mercado_pago": "Conciliação fina de tarifas: taxa líquida consolidada em 3.25%, estorno de 1 operação cancelada pelo cliente processado sem prejuízo.",
                "prioridades_proxima_semana": "Preparar briefing executivo para a reunião de gestão e validar conferência física de contêiner com Jhon."
            }
        },
        {
            "cycle_code": "2026-W42",
            "title": "Ciclo Semanal 42/2026",
            "start_date": "2026-10-12",
            "deadline": datetime(2026, 10, 16, 18, 0, 0),
            "submitted_at": datetime(2026, 10, 14, 17, 52, 42),
            "status": "submitted_on_time",
            "answers": {
                "faturamento_nfs": "Faturamento recorde de 15 motos no atacado e 8 no varejo. NFs 1042 a 1065 emitidas no Bling com chave de acesso validada.",
                "entradas_pendentes": "Conferência de caixa diário batendo 100% com numerário físico conferido com Jhon em ambos os galpões.",
                "contas_vencimentos": "Repassadas 4 contas para a Geysa com vencimento na terça-feira (energia, internet e suprimentos de escritório).",
                "docs_faltantes": "Aguardando canhoto da transportadora Braspress relativo ao envio de Vitória para Linhares.",
                "recibos_pendentes": "Dois recibos em trânsito com o motorista Carlos.",
                "piloto_mercado_pago": "Taxas do Mercado Pago conferidas: 3.2% líquido apurado sem divergências no extrato consolidado.",
                "prioridades_proxima_semana": "Prioridade para conciliação das devoluções e preparação do fechamento de quinzena."
            }
        }
    ]

    with db() as conn:
        pg = _is_pg(conn)
        ph = "%s" if pg else "?"

        for c in cycles_data:
            # Garante ciclo
            cur = conn.execute(f"SELECT id FROM maj_report_cycles WHERE cycle_code = {ph} LIMIT 1", (c["cycle_code"],))
            row = cur.fetchone()
            if row:
                cycle_id = row["id"]
            else:
                cur_ins = conn.execute(
                    f"INSERT INTO maj_report_cycles (cycle_code, title, start_date, deadline, is_active) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}) RETURNING id" if pg else
                    f"INSERT INTO maj_report_cycles (cycle_code, title, start_date, deadline, is_active) VALUES ({ph}, {ph}, {ph}, {ph}, {ph})",
                    (c["cycle_code"], c["title"], c["start_date"], c["deadline"], c["cycle_code"] == "2026-W42")
                )
                if pg:
                    cycle_id = cur_ins.fetchone()["id"]
                else:
                    cycle_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            # Upsert relatório da Marisa
            answers_json = json.dumps(c["answers"], ensure_ascii=False)
            cur_rep = conn.execute(f"SELECT id FROM maj_employee_reports WHERE cycle_id = {ph} AND employee_key = 'marisa' LIMIT 1", (cycle_id,))
            rep_row = cur_rep.fetchone()
            if rep_row:
                conn.execute(
                    f"""UPDATE maj_employee_reports 
                        SET answers_json = {ph}, status = {ph}, submitted_at = {ph}, updated_at = {ph}
                        WHERE id = {ph}""",
                    (answers_json, c["status"], c["submitted_at"], c["submitted_at"], rep_row["id"])
                )
            else:
                conn.execute(
                    f"""INSERT INTO maj_employee_reports
                        (cycle_id, user_id, employee_key, employee_name, role_title, answers_json, status, submitted_at, updated_at)
                        VALUES ({ph}, 1, 'marisa', 'Marisa', 'Assistente Administrativo / Financeiro', {ph}, {ph}, {ph}, {ph})""",
                    (cycle_id, answers_json, c["status"], c["submitted_at"], c["submitted_at"])
                )

        conn.commit()
    print("✓ 4 ciclos e 4 relatórios da Marisa criados/atualizados com sucesso!")


if __name__ == "__main__":
    seed_demo_reports()
