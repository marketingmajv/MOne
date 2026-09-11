"""
Unit tests for Evolution API Integration & Audio Transcription Service
"""

import json
import unittest
from app import app
from database import db
from services.audio_transcription_service import _encode_multipart_form, transcribe_audio
from services.evolution_service import get_evolution_config, save_evolution_config


class TestEvolutionIntegration(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_multipart_form_encoding(self):
        fields = {"model": "whisper-large-v3-turbo", "language": "pt"}
        file_bytes = b"OggS\x00\x02\x00\x00fakeaudiobytes"
        body, content_type = _encode_multipart_form(fields, file_bytes, "test.ogg", "audio/ogg")
        self.assertIn("multipart/form-data; boundary=", content_type)
        self.assertIn(b"whisper-large-v3-turbo", body)
        self.assertIn(b"fakeaudiobytes", body)

    def test_audio_transcription_fallback(self):
        # Sem chave de API ou com áudio vazio, deve retornar None de forma segura sem lançar exceção
        res = transcribe_audio(b"")
        self.assertIsNone(res)

    def test_evolution_config_persistence(self):
        test_url = "https://whatsapp-test.majmobilidade.com.br"
        test_key = "test_evolution_secret_key"
        ok = save_evolution_config(test_url, test_key)
        self.assertTrue(ok)

        cfg = get_evolution_config()
        self.assertEqual(cfg["api_url"], test_url)
        self.assertEqual(cfg["api_key"], test_key)

    def test_evolution_webhook_connection_update(self):
        # 1. Garantir linha de teste no banco
        test_instance = "vendedor_unittest"
        with db() as conn:
            conn.execute("DELETE FROM whatsapp_monitored_lines WHERE instance_name = %s", (test_instance,))
            conn.execute(
                """
                INSERT INTO whatsapp_monitored_lines (account_name, instance_name, instance_type, connection_status, is_monitored)
                VALUES ('Linha Teste Unitário', %s, 'evolution', 'connecting', FALSE)
                """,
                (test_instance,),
            )
            conn.commit()

        # 2. Disparar webhook CONNECTION_UPDATE
        payload = {
            "event": "connection.update",
            "instance": test_instance,
            "data": {
                "state": "open",
                "battery": 92
            }
        }
        res = self.client.post("/webhook/evolution", json=payload)
        self.assertEqual(res.status_code, 200)

        # 3. Validar atualização no banco
        with db() as conn:
            row = conn.execute(
                "SELECT connection_status, is_monitored, battery_level FROM whatsapp_monitored_lines WHERE instance_name = %s",
                (test_instance,)
            ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["connection_status"], "open")
            self.assertTrue(row["is_monitored"])
            self.assertEqual(row["battery_level"], 92)

    def test_evolution_webhook_messages_upsert_inbound(self):
        test_instance = "vendedor_unittest"
        test_phone = "5527999998888"
        test_wam_id = f"unit_test_msg_{test_phone}"

        # Disparar webhook MESSAGES_UPSERT (mensagem de cliente)
        payload = {
            "event": "messages.upsert",
            "instance": test_instance,
            "data": {
                "key": {
                    "remoteJid": f"{test_phone}@s.whatsapp.net",
                    "fromMe": False,
                    "id": test_wam_id
                },
                "pushName": "Cliente Teste Unitário",
                "messageType": "conversation",
                "message": {
                    "conversation": "Olá, tenho interesse na moto elétrica!"
                }
            }
        }
        res = self.client.post("/webhook/evolution", json=payload)
        self.assertEqual(res.status_code, 200)

        # Validar persistência em whatsapp_messages
        with db() as conn:
            msg = conn.execute(
                "SELECT * FROM whatsapp_messages WHERE wam_id = %s",
                (test_wam_id,)
            ).fetchone()
            self.assertIsNotNone(msg)
            self.assertEqual(msg["direction"], "inbound")
            self.assertIn("moto elétrica", msg["body"])

            # Validar criação do lead no CRM
            lead = conn.execute(
                "SELECT * FROM crm_leads WHERE phone = %s",
                (test_phone,)
            ).fetchone()
            self.assertIsNotNone(lead)
            self.assertEqual(lead["channel"], "whatsapp")

        # Limpeza pós-teste
        with db() as conn:
            conn.execute("DELETE FROM whatsapp_messages WHERE wam_id = %s", (test_wam_id,))
            conn.execute("DELETE FROM crm_leads WHERE phone = %s", (test_phone,))
            conn.execute("DELETE FROM whatsapp_monitored_lines WHERE instance_name = %s", (test_instance,))
            conn.commit()


if __name__ == "__main__":
    unittest.main()
