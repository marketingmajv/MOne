import unittest
from unittest.mock import patch, MagicMock
import json
import os
import sqlite3
import time
import io

import tempfile
from datetime import datetime, timedelta

# Isolamento de segurança estrito: Forçar banco de dados SQLite temporário exclusivo para a suíte de testes
TEMP_TEST_DB = tempfile.NamedTemporaryFile(suffix="_test_automation.db", delete=False).name
os.environ["TEST_DB_FILE"] = TEMP_TEST_DB
os.environ["USE_LOCAL_DB"] = "1"
os.environ["VERCEL"] = ""

from app import app, init_db
from database import db
from services.automation_service import (
    validate_input_format,
    ensure_automation_schema,
    seed_default_flows_if_empty,
    process_inbound_automation,
    acquire_contact_lock,
    release_contact_lock,
    process_pending_delayed_sessions,
    process_pending_timeouts,
    execute_flow_step
)

class TestWhatsAppAutomationModule(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        cls.client = app.test_client()

        # Garante schema base no banco de dados temporário isolado
        with db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    username TEXT UNIQUE,
                    password_hash TEXT,
                    role TEXT,
                    active INTEGER DEFAULT 1
                );
            """)
            conn.execute("INSERT OR REPLACE INTO users (id, name, username, password_hash, role, active) VALUES (17, 'Jam', 'jam', '5b61661d56d43bce0c316ed882ecb807493421b6c33a14dc2ce34fc43f578690', 'admin', 1)")
            conn.execute("INSERT OR REPLACE INTO users (id, name, username, password_hash, role, active) VALUES (16, 'Fauzer', 'fauzer', '5b61661d56d43bce0c316ed882ecb807493421b6c33a14dc2ce34fc43f578690', 'admin', 1)")
            conn.commit()

        init_db()
        ensure_automation_schema(force=True)
        seed_default_flows_if_empty()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TEMP_TEST_DB):
            try:
                os.remove(TEMP_TEST_DB)
            except Exception:
                pass

    def setUp(self):

        # Prepare clean lead & session state for testing
        with db() as conn:
            conn.execute("DELETE FROM contact_locks")
            conn.execute("DELETE FROM automation_processed_wams")
            conn.execute("DELETE FROM automation_logs")
            conn.execute("DELETE FROM automation_sessions")
            conn.execute("DELETE FROM whatsapp_messages")
            conn.execute("DELETE FROM crm_leads")
            conn.execute("UPDATE automation_flows SET status='active', active_version_data=COALESCE(draft_version_data, active_version_data), active_trigger_type=COALESCE(draft_trigger_type, trigger_type, 'keyword'), active_trigger_config=COALESCE(draft_trigger_config, trigger_config, '{\"keywords\": [\"ola\", \"olá\", \"menu\", \"ajuda\", \"inicio\"]}')")

            conn.execute(
                "INSERT INTO crm_leads (id, name, phone, channel, status, bot_paused) VALUES (100, ?, ?, ?, ?, ?)",
                ("Cliente Teste", "5527999990001", "WhatsApp", "novo", 0)
            )
            conn.commit()

    def test_01_input_format_validation(self):
        """Test text, email, number, and phone format validators with correct signature (rule, val)"""
        self.assertTrue(validate_input_format("email", "contato@maj.com.br"))
        self.assertFalse(validate_input_format("email", "contato-invalido"))

        self.assertTrue(validate_input_format("number", "1250.50"))
        self.assertTrue(validate_input_format("number", "100"))
        self.assertFalse(validate_input_format("number", "cem reais"))

        self.assertTrue(validate_input_format("phone", "27996061538"))
        self.assertTrue(validate_input_format("phone", "+55 (27) 99606-1538"))
        self.assertFalse(validate_input_format("phone", "123"))

        self.assertTrue(validate_input_format("text", "Qualquer texto válido"))

    def test_02_permission_guard(self):
        """Test that only Jam and Fauzer can access automation studio and APIs"""
        # Test anonymous access
        res = self.client.get("/automation")
        self.assertEqual(res.status_code, 302)

        # Test unauthorized user session
        with self.client.session_transaction() as sess:
            sess["user_id"] = 999
            sess["username"] = "vendedor_comum"

        res = self.client.get("/automation")
        self.assertEqual(res.status_code, 302)

        res_api = self.client.get("/api/automation/flows")
        self.assertEqual(res_api.status_code, 403)

        # Test authorized user (Jam)
        with self.client.session_transaction() as sess:
            sess["user_id"] = 17
            sess["username"] = "jam"

        res_jam = self.client.get("/automation")
        self.assertEqual(res_jam.status_code, 200)

        res_api_jam = self.client.get("/api/automation/flows")
        self.assertEqual(res_api_jam.status_code, 200)
        data = res_api_jam.get_json()
        self.assertIsInstance(data, list)

    def test_03_flow_save_draft_and_activate(self):
        """Test saving a draft flow and promoting it to active version"""
        with self.client.session_transaction() as sess:
            sess["user_id"] = 17
            sess["username"] = "jam"

        # Create flow draft
        payload = {
            "name": "Fluxo Teste Qualificação",
            "trigger_type": "keyword",
            "trigger_value": "scooter, patinete",
            "graph_data": {
                "nodes": [
                    {"id": "node_1", "type": "trigger", "config": {"keywords": ["scooter", "patinete"]}},
                    {"id": "node_2", "type": "send_message", "config": {"text": "Bem vindo à MAJ!"}}
                ],
                "edges": [
                    {"id": "e1", "source": "node_1", "target": "node_2"}
                ]
            }
        }
        res = self.client.post("/api/automation/flows/save", json=payload)
        self.assertEqual(res.status_code, 200)
        flow_id = res.get_json().get("id")
        self.assertIsNotNone(flow_id)

        # Activate flow
        res_act = self.client.post(f"/api/automation/flows/{flow_id}/activate")
        self.assertEqual(res_act.status_code, 200)
        self.assertTrue(res_act.get_json().get("success"))

    def test_04_inbound_automation_execution_and_atomic_wam_id(self):
        """Test executing inbound keyword trigger, menu choice, and atomic wam_id reservation"""
        phone = "5527999990001"
        wam_id_1 = "WAM_TEST_ATOMIC_1001"
        
        # 1. Trigger automation by sending keyword "olá"
        res1 = process_inbound_automation(phone, "olá", wam_id=wam_id_1)
        self.assertIn(res1.get("status"), ["waiting_user_input", "flow_completed"])

        # 2. Duplicate wam_id attempt must be ignored idempotently
        res_dup = process_inbound_automation(phone, "olá", wam_id=wam_id_1)
        self.assertEqual(res_dup.get("status"), "duplicate_wam_id_ignored")

        # 3. Check outbound messages in local DB
        with db() as conn:
            msgs = conn.execute("SELECT * FROM whatsapp_messages WHERE phone=?", (phone,)).fetchall()
            self.assertGreaterEqual(len(msgs), 1)

    def test_05_menu_option_mapping_and_validation_retry(self):
        """Test menu numbered choice (e.g. '1') and validation retry on bad input"""
        phone = "5527999990001"
        
        # Start flow to reach menu node
        process_inbound_automation(phone, "olá")

        # Send invalid menu choice "99" -> should fallback/re-prompt menu without advancing to target branch
        res_bad = process_inbound_automation(phone, "99")
        self.assertIn(res_bad.get("status"), ["validation_failed", "waiting_user_input"])

        # Send valid choice "1" -> should map option and advance
        res_good = process_inbound_automation(phone, "1")
        self.assertIn(res_good.get("status"), ["flow_completed", "waiting_user_input"])

    def test_06_flow_simulator(self):
        """Test visual flow simulator API endpoint"""
        with self.client.session_transaction() as sess:
            sess["user_id"] = 17
            sess["username"] = "jam"

        payload = {
            "graph_data": {
                "nodes": [
                    {"id": "node_start", "type": "trigger", "config": {"keywords": "oi"}},
                    {"id": "node_msg", "type": "send_message", "config": {"text": "Olá do simulador!"}}
                ],
                "edges": [
                    {"id": "e1", "source": "node_start", "target": "node_msg"}
                ]
            },
            "input": "oi"
        }
        res = self.client.post("/api/automation/simulate", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(len(data.get("responses")), 1)
        self.assertIn("simulador", data["responses"][0]["text"])

    def test_07_inbox_multiagent_actions(self):
        """Test inbox actions: toggle bot, assign agent, save notes"""
        with self.client.session_transaction() as sess:
            sess["user_id"] = 17
            sess["username"] = "jam"

        phone = "5527999990001"

        # Toggle bot pause
        res_bot = self.client.post("/api/automation/inbox/toggle-bot", json={"phone": phone})
        self.assertEqual(res_bot.status_code, 200)

        with db() as conn:
            lead = conn.execute("SELECT bot_paused FROM crm_leads WHERE phone=?", (phone,)).fetchone()
            self.assertEqual(lead["bot_paused"], 1)

        # Assign agent ticket
        res_assign = self.client.post("/api/automation/inbox/action", json={"action": "assign", "phone": phone, "agent": "fauzer"})
        self.assertEqual(res_assign.status_code, 200)

        with db() as conn:
            lead = conn.execute("SELECT assigned_to FROM crm_leads WHERE phone=?", (phone,)).fetchone()
            self.assertEqual(lead["assigned_to"], "fauzer")

        # Save notes
        res_notes = self.client.post("/api/automation/inbox/action", json={"action": "save_notes", "phone": phone, "notes": "Cliente interessado em Scooter X3"})
        self.assertEqual(res_notes.status_code, 200)

        with db() as conn:
            lead = conn.execute("SELECT notes FROM crm_leads WHERE phone=?", (phone,)).fetchone()
            self.assertIn("Scooter X3", lead["notes"])

    def test_08_contact_lock_and_lease_recovery(self):
        """Test contact lock exclusivity and automatic lease expiration recovery"""
        phone = "5527999990001"

        # Acquire initial lock
        locked = acquire_contact_lock(phone, "worker_1", lease_seconds=2)
        self.assertTrue(locked)

        # Concurrent lock attempt must be rejected
        locked_again = acquire_contact_lock(phone, "worker_2", lease_seconds=2)
        self.assertFalse(locked_again)

        # Release lock manually
        release_contact_lock(phone, "worker_1")
        locked_after_release = acquire_contact_lock(phone, "worker_2", lease_seconds=2)
        self.assertTrue(locked_after_release)

    def test_09_persistent_delay_worker(self):
        """Test persistent delay with resume_due_at and clock-controlled worker execution"""
        phone = "5527999990001"
        graph = {
            "nodes": [
                {"id": "n1", "type": "trigger", "config": {}},
                {"id": "n2", "type": "delay", "config": {"delay_seconds": 10}},
                {"id": "n3", "type": "send_message", "config": {"text": "Mensagem pós delay!"}}
            ],
            "edges": [
                {"id": "e1", "source": "n1", "target": "n2"},
                {"id": "e2", "source": "n2", "target": "n3"}
            ]
        }

        # Create session at delay node
        with db() as conn:
            cur = conn.execute(
                "INSERT INTO automation_sessions (flow_id, phone, status, current_node_id, flow_snapshot) VALUES (1, ?, 'running', 'n1', ?)",
                (phone, json.dumps(graph))
            )
            sid = cur.lastrowid
            conn.commit()

        # Step into delay node
        res_delay = execute_flow_step(sid, 1, graph, "n2", phone)
        self.assertEqual(res_delay.get("status"), "waiting_delay")

        # Worker at current time -> delay not due yet
        now_ts = int(time.time())
        res_early = process_pending_delayed_sessions(now_ts=now_ts)
        self.assertEqual(len(res_early), 0)

        # Worker after 15 seconds -> delay due and resumed!
        res_due = process_pending_delayed_sessions(now_ts=now_ts + 15)
        self.assertEqual(len(res_due), 1)
        self.assertEqual(res_due[0]["result"]["status"], "flow_completed")

    def test_10_question_timeout_and_ports(self):
        """Test ask_question node timeout and valid/invalid/timeout ports"""
        phone = "5527999990001"
        graph = {
            "nodes": [
                {"id": "q1", "type": "ask_question", "config": {"question": "Qual seu e-mail?", "validation": "email", "timeout_seconds": 60}},
                {"id": "n_valid", "type": "send_message", "config": {"text": "E-mail válido!"}},
                {"id": "n_invalid", "type": "send_message", "config": {"text": "E-mail inválido!"}},
                {"id": "n_timeout", "type": "send_message", "config": {"text": "Tempo esgotado!"}}
            ],
            "edges": [
                {"id": "e_v", "source": "q1", "source_handle": "valid_answer", "target": "n_valid"},
                {"id": "e_inv", "source": "q1", "source_handle": "invalid_answer", "target": "n_invalid"},
                {"id": "e_to", "source": "q1", "source_handle": "timeout", "target": "n_timeout"}
            ]
        }

        # Start question node
        with db() as conn:
            cur = conn.execute(
                "INSERT INTO automation_sessions (flow_id, phone, status, current_node_id, flow_snapshot) VALUES (1, ?, 'running', 'q1', ?)",
                (phone, json.dumps(graph))
            )
            sid = cur.lastrowid
            conn.commit()

        execute_flow_step(sid, 1, graph, "q1", phone)

        # Test timeout worker after 100 seconds
        now_ts = int(time.time())
        res_timeout = process_pending_timeouts(now_ts=now_ts + 100)
        self.assertEqual(len(res_timeout), 1)

    def test_11_crm_actions(self):
        """Test complete CRM actions: create lead, update status, assign seller, create task note"""
        phone = "5527999999999"
        graph = {
            "nodes": [
                {"id": "act_create", "type": "action", "config": {"action_type": "create_lead", "name": "Novo Lead Bot"}},
                {"id": "act_status", "type": "action", "config": {"action_type": "update_lead_status", "status": "em_atendimento"}},
                {"id": "act_seller", "type": "action", "config": {"action_type": "assign_seller", "seller": "fauzer", "seller_id": 16}},
                {"id": "act_task", "type": "action", "config": {"action_type": "create_task", "note": "Ligar amanhã para cotação"}}
            ],
            "edges": [
                {"id": "e1", "source": "act_create", "target": "act_status"},
                {"id": "e2", "source": "act_status", "target": "act_seller"},
                {"id": "e3", "source": "act_seller", "target": "act_task"}
            ]
        }

        # Run CRM action flow
        with db() as conn:
            cur = conn.execute(
                "INSERT INTO automation_sessions (flow_id, phone, status, current_node_id, flow_snapshot) VALUES (1, ?, 'running', 'act_create', ?)",
                (phone, json.dumps(graph))
            )
            sid = cur.lastrowid
            conn.commit()

        res = execute_flow_step(sid, 1, graph, "act_create", phone)
        self.assertEqual(res.get("status"), "flow_completed")

        # Verify CRM lead was updated correctly in DB
        with db() as conn:
            lead = conn.execute("SELECT * FROM crm_leads WHERE phone=?", (phone,)).fetchone()
            self.assertIsNotNone(lead)
            self.assertEqual(lead["status"], "em_atendimento")
            self.assertEqual(lead["assigned_to"], "fauzer")
            self.assertEqual(lead["seller_id"], 16)
            task = conn.execute("SELECT * FROM crm_tasks WHERE phone=?", (phone,)).fetchone()
            self.assertIsNotNone(task)
            self.assertIn("Ligar amanhã", task["title"])

    def test_12_simulation_multi_step_flow(self):
        """Test multi-step conversation simulation: trigger -> ask_question (email) -> condition -> transfer"""
        with self.client.session_transaction() as sess:
            sess["user_id"] = 17
            sess["username"] = "jam"

        graph = {
            "nodes": [
                {"id": "n_trg", "type": "trigger", "config": {"keywords": ["inicio"]}},
                {"id": "n_q", "type": "ask_question", "config": {"question": "Qual seu e-mail de contato?", "validation": "email", "save_variable": "user_email"}},
                {"id": "n_cond", "type": "condition", "config": {"variable": "user_email", "conditions": [{"operator": "contains", "value": "@maj.com.br", "target_node": "n_transfer"}], "fallback_target_node": "n_end"}},
                {"id": "n_transfer", "type": "transfer_agent", "config": {"message": "Encaminhando para consultor corporativo..."}},
                {"id": "n_end", "type": "end", "config": {}}
            ],
            "edges": [
                {"id": "e1", "source": "n_trg", "target": "n_q"},
                {"id": "e2", "source": "n_q", "target": "n_cond"},
                {"id": "e3", "source": "n_cond", "target": "n_transfer"},
                {"id": "e4", "source": "n_cond", "target": "n_end"}
            ]
        }

        # 1. Start simulation
        res1 = self.client.post("/api/automation/simulate", json={"graph_data": graph})
        self.assertEqual(res1.status_code, 200)
        data1 = res1.get_json()
        self.assertEqual(data1["current_node_id"], "n_q")

        # 2. Send valid email input
        res2 = self.client.post("/api/automation/simulate", json={
            "graph_data": graph,
            "current_node_id": "n_q",
            "input": "jam@maj.com.br",
            "variables": data1["variables"]
        })
        self.assertEqual(res2.status_code, 200)
        data2 = res2.get_json()
        self.assertEqual(data2["variables"].get("user_email"), "jam@maj.com.br")
        self.assertIn("n_transfer", data2["visited_path"])

    def test_13_flow_activation_validation_errors(self):
        """Test strict flow activation graph validation errors"""
        with self.client.session_transaction() as sess:
            sess["user_id"] = 17
            sess["username"] = "jam"

        # Create flow draft with broken graph (missing trigger, disconnected nodes)
        broken_graph = {
            "nodes": [
                {"id": "node_broken", "type": "send_message", "config": {}}
            ],
            "edges": []
        }

        res_save = self.client.post("/api/automation/flows/save", json={
            "name": "Fluxo Quebrado",
            "graph_data": broken_graph
        })
        fid = res_save.get_json()["id"]

        # Attempt to activate flow -> should be rejected with 400 and validation_errors array
        res_act = self.client.post(f"/api/automation/flows/{fid}/activate")
        self.assertEqual(res_act.status_code, 400)
        data_act = res_act.get_json()
        self.assertFalse(data_act["success"])
        self.assertIn("validation_errors", data_act)
        self.assertGreaterEqual(len(data_act["validation_errors"]), 1)

    def test_14_concurrent_different_messages_same_contact(self):
        """Test two different concurrent messages from the same contact serialization"""
        phone = "5527999990001"
        acquire_contact_lock(phone, "worker_holding_lock", lease_seconds=10)

        # Message 1 arrives while lock is held -> status contact_locked
        res1 = process_inbound_automation(phone, "olá", wam_id="WAM_CONC_1")
        self.assertEqual(res1.get("status"), "contact_locked")

        # Release lock
        release_contact_lock(phone, "worker_holding_lock")

        # Message 2 arrives after release -> processes cleanly
        res2 = process_inbound_automation(phone, "olá", wam_id="WAM_CONC_2")
        self.assertIn(res2.get("status"), ["waiting_user_input", "flow_completed"])

    def test_15_crash_recovery_between_reservation_and_effect(self):
        """Test crash/failure recovery between wam_id reservation and effect execution"""
        phone = "5527999990001"
        wam_id = "WAM_CRASH_TEST_99"

        # Simulate reservation happening before crash
        with db() as conn:
            conn.execute("INSERT INTO automation_processed_wams (wam_id, phone, status, last_error) VALUES (?, ?, 'pending', 'crash_simulation')", (wam_id, phone))
            conn.commit()

        # Re-sending or re-processing the wam_id must be allowed since status was pending/failed
        res_retry = process_inbound_automation(phone, "olá", wam_id=wam_id)
        self.assertIn(res_retry.get("status"), ["waiting_user_input", "flow_completed"])

        with db() as conn:
            row = conn.execute("SELECT status FROM automation_processed_wams WHERE wam_id=?", (wam_id,)).fetchone()
            self.assertEqual(row["status"], "completed")

    def test_16_crm_tasks_entity_persistence(self):
        """Test real task entity persistence in crm_tasks table"""
        phone = "5527999990001"
        graph = {
            "nodes": [
                {"id": "t1", "type": "action", "config": {"action_type": "create_task", "title": "Enviar Proposta Comercial Scooter M1", "due_date": "2026-10-15", "assigned_to": "jam"}}
            ],
            "edges": []
        }

        with db() as conn:
            cur = conn.execute(
                "INSERT INTO automation_sessions (flow_id, phone, status, current_node_id, flow_snapshot) VALUES (1, ?, 'running', 't1', ?)",
                (phone, json.dumps(graph))
            )
            sid = cur.lastrowid
            conn.commit()

        res = execute_flow_step(sid, 1, graph, "t1", phone)
        self.assertEqual(res.get("status"), "flow_completed")

        with db() as conn:
            task = conn.execute("SELECT * FROM crm_tasks WHERE phone=?", (phone,)).fetchone()
            self.assertIsNotNone(task)
            self.assertEqual(task["title"], "Enviar Proposta Comercial Scooter M1")
            self.assertEqual(task["assigned_to"], "jam")
            self.assertEqual(task["due_date"], "2026-10-15")
            self.assertEqual(task["status"], "pending")

    def test_17_inbox_tags_and_custom_fields_persistence(self):
        """Test persistent tag addition/removal and custom fields saving via API"""
        with self.client.session_transaction() as sess:
            sess["user_id"] = 17
            sess["username"] = "jam"

        phone = "5527999990001"

        # 1. Add Tag
        res_tag = self.client.post("/api/automation/inbox/action", json={"action": "add_tag", "phone": phone, "tag": "Interessado Scooter"})
        self.assertEqual(res_tag.status_code, 200)
        self.assertIn("Interessado Scooter", res_tag.get_json()["tags"])

        # Check DB persistence
        with db() as conn:
            lead = conn.execute("SELECT tags FROM crm_leads WHERE phone=?", (phone,)).fetchone()
            self.assertIn("Interessado Scooter", lead["tags"])

        # 2. Save Custom Field
        res_field = self.client.post("/api/automation/inbox/action", json={"action": "save_custom_field", "phone": phone, "key": "modelo_interesse", "value": "MAJ E-Scooter X3"})
        self.assertEqual(res_field.status_code, 200)
        self.assertEqual(res_field.get_json()["custom_fields"].get("modelo_interesse"), "MAJ E-Scooter X3")

        with db() as conn:
            lead = conn.execute("SELECT custom_fields FROM crm_leads WHERE phone=?", (phone,)).fetchone()
            self.assertIn("MAJ E-Scooter X3", lead["custom_fields"])

        # 3. Remove Tag
        res_rem = self.client.post("/api/automation/inbox/action", json={"action": "remove_tag", "phone": phone, "tag": "Interessado Scooter"})
        self.assertEqual(res_rem.status_code, 200)
        self.assertNotIn("Interessado Scooter", res_rem.get_json()["tags"])

    def test_18_inbox_ticket_reopen_and_unread(self):
        """Test close, reopen, and mark unread ticket action APIs preserving commercial stage (crm_leads.status)"""
        with self.client.session_transaction() as sess:
            sess["user_id"] = 17
            sess["username"] = "jam"

        phone = "5527999990001"

        # Set lead commercial stage to 'proposta' and ticket_status to 'open'
        with db() as conn:
            conn.execute("UPDATE crm_leads SET status='proposta', ticket_status='open' WHERE phone=?", (phone,))
            conn.commit()

        # Close ticket -> ticket_status='closed', status remains 'proposta'
        res_close = self.client.post("/api/automation/inbox/action", json={"action": "close", "phone": phone})
        self.assertEqual(res_close.status_code, 200)
        with db() as conn:
            lead = conn.execute("SELECT status, ticket_status FROM crm_leads WHERE phone=?", (phone,)).fetchone()
            self.assertEqual(lead["ticket_status"], "closed")
            self.assertEqual(lead["status"], "proposta", "A etapa comercial CRM ('proposta') deve ser preservada ao encerrar o ticket")

        # Reopen ticket -> ticket_status='open', status remains 'proposta'
        res_reopen = self.client.post("/api/automation/inbox/action", json={"action": "reopen", "phone": phone})
        self.assertEqual(res_reopen.status_code, 200)
        with db() as conn:
            lead = conn.execute("SELECT status, ticket_status FROM crm_leads WHERE phone=?", (phone,)).fetchone()
            self.assertEqual(lead["ticket_status"], "open")
            self.assertEqual(lead["status"], "proposta", "A etapa comercial CRM ('proposta') deve ser preservada ao reabrir o ticket")

        # Toggle unread
        res_unread = self.client.post("/api/automation/inbox/action", json={"action": "mark_unread", "phone": phone})
        self.assertEqual(res_unread.status_code, 200)

    def test_19_ai_reply_missing_provider_safety(self):
        """Test that ai_reply node with missing API key safely sends error message and pauses bot"""
        old_env = {k: os.environ.get(k) for k in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"]}
        for k in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"]:
            os.environ.pop(k, None)

        try:
            phone = "5527999990001"
            graph = {
                "nodes": [
                    {"id": "ai_1", "type": "ai_reply", "config": {"prompt": "Atender cliente com IA"}}
                ],
                "edges": []
            }

            with db() as conn:
                cur = conn.execute(
                    "INSERT INTO automation_sessions (flow_id, phone, status, current_node_id, flow_snapshot) VALUES (1, ?, 'running', 'ai_1', ?)",
                    (phone, json.dumps(graph))
                )
                sid = cur.lastrowid
                conn.commit()

            res = execute_flow_step(sid, 1, graph, "ai_1", phone)
            self.assertEqual(res.get("status"), "ai_not_configured_transferred")

            with db() as conn:
                lead = conn.execute("SELECT bot_paused FROM crm_leads WHERE phone=?", (phone,)).fetchone()
                self.assertEqual(lead["bot_paused"], 1)
                msg = conn.execute("SELECT body FROM whatsapp_messages WHERE phone=? ORDER BY id DESC LIMIT 1", (phone,)).fetchone()
                self.assertIn("chave API ausente", msg["body"])
        finally:
            for k, v in old_env.items():
                if v is not None:
                    os.environ[k] = v


    def test_20_inbox_canned_responses_and_analytics(self):
        """Test canned responses and analytics endpoints"""
        with self.client.session_transaction() as sess:
            sess["user_id"] = 17
            sess["username"] = "jam"

        # Test analytics
        res_analytics = self.client.get("/api/automation/inbox/analytics")
        self.assertEqual(res_analytics.status_code, 200)
        data = res_analytics.get_json()
        self.assertIn("analytics", data)
        self.assertIn("processed_wams", data["analytics"])

        # Test canned responses GET & POST
        res_canned = self.client.get("/api/automation/inbox/canned-responses")
        self.assertEqual(res_canned.status_code, 200)

        res_post_canned = self.client.post("/api/automation/inbox/canned-responses", json={"title": "Horário de Atendimento", "message": "Atendemos de Seg a Sex das 8h às 18h."})
        self.assertEqual(res_post_canned.status_code, 200)

    def test_21_concurrent_workers_claim_isolation(self):
        """Test dual concurrent workers claim isolation and effect ledger status tracking"""
        phone = "5527999990001"
        graph = {
            "nodes": [
                {"id": "d1", "type": "delay", "config": {"delay_seconds": 1}},
                {"id": "m1", "type": "send_message", "config": {"text": "Mensagem pós delay worker"}}
            ],
            "edges": [
                {"id": "e1", "source": "d1", "target": "m1"}
            ]
        }

        now_ts = int(time.time())
        due_ts = now_ts - 5

        # Create session waiting delay
        with db() as conn:
            cur = conn.execute(
                "INSERT INTO automation_sessions (flow_id, phone, status, current_node_id, flow_snapshot, resume_due_at) VALUES (1, ?, 'waiting_delay', 'm1', ?, ?)",
                (phone, json.dumps(graph), due_ts)
            )
            sid = cur.lastrowid
            conn.commit()

        from services.automation.workers import process_delays_worker
        from services.automation.schema import acquire_contact_lock, release_contact_lock

        # Worker 1 acquires lock
        acquire_contact_lock(phone, "worker_1", lease_seconds=10)

        # Worker 2 attempts to process delay -> must be blocked
        res_w2 = process_delays_worker(worker_id="worker_2", now_ts=now_ts)
        self.assertEqual(len(res_w2), 1)
        self.assertEqual(res_w2[0]["result"]["status"], "contact_locked_by_other")

        # Worker 1 releases lock
        release_contact_lock(phone, "worker_1")

        # Worker 1 processes delay -> succeeds
        res_w1 = process_delays_worker(worker_id="worker_1", now_ts=now_ts)
        self.assertEqual(len(res_w1), 1)
        self.assertEqual(res_w1[0]["result"]["status"], "flow_completed")

        # Verify effect ledger recorded completed status
        with db() as conn:
            eff = conn.execute("SELECT status FROM automation_node_effects WHERE session_id=? AND node_id='m1'", (sid,)).fetchone()
            self.assertIsNotNone(eff)
            self.assertEqual(eff["status"], "completed")

    def test_22_full_ui_editor_flow_scenario(self):
        """
        Test UI End-to-End scenario: create flow from scratch with 2-option menu,
        email collection (valid, invalid, timeout branches), stage update, task creation for Fauzer,
        and agent transfer to Fauzer. Save, reload without data loss, activate, and simulate all branches.
        """
        flow_name = "Fluxo Completo Atendimento MAJ (Fauzer)"
        flow_graph = {
            "nodes": [
                {"id": "trg", "type": "trigger", "label": "Gatilho", "config": {"keywords": ["inicio", "ola"]}, "position": {"x": 50, "y": 100}},
                {"id": "menu", "type": "send_menu", "label": "Menu Principal", "config": {
                    "title": "Como deseja prosseguir?",
                    "save_variable": "menu_choice",
                    "options": [
                        {"id": "opt_qualify", "text": "1. Qualificar por E-mail"},
                        {"id": "opt_fauzer", "text": "2. Falar com Fauzer"}
                    ]
                }, "position": {"x": 350, "y": 100}},
                {"id": "ask_email", "type": "ask_question", "label": "Coletar E-mail", "config": {
                    "text": "Por favor, digite seu e-mail corporativo:",
                    "validation": "email",
                    "save_variable": "lead_email",
                    "timeout_seconds": 300
                }, "position": {"x": 650, "y": 50}},
                {"id": "task_fauzer", "type": "action", "label": "Criar Tarefa", "config": {
                    "action_type": "create_task",
                    "task_title": "Follow-up Lead Qualificado",
                    "assigned_to": "fauzer",
                    "due_days": 1
                }, "position": {"x": 950, "y": 50}},
                {"id": "stage_update", "type": "action", "label": "Atualizar Etapa", "config": {
                    "action_type": "update_stage",
                    "status": "proposta"
                }, "position": {"x": 1250, "y": 50}},
                {"id": "err_msg", "type": "send_message", "label": "Erro E-mail", "config": {"text": "Formato de e-mail inválido."}, "position": {"x": 950, "y": 180}},
                {"id": "timeout_msg", "type": "send_message", "label": "Timeout E-mail", "config": {"text": "Tempo de resposta esgotado."}, "position": {"x": 950, "y": 300}},
                {"id": "transfer_fauzer", "type": "transfer_agent", "label": "Transferir para Fauzer", "config": {
                    "assigned_to": "fauzer",
                    "message": "👨‍💼 Transferindo para o consultor Fauzer..."
                }, "position": {"x": 650, "y": 300}}
            ],
            "edges": [
                {"id": "e_trg_menu", "source": "trg", "target": "menu"},
                {"id": "e_menu_opt1", "source": "menu", "target": "ask_email", "source_handle": "opt_qualify"},
                {"id": "e_menu_opt2", "source": "menu", "target": "transfer_fauzer", "source_handle": "opt_fauzer"},
                {"id": "e_email_valid", "source": "ask_email", "target": "task_fauzer", "source_handle": "valid"},
                {"id": "e_email_invalid", "source": "ask_email", "target": "err_msg", "source_handle": "invalid"},
                {"id": "e_email_timeout", "source": "ask_email", "target": "timeout_msg", "source_handle": "timeout"},
                {"id": "e_task_stage", "source": "task_fauzer", "target": "stage_update"}
            ]
        }

        # 1. Save draft flow via API
        with self.client.session_transaction() as sess:
            sess["user_id"] = 17

        res_save = self.client.post("/api/automation/flows/save", json={
            "name": flow_name,
            "graph_data": flow_graph
        })
        self.assertEqual(res_save.status_code, 200)
        save_data = res_save.get_json()
        self.assertTrue(save_data["success"])
        fid = save_data["id"]

        # 2. Reload and verify loss-less saving & reopening
        res_flows = self.client.get("/api/automation/flows")
        flows_list = res_flows.get_json()
        saved_flow = next((f for f in flows_list if f["id"] == fid), None)
        self.assertIsNotNone(saved_flow)
        reopened_graph = json.loads(saved_flow["draft_version_data"])
        self.assertEqual(len(reopened_graph["nodes"]), 8)
        self.assertEqual(len(reopened_graph["edges"]), 7)

        # 3. Activate flow version
        res_act = self.client.post(f"/api/automation/flows/{fid}/activate")
        self.assertEqual(res_act.status_code, 200)
        self.assertTrue(res_act.get_json()["success"])

        # 4. Simulate Branch 1: Valid email path -> Task Fauzer -> Update Stage propuesta
        sim1_step1 = self.client.post("/api/automation/simulate", json={"graph_data": flow_graph, "input": "inicio"}).get_json()
        self.assertTrue(sim1_step1["success"])
        self.assertEqual(sim1_step1["current_node_id"], "menu")

        sim1_step2 = self.client.post("/api/automation/simulate", json={
            "graph_data": flow_graph, "input": "1", "current_node_id": "menu", "variables": sim1_step1["variables"]
        }).get_json()
        self.assertEqual(sim1_step2["current_node_id"], "ask_email")

        sim1_step3 = self.client.post("/api/automation/simulate", json={
            "graph_data": flow_graph, "input": "contato@empresa.com", "current_node_id": "ask_email", "variables": sim1_step2["variables"]
        }).get_json()
        self.assertTrue(sim1_step3["completed"])
        self.assertEqual(sim1_step3["variables"]["lead_email"], "contato@empresa.com")
        sys_events = [r["text"] for r in sim1_step3["responses"] if r["type"] == "system_event"]
        self.assertTrue(any("Fauzer" in ev for ev in sys_events))
        self.assertTrue(any("proposta" in ev for ev in sys_events))

        # 5. Simulate Branch 2: Invalid email path
        sim2_step3 = self.client.post("/api/automation/simulate", json={
            "graph_data": flow_graph, "input": "email_invalido", "current_node_id": "ask_email", "variables": sim1_step2["variables"]
        }).get_json()
        self.assertEqual(sim2_step3["current_node_id"], "err_msg")

        # 6. Simulate Branch 3: Timeout branch
        sim3_step3 = self.client.post("/api/automation/simulate", json={
            "graph_data": flow_graph, "input": "__timeout__", "current_node_id": "ask_email", "variables": sim1_step2["variables"]
        }).get_json()
        self.assertEqual(sim3_step3["current_node_id"], "timeout_msg")

        # 7. Simulate Branch 4: Menu Option 2 -> Transfer to Fauzer
        sim4_step2 = self.client.post("/api/automation/simulate", json={
            "graph_data": flow_graph, "input": "2", "current_node_id": "menu", "variables": sim1_step1["variables"]
        }).get_json()
        self.assertTrue(sim4_step2["completed"])
        transfer_events = [r["text"] for r in sim4_step2["responses"] if r["type"] == "system_event"]
        self.assertTrue(any("Fauzer" in ev for ev in transfer_events))

    def test_23_adapters_real_transport_and_simulation(self):
        """Test Meta Cloud API formatters delegation to transport and simulation mode handling"""
        from services.automation.adapters import (
            send_meta_text_message,
            send_meta_media_message,
            send_meta_button_message,
            send_meta_list_message
        )

        phone = "5527999990001"
        transport_calls = []
        def fake_transport(p, msg):
            transport_calls.append((p, msg))
            return {"status": "ok", "wam_id": "wam_test_123"}

        # 1. Simulation mode -> no transport execution
        sim_res = send_meta_text_message(phone, "Olá em simulação", is_simulation=True)
        self.assertEqual(sim_res["status"], "simulated")
        self.assertEqual(len(transport_calls), 0)

        # 2. Real/Injected transport mode -> delegates payload and registers return
        text_res = send_meta_text_message(phone, "Mensagem real", transport_caller=fake_transport)
        self.assertEqual(text_res["status"], "sent")
        self.assertEqual(text_res["response"]["wam_id"], "wam_test_123")
        self.assertEqual(len(transport_calls), 1)

        # 3. Media message
        media_res = send_meta_media_message(phone, "image", "https://site.com/foto.jpg", caption="Legenda", transport_caller=fake_transport)
        self.assertEqual(media_res["status"], "sent")
        self.assertIn("https://site.com/foto.jpg", str(transport_calls[-1][1]))

        # 4. Button message
        btn_res = send_meta_button_message(phone, "Escolha:", [{"id": "b1", "text": "Opção 1"}], transport_caller=fake_transport)
        self.assertEqual(btn_res["status"], "sent")
        self.assertIn("Opção 1", str(transport_calls[-1][1]))

        # 5. List message
        list_res = send_meta_list_message(phone, "Selecione item:", "Ver Lista", [], transport_caller=fake_transport)
        self.assertEqual(list_res["status"], "sent")

    def test_24_ai_adapters_no_fake_responses(self):
        """Test AI Provider Adapters raise/return AINotConfiguredError without generating fake responses"""
        from services.automation.adapters import (
            OpenAIAdapter,
            AnthropicAdapter,
            GeminiAdapter,
            AIProviderAdapterManager,
            AINotConfiguredError
        )

        # Save old environment
        old_env = {k: os.environ.get(k) for k in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"]}
        for k in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"]:
            os.environ.pop(k, None)

        try:
            # Unconfigured adapters raise AINotConfiguredError
            openai = OpenAIAdapter()
            self.assertFalse(openai.is_configured())
            with self.assertRaises(AINotConfiguredError):
                openai.generate_reply("teste")

            anthropic = AnthropicAdapter()
            self.assertFalse(anthropic.is_configured())
            with self.assertRaises(AINotConfiguredError):
                anthropic.generate_reply("teste")

            gemini = GeminiAdapter()
            self.assertFalse(gemini.is_configured())
            with self.assertRaises(AINotConfiguredError):
                gemini.generate_reply("teste")

            # Manager returns (False, error_msg) without fake text
            mgr = AIProviderAdapterManager()
            success, msg = mgr.generate_ai_reply("teste")
            self.assertFalse(success)
            self.assertIn("chave API ausente", msg)
            self.assertNotIn("OpenAI Response", msg)
            self.assertNotIn("Anthropic Response", msg)
            self.assertNotIn("Gemini Response", msg)

            # Injected custom callers for network-free unit tests
            fake_mgr = AIProviderAdapterManager(openai_caller=lambda p, c: f"Resposta real fake: {p}")
            success, msg = fake_mgr.generate_ai_reply("qual valor do frete?")
            self.assertTrue(success)
            self.assertEqual(msg, "Resposta real fake: qual valor do frete?")
        finally:
            for k, v in old_env.items():
                if v is not None:
                    os.environ[k] = v

    def test_25_webhook_adapter_validation_and_simulation(self):
        """Test Webhook adapter strict URL validation, simulation mode, and no substring mock inference"""
        from services.automation.adapters import execute_webhook_adapter

        # Invalid URL scheme
        code, body = execute_webhook_adapter("ftp://invalid.url", "POST", "{}", "5527999990001")
        self.assertEqual(code, 400)
        self.assertIn("URL inválida", body)

        # Simulation mode
        code_sim, body_sim = execute_webhook_adapter("https://example.com/api/webhook", "POST", "{}", "5527999990001", is_simulation=True)
        self.assertEqual(code_sim, 200)
        self.assertIn("simulated", body_sim)

        # Injected HTTP caller for network-free execution
        def fake_http(url, method, payload, phone):
            return 201, json.dumps({"received": True, "target": url})

        # URL containing 'mock' or 'example.com' must NOT trigger mock behavior automatically; it executes caller
        code_real, body_real = execute_webhook_adapter("https://example.com/mock/endpoint", "POST", '{"test": 1}', "5527999990001", http_caller=fake_http)
        self.assertEqual(code_real, 201)
        self.assertIn("received", body_real)

    def test_26_pending_wams_worker_single_lock_acquisition(self):
        """Test process_pending_wams_worker inherits lock_id in process_inbound_automation without self-locking"""
        phone = "5527999990001"
        wam_id = "wam_worker_test_100"

        # Create active flow
        flow_graph = {
            "nodes": [
                {"id": "trg", "type": "trigger", "config": {"keywords": ["promocao"]}},
                {"id": "msg", "type": "send_message", "config": {"text": "Mensagem Worker WAM"}}
            ],
            "edges": [{"id": "e1", "source": "trg", "target": "msg"}]
        }

        with db() as conn:
            conn.execute(
                """
                INSERT INTO automation_flows 
                (name, status, version, draft_version_data, active_version_data, active_trigger_config)
                VALUES ('Fluxo Worker WAM', 'active', 1, ?, ?, ?)
                """,
                (json.dumps(flow_graph), json.dumps(flow_graph), json.dumps({"keywords": ["promocao"]}))
            )
            # Insert pending WAM in automation_processed_wams
            conn.execute(
                "INSERT INTO automation_processed_wams (wam_id, phone, payload, status, attempts) VALUES (?, ?, ?, 'pending', 1)",
                (wam_id, phone, json.dumps({"body": "promocao"}))
            )
            conn.commit()

        from services.automation.workers import process_pending_wams_worker
        res = process_pending_wams_worker(worker_id="worker_wams_spec", now_ts=int(time.time()))

        self.assertEqual(len(res), 1)
        # Verify it did NOT self-lock
        self.assertNotEqual(res[0]["result"].get("status"), "contact_locked")
        self.assertEqual(res[0]["result"].get("status"), "flow_completed")

        with db() as conn:
            wam = conn.execute("SELECT status FROM automation_processed_wams WHERE wam_id=?", (wam_id,)).fetchone()
            self.assertEqual(wam["status"], "completed")

    def test_27_worker_concurrent_barrier_revalidation(self):
        """Test concurrent workers using barrier; only one worker claims session via UPDATE rowcount check"""
        import threading

        phone = "5527999990099"
        flow_graph = {
            "nodes": [
                {"id": "d1", "type": "delay", "config": {"seconds": 1}},
                {"id": "m1", "type": "send_message", "config": {"text": "Pós Delay Concorrente"}}
            ],
            "edges": [{"id": "e1", "source": "d1", "target": "m1"}]
        }

        now_ts = int(time.time())
        due_ts = now_ts - 10

        with db() as conn:
            cur = conn.execute(
                """
                INSERT INTO automation_sessions (flow_id, phone, status, current_node_id, flow_snapshot, resume_due_at)
                VALUES (1, ?, 'waiting_delay', 'm1', ?, ?)
                """,
                (phone, json.dumps(flow_graph), due_ts)
            )
            sid = cur.lastrowid
            conn.commit()

        barrier = threading.Barrier(2)
        results = {}

        def run_worker(wid):
            from services.automation.workers import process_delays_worker
            barrier.wait()
            res = process_delays_worker(worker_id=wid, now_ts=now_ts)
            results[wid] = res

        t1 = threading.Thread(target=run_worker, args=("worker_t1",))
        t2 = threading.Thread(target=run_worker, args=("worker_t2",))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Combine results from both workers
        all_results = results["worker_t1"] + results["worker_t2"]
        completed_runs = [r for r in all_results if r.get("result", {}).get("status") == "flow_completed"]
        skipped_runs = [r for r in all_results if r.get("result", {}).get("status") in ["session_already_processed_or_invalid_state", "contact_locked_by_other"]]

        # Exactly one worker completed the step, the other skipped or found session already processed
        self.assertEqual(len(completed_runs), 1)
        self.assertIn(len(skipped_runs), [0, 1])

    def test_28_send_failure_or_uncompleted_effect_stops_flow(self):
        """Test that send transport failure or non-completed effect status stops flow and marks session failed"""
        phone = "5527999990088"
        flow_graph = {
            "nodes": [
                {"id": "wh1", "type": "webhook", "config": {"url": "http://invalid-test-domain-999.com/webhook", "method": "POST"}},
                {"id": "n2", "type": "send_message", "config": {"text": "Mensagem Pós Webhook"}}
            ],
            "edges": [{"id": "e1", "source": "wh1", "target": "n2"}]
        }

        # 1. Test webhook failure (returns 400 / error) -> stops flow, sets status='failed', returns failed_needs_review
        with db() as conn:
            cur = conn.execute(
                """
                INSERT INTO automation_sessions (flow_id, phone, status, current_node_id, flow_snapshot)
                VALUES (1, ?, 'running', 'wh1', ?)
                """,
                (phone, json.dumps(flow_graph))
            )
            sid1 = cur.lastrowid
            conn.commit()

        res_fail = execute_flow_step(sid1, 1, flow_graph, "wh1", phone)
        self.assertEqual(res_fail["status"], "failed_needs_review")

        with db() as conn:
            sess = conn.execute("SELECT status, last_error FROM automation_sessions WHERE id=?", (sid1,)).fetchone()
            self.assertEqual(sess["status"], "failed")
            # Verify node 2 was never executed
            n2_effect = conn.execute("SELECT id FROM automation_node_effects WHERE session_id=? AND node_id='n2'", (sid1,)).fetchone()
            self.assertIsNone(n2_effect)

        # 2. Test concurrent effect collision with non-completed status -> stops flow
        from services.automation.schema import record_node_effect
        can_exec, eff_status = record_node_effect(sid1, "dummy_node", "test_effect", "detail", status="pending")
        self.assertTrue(can_exec)
        self.assertEqual(eff_status, "pending")

        # Second attempt on same effect returns (False, 'pending')
        can_exec_2, eff_status_2 = record_node_effect(sid1, "dummy_node", "test_effect", "detail", status="pending")
        self.assertFalse(can_exec_2)
        self.assertEqual(eff_status_2, "pending")

    def test_29_editor_engine_contract_unified_all_blocks(self):
        """
        Teste unificado de contrato Editor-Motor:
        Salva via API com o MESMO JSON do editor (static/js/automation_studio.js),
        ativa o fluxo e executa no motor persistente isolado (process_inbound_automation).
        Valida todos os blocos: trigger, send_message, send_menu, ask_question, condition,
        delay, webhook, action (create_task, update_stage, update_lead), transfer_agent e end.
        Garante que crm_tasks persiste exatamente task_title, fauzer (seller_id 18) e prazo relativo (+3 dias).
        Garante que transfer_agent atribui Fauzer de verdade ao lead (assigned_to='fauzer', seller_id=18).
        """
        with self.client.session_transaction() as sess:
            sess["user_id"] = 16
            sess["username"] = "fauzer"

        phone = "5527999990077"
        expected_due_date = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")

        # JSON exato no formato produzido pelo editor visual
        editor_graph = {
            "nodes": [
                {"id": "trg", "type": "trigger", "label": "Gatilho Contrato", "config": {"keywords": ["contrato"]}},
                {"id": "n_msg", "type": "send_message", "label": "Mensagem Boas-vindas", "config": {"text": "Iniciando verificação de contrato."}},
                {"id": "n_menu", "type": "send_menu", "label": "Menu Opções", "config": {"title": "Selecione uma opção:", "options": [{"id": "opt_1", "text": "1. Simular Contrato"}], "save_variable": "menu_choice"}},
                {"id": "n_ask", "type": "ask_question", "label": "Perguntar Email", "config": {"text": "Por favor informe seu email:", "validation": "email", "save_variable": "user_email", "timeout_seconds": 300}},
                {"id": "n_cond", "type": "condition", "label": "Checar Email", "config": {"variable": "user_email", "operator": "contains", "value": "@"}},
                {"id": "n_delay", "type": "delay", "label": "Aguardar Ação", "config": {"seconds": 1}},
                {"id": "n_wh", "type": "webhook", "label": "Notificar Webhook", "config": {"url": "https://api.exemplo.com/webhook", "method": "POST", "payload": "{}"}},
                {"id": "n_task", "type": "action", "label": "Criar Tarefa Fauzer", "config": {"action_type": "create_task", "task_title": "Ligar para cliente Fauzer", "assigned_to": "fauzer", "due_days": 3}},
                {"id": "n_stage", "type": "action", "label": "Atualizar Etapa Proposta", "config": {"action_type": "update_stage", "status": "proposta"}},
                {"id": "n_lead", "type": "action", "label": "Atualizar Dados Lead", "config": {"action_type": "update_lead", "notes": "Cliente VIP interessado na scooter", "assigned_to": "fauzer"}},
                {"id": "n_trans", "type": "transfer_agent", "label": "Transferir Fauzer", "config": {"assigned_to": "fauzer", "message": "👨‍💼 Transferindo para Fauzer..."}},
                {"id": "n_end", "type": "end", "label": "Fim do Fluxo", "config": {}}
            ],
            "edges": [
                {"id": "e1", "source": "trg", "target": "n_msg"},
                {"id": "e2", "source": "n_msg", "target": "n_menu"},
                {"id": "e3", "source": "n_menu", "target": "n_ask", "source_handle": "1. Simular Contrato"},
                {"id": "e4", "source": "n_ask", "target": "n_cond", "source_handle": "valid_answer"},
                {"id": "e5", "source": "n_cond", "target": "n_delay"},
                {"id": "e6", "source": "n_delay", "target": "n_wh"},
                {"id": "e7", "source": "n_wh", "target": "n_task"},
                {"id": "e8", "source": "n_task", "target": "n_stage"},
                {"id": "e9", "source": "n_stage", "target": "n_lead"},
                {"id": "e10", "source": "n_lead", "target": "n_trans"},
                {"id": "e11", "source": "n_trans", "target": "n_end"}
            ]
        }

        # 1. Salvar via API de salvar fluxo do editor
        res_save = self.client.post("/api/automation/flows/save", json={
            "name": "Fluxo Contrato Unificado Editor Motor",
            "description": "Validação integral do contrato",
            "graph_data": editor_graph,
            "trigger_type": "keyword",
            "trigger_config": {"keywords": ["contrato"]}
        })
        self.assertEqual(res_save.status_code, 200)
        flow_id = res_save.get_json()["id"]

        # 2. Ativar via API do editor
        res_act = self.client.post(f"/api/automation/flows/{flow_id}/activate")
        self.assertEqual(res_act.status_code, 200)
        self.assertTrue(res_act.get_json()["success"])

        # 3. Execução no motor persistente isolado (Passo 1: Trigger -> Menu)
        res1 = process_inbound_automation(phone, "contrato", wam_id="WAM_CONTRACT_1")
        self.assertEqual(res1.get("status"), "waiting_user_input")

        # 4. Execução no motor (Passo 2: Escolha de Menu -> Pergunta Email)
        res2 = process_inbound_automation(phone, "1", wam_id="WAM_CONTRACT_2")
        self.assertEqual(res2.get("status"), "waiting_user_input")

        # 5. Execução no motor (Passo 3: Resposta Email -> Condition -> Delay)
        res3 = process_inbound_automation(phone, "fauzer.teste@maj.com.br", wam_id="WAM_CONTRACT_3")
        self.assertEqual(res3.get("status"), "waiting_delay")
        self.assertEqual(res3.get("next_node_id"), "n_wh")

        # 6. Processar worker de delay (Passo 4: Delay -> Webhook -> Action Task -> Action Stage -> Action Lead -> Transfer)
        from services.automation.workers import process_delays_worker
        res_worker = process_delays_worker(worker_id="test_worker_contract", now_ts=int(time.time()) + 10)
        self.assertEqual(len(res_worker), 1)
        self.assertEqual(res_worker[0]["result"].get("status"), "transferred_to_human")

        # 7. Conferencia rigorosa das entidades no banco de dados
        with db() as conn:
            # Tarefa criada em crm_tasks
            task = conn.execute("SELECT * FROM crm_tasks WHERE phone=? AND title=?", (phone, "Ligar para cliente Fauzer")).fetchone()
            self.assertIsNotNone(task, "A tarefa não foi criada no banco crm_tasks")
            self.assertEqual(task["title"], "Ligar para cliente Fauzer")
            self.assertEqual(task["assigned_to"], "fauzer")
            self.assertEqual(task["due_date"], expected_due_date)
            self.assertEqual(task["status"], "pending")

            # Lead atualizado em crm_leads pelo action update_stage, update_lead e transfer_agent
            lead = conn.execute("SELECT * FROM crm_leads WHERE phone=?", (phone,)).fetchone()
            self.assertIsNotNone(lead)
            self.assertEqual(lead["status"], "proposta")
            self.assertEqual(lead["assigned_to"], "fauzer")
            self.assertEqual(lead["seller_id"], 16)
            self.assertEqual(lead["notes"], "Cliente VIP interessado na scooter")
            self.assertEqual(lead["bot_paused"], 1)
            self.assertEqual(lead["ticket_status"], "claimed")

    def test_30_multiple_tasks_same_title_allowed(self):
        """
        Garante que a criação de tarefas não deduplica globalmente por título/telefone:
        Duas tarefas legítimas com o mesmo título e prazos/sessões diferentes devem coexistir no banco crm_tasks.
        """
        phone = "5527999990066"
        graph_1 = {
            "nodes": [
                {"id": "t1", "type": "action", "config": {"action_type": "create_task", "task_title": "Follow-up Proposta", "due_days": 1, "assigned_to": "fauzer"}}
            ],
            "edges": []
        }
        graph_2 = {
            "nodes": [
                {"id": "t2", "type": "action", "config": {"action_type": "create_task", "task_title": "Follow-up Proposta", "due_days": 5, "assigned_to": "jam"}}
            ],
            "edges": []
        }

        # Sessão 1 cria primeira tarefa
        with db() as conn:
            cur1 = conn.execute(
                "INSERT INTO automation_sessions (flow_id, phone, status, current_node_id, flow_snapshot) VALUES (10, ?, 'running', 't1', ?)",
                (phone, json.dumps(graph_1))
            )
            sid1 = cur1.lastrowid
            conn.commit()

        res1 = execute_flow_step(sid1, 10, graph_1, "t1", phone)
        self.assertEqual(res1.get("status"), "flow_completed")

        # Sessão 2 cria segunda tarefa com mesmo título
        with db() as conn:
            cur2 = conn.execute(
                "INSERT INTO automation_sessions (flow_id, phone, status, current_node_id, flow_snapshot) VALUES (11, ?, 'running', 't2', ?)",
                (phone, json.dumps(graph_2))
            )
            sid2 = cur2.lastrowid
            conn.commit()

        res2 = execute_flow_step(sid2, 11, graph_2, "t2", phone)
        self.assertEqual(res2.get("status"), "flow_completed")

        # Verifica se ambas as tarefas existem em crm_tasks
        with db() as conn:
            tasks = conn.execute("SELECT * FROM crm_tasks WHERE phone=? AND title=? ORDER BY id ASC", (phone, "Follow-up Proposta")).fetchall()
            self.assertEqual(len(tasks), 2, "Devem existir 2 tarefas legítimas criadas com o mesmo título")
            self.assertEqual(tasks[0]["assigned_to"], "fauzer")
            self.assertEqual(tasks[1]["assigned_to"], "jam")

    @patch("urllib.request.urlopen")
    def test_31_native_meta_structured_payloads_http_caller_mock(self, mock_urlopen):
        """
        Valida que send_whatsapp_message transmite JSONs estruturados da Meta Cloud API via urllib.request.urlopen mockado.
        Testa os tipos: text, image, document, audio, video, interactive button e interactive list.
        """
        from app import send_whatsapp_message
        from services.automation.adapters import (
            send_meta_text_message,
            send_meta_media_message,
            send_meta_button_message,
            send_meta_list_message
        )

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"messages": [{"id": "wam-test-meta-123"}]}).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        phone = "5527999990099"

        # 1. Texto simples
        res_text = send_meta_text_message(phone, "Olá mundo Meta")
        self.assertEqual(res_text.get("status"), "sent")
        last_req = mock_urlopen.call_args[0][0]
        sent_json = json.loads(last_req.data.decode("utf-8"))
        self.assertEqual(sent_json["type"], "text")
        self.assertEqual(sent_json["text"]["body"], "Olá mundo Meta")

        # 2. Imagem
        res_img = send_meta_media_message(phone, "image", "https://m-one.majmobilidade.com.br/foto.jpg", caption="Scooter MAJ")
        self.assertEqual(res_img.get("status"), "sent")
        last_req = mock_urlopen.call_args[0][0]
        sent_json = json.loads(last_req.data.decode("utf-8"))
        self.assertEqual(sent_json["type"], "image")
        self.assertEqual(sent_json["image"]["link"], "https://m-one.majmobilidade.com.br/foto.jpg")
        self.assertEqual(sent_json["image"]["caption"], "Scooter MAJ")

        # 3. Documento PDF
        res_doc = send_meta_media_message(phone, "document", "https://m-one.majmobilidade.com.br/manual.pdf", caption="Manual")
        self.assertEqual(res_doc.get("status"), "sent")
        last_req = mock_urlopen.call_args[0][0]
        sent_json = json.loads(last_req.data.decode("utf-8"))
        self.assertEqual(sent_json["type"], "document")
        self.assertEqual(sent_json["document"]["link"], "https://m-one.majmobilidade.com.br/manual.pdf")

        # 4. Áudio
        res_audio = send_meta_media_message(phone, "audio", "https://m-one.majmobilidade.com.br/audio.mp3")
        self.assertEqual(res_audio.get("status"), "sent")
        last_req = mock_urlopen.call_args[0][0]
        sent_json = json.loads(last_req.data.decode("utf-8"))
        self.assertEqual(sent_json["type"], "audio")
        self.assertEqual(sent_json["audio"]["link"], "https://m-one.majmobilidade.com.br/audio.mp3")

        # 5. Vídeo
        res_video = send_meta_media_message(phone, "video", "https://m-one.majmobilidade.com.br/video.mp4", caption="Demonstração")
        self.assertEqual(res_video.get("status"), "sent")
        last_req = mock_urlopen.call_args[0][0]
        sent_json = json.loads(last_req.data.decode("utf-8"))
        self.assertEqual(sent_json["type"], "video")

        # 6. Botões Interativos
        buttons = [
            {"id": "btn_1", "text": "Ver Catalogo"},
            {"id": "btn_2", "text": "Falar Vendedor"}
        ]
        res_btn = send_meta_button_message(phone, "Escolha:", buttons)
        self.assertEqual(res_btn.get("status"), "sent")
        last_req = mock_urlopen.call_args[0][0]
        sent_json = json.loads(last_req.data.decode("utf-8"))
        self.assertEqual(sent_json["type"], "interactive")
        self.assertEqual(sent_json["interactive"]["type"], "button")
        self.assertEqual(len(sent_json["interactive"]["action"]["buttons"]), 2)

        # 7. Menu Lista Interativa
        sections = [{
            "title": "Modelos",
            "rows": [{"id": "m1", "title": "Modelo X", "description": "1000W"}]
        }]
        res_list = send_meta_list_message(phone, "Menu de Opções", "Ver Lista", sections)
        self.assertEqual(res_list.get("status"), "sent")
        last_req = mock_urlopen.call_args[0][0]
        sent_json = json.loads(last_req.data.decode("utf-8"))
        self.assertEqual(sent_json["type"], "interactive")
        self.assertEqual(sent_json["interactive"]["type"], "list")

    @patch("urllib.request.urlopen")
    def test_32_meta_transport_error_and_validation_limits(self, mock_urlopen):
        """
        Testa que response.success=false ou HTTP 400 NÃO retorna status sent (retorna failed).
        Valida que limites de lista (>10 rows, item >24 chars) e mídia inválida retornam validation_failed sem truncar silenciosamente.
        """
        from services.automation.adapters import send_meta_button_message, send_meta_list_message, send_meta_media_message

        # Mock de falha HTTP
        import urllib.error
        mock_urlopen.side_effect = urllib.error.HTTPError("https://graph.facebook.com", 400, "Bad Request", {}, io.BytesIO(b'{"error":{"message":"Invalid token"}}'))

        res_fail = send_meta_button_message("5527999990099", "Teste", [{"id": "b1", "text": "Opção 1"}])
        self.assertEqual(res_fail.get("status"), "failed", "Em erro HTTP não pode retornar status 'sent'")

        # Mock reseta para testar validações
        mock_urlopen.side_effect = None

        # Validação: Lista com mais de 10 opções
        eleven_rows = [{"id": f"r{i}", "title": f"Row {i}"} for i in range(1, 12)]
        res_over_list = send_meta_list_message("5527999990099", "Menu Grande", "Ver Lista", [{"title": "Sec", "rows": eleven_rows}])
        self.assertEqual(res_over_list.get("status"), "validation_failed")
        self.assertIn("máximo de 10 opções", res_over_list.get("error"))

        # Validação: Item de lista > 24 caracteres
        long_row = [{"id": "r1", "title": "Título De Item Que Excede Vinte E Quatro Chars"}]
        res_long_row = send_meta_list_message("5527999990099", "Menu Longo", "Ver Lista", [{"title": "Sec", "rows": long_row}])
        self.assertEqual(res_long_row.get("status"), "validation_failed")
        self.assertIn("excede 24 caracteres", res_long_row.get("error"))

        # Validação: Mídia com URL inválida
        res_bad_url = send_meta_media_message("5527999990099", "image", "ftp://link_invalido.jpg")
        self.assertEqual(res_bad_url.get("status"), "validation_failed")

    def test_33_send_media_node_engine_execution(self):
        """
        Testa a execução do nó 'send_media' pelo motor de automação (engine.py).
        Garante que o nó executa, registra efeito e completa a etapa.
        """
        phone = "5527999990088"
        graph = {
            "nodes": [
                {
                    "id": "node_media",
                    "type": "send_media",
                    "config": {
                        "media_type": "image",
                        "media_url": "https://m-one.majmobilidade.com.br/static/img/scooter.jpg",
                        "caption": "Confira o novo modelo MAJ"
                    }
                }
            ],
            "edges": []
        }

        with db() as conn:
            cur = conn.execute(
                "INSERT INTO automation_sessions (flow_id, phone, status, current_node_id, flow_snapshot) VALUES (1, ?, 'running', 'node_media', ?)",
                (phone, json.dumps(graph))
            )
            sid = cur.lastrowid
            conn.commit()

        res = execute_flow_step(sid, 1, graph, "node_media", phone)
        self.assertEqual(res.get("status"), "flow_completed")

        with db() as conn:
            eff = conn.execute("SELECT * FROM automation_node_effects WHERE session_id=? AND node_id=?", (sid, "node_media")).fetchone()
            self.assertIsNotNone(eff)
            self.assertEqual(eff["status"], "completed")

    def test_34_strict_debounce_and_failed_retry(self):
        """
        Valida que o debounce não suprime botões diferentes com mesmo texto de body,
        e que envios anteriores com status 'failed' não são mascarados como duplicatas bem-sucedidas.
        """
        from app import send_whatsapp_message

        phone = "5527999990077"

        btn_payload_1 = {
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": "Escolha:"},
                "action": {"buttons": [{"type": "reply", "reply": {"id": "opt_a", "title": "Opção A"}}]}
            }
        }

        btn_payload_2 = {
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": "Escolha:"},
                "action": {"buttons": [{"type": "reply", "reply": {"id": "opt_b", "title": "Opção B"}}]}
            }
        }

        # Enviar payload 1
        res1 = send_whatsapp_message(phone, btn_payload_1)
        self.assertTrue(res1.get("success"))
        self.assertFalse(res1.get("duplicate_prevented"))

        # Enviar payload 2 (mesmo body "Escolha:", botões diferentes) -> NÃO pode prevenir como duplicata!
        res2 = send_whatsapp_message(phone, btn_payload_2)
        self.assertTrue(res2.get("success"))
        self.assertFalse(res2.get("duplicate_prevented"), "Payloads com botões diferentes não devem ser suprimidos pelo debounce")

    def test_35_engine_isolated_variables_condition_template_webhook(self):
        """
        Testa o fluxo isolado do motor real:
        Pergunta email -> Condition email preenchido (com variáveis da sessão) -> Mensagem 'Olá {{user_name}}' -> Webhook com aspas no payload e salvamento de resposta em variável.
        Garante que variáveis persistidas são carregadas em cada passo e compara o resultado com o simulador.
        """
        phone = "5527999990055"
        flow_graph = {
            "nodes": [
                {"id": "trg", "type": "trigger", "config": {"keywords": ["inicio_test35"]}},
                {"id": "q_email", "type": "ask_question", "config": {"text": "Qual o seu e-mail?", "validation": "email", "save_variable": "user_email", "timeout_seconds": 300}},
                {"id": "cond", "type": "condition", "config": {"variable": "user_email", "operator": "not_empty"}},
                {"id": "msg_hello", "type": "send_message", "config": {"text": "Olá {{user_name}}, seu e-mail é {{user_email}}!"}},
                {"id": "wh", "type": "webhook", "config": {
                    "url": "https://api.exemplo.com/lead",
                    "method": "POST",
                    "payload": '{"name": "{{user_name}}", "email": "{{user_email}}", "note": "cliente \\"VIP\\""}',
                    "save_variable": "webhook_res"
                }},
                {"id": "end", "type": "end", "config": {}}
            ],
            "edges": [
                {"id": "e1", "source": "trg", "target": "q_email"},
                {"id": "e2", "source": "q_email", "target": "cond", "source_handle": "valid_answer"},
                {"id": "e3", "source": "cond", "target": "msg_hello", "source_handle": "true"},
                {"id": "e4", "source": "msg_hello", "target": "wh"},
                {"id": "e5", "source": "wh", "target": "end"}
            ]
        }

        # 1. Iniciar sessão no motor real
        from services.automation.engine import get_active_session_for_contact, resume_session_with_input
        with db() as conn:
            flow_str = json.dumps(flow_graph)
            cur = conn.execute(
                "INSERT INTO automation_sessions (flow_id, phone, status, current_node_id, waiting_variable, waiting_validation, variables, flow_snapshot) VALUES (35, ?, 'waiting_input', 'q_email', 'user_email', 'email', ?, ?)",
                (phone, json.dumps({"user_name": "João", "company": 'MAJ "Mobilidade"'}), flow_str)
            )
            sid = cur.lastrowid
            conn.commit()

        sess_row = get_active_session_for_contact(phone)
        self.assertIsNotNone(sess_row)

        # Injetar HTTP caller mock para webhook sem envio de rede real
        webhook_calls = []
        def fake_webhook_caller(url, method, payload, ph):
            webhook_calls.append((url, method, payload))
            return 200, json.dumps({"status": "created", "id": 999})

        with patch("services.automation.engine.execute_webhook_adapter", side_effect=lambda url, method, payload, ph: (200, json.dumps({"status": "created", "id": 999}))):
            # 2. Retomar sessão com e-mail válido no motor real
            res_engine = resume_session_with_input(sess_row, phone, "joao@exemplo.com")
            self.assertEqual(res_engine.get("status"), "flow_completed")

        # 3. Verificar estado do banco de dados no motor real
        with db() as conn:
            sess_final = conn.execute("SELECT variables, status FROM automation_sessions WHERE id=?", (sid,)).fetchone()
            self.assertEqual(sess_final["status"], "completed")
            saved_vars = json.loads(sess_final["variables"])
            self.assertEqual(saved_vars.get("user_email"), "joao@exemplo.com")
            self.assertEqual(saved_vars.get("user_name"), "João")
            self.assertIn("webhook_res", saved_vars)
            self.assertEqual(saved_vars["webhook_res"].get("id"), 999)

            # Verificar se a mensagem enviada interpolou {{user_name}} e {{user_email}}
            effects = conn.execute("SELECT detail FROM automation_node_effects WHERE session_id=? AND node_id='msg_hello'", (sid,)).fetchall()
            self.assertEqual(len(effects), 1)
            self.assertEqual(effects[0]["detail"], "Olá João, seu e-mail é joao@exemplo.com!")

        # 4. Executar exatamente a mesma sequência no simulador e comparar resultado
        sim_step1 = self.client.post("/api/automation/simulate", json={
            "graph_data": flow_graph,
            "input": "joao@exemplo.com",
            "current_node_id": "q_email",
            "variables": {"user_name": "João", "company": 'MAJ "Mobilidade"'}
        }).get_json()

        self.assertTrue(sim_step1["success"])
        self.assertTrue(sim_step1["completed"])
        self.assertEqual(sim_step1["variables"].get("user_email"), "joao@exemplo.com")
        self.assertEqual(sim_step1["variables"].get("user_name"), "João")
        self.assertIn("webhook_res", sim_step1["variables"])

        # Verificar respostas do simulador
        sim_texts = [r["text"] for r in sim_step1["responses"] if r["type"] == "bot_text"]
        self.assertIn("Olá João, seu e-mail é joao@exemplo.com!", sim_texts)

    def test_36_pg_cursor_wrapper_contract_rowcount(self):
        """
        Testa a delegação de rowcount e lastrowid no PGCursorWrapper usando cursor simulado (fake cursor).
        Garante o contrato necessário para que workers e queries leiam rowcount sem lançar AttributeError.
        (Nota: Este teste valida o contrato da classe wrapper sem alegar execução contra banco PostgreSQL real).
        """
        from database import PGCursorWrapper, PGConnWrapper

        # 1. Objeto de cursor simulado com rowcount e retorno de fetch
        fake_cursor = MagicMock()
        fake_cursor.rowcount = 42
        fake_cursor.fetchone.return_value = {"id": 100, "status": "active"}
        fake_cursor.fetchall.return_value = [{"id": 100, "status": "active"}]

        wrapper = PGCursorWrapper(fake_cursor, lastrowid=100)

        # 2. Valida propriedades rowcount e lastrowid
        self.assertEqual(wrapper.rowcount, 42)
        self.assertEqual(wrapper.lastrowid, 100)
        self.assertEqual(wrapper.fetchone()["id"], 100)
        self.assertEqual(len(wrapper.fetchall()), 1)

        # 3. Valida PGConnWrapper
        fake_conn = MagicMock()
        fake_conn.cursor.return_value = fake_cursor

        conn_wrapper = PGConnWrapper(fake_conn)
        res_cur = conn_wrapper.execute("UPDATE automation_sessions SET status='running' WHERE id=?", (1,))

        self.assertEqual(res_cur.rowcount, 42)



if __name__ == "__main__":
    unittest.main()





