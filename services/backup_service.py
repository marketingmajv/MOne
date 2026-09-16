"""
Serviço de Backup Físico Automático e Disaster Recovery — M-One (MAJ OS)
Gera pacotes completos (.zip) contendo:
  1. Dump PostgreSQL Supabase (.sql)
  2. Banco SQLite espelhado offline (m_one_offline.db)
  3. Relatórios auditáveis em CSV e JSON
  4. Script e manual autônomo de restauração de emergência
Espelha automaticamente para a pasta local e Google Drive para Desktop.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import os
import shutil
import sqlite3
import tempfile
import threading
import time
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import database

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
if os.environ.get("VERCEL"):
    LOCAL_BACKUP_DIR = Path("/tmp/backups")
else:
    LOCAL_BACKUP_DIR = BASE_DIR / "backups"

try:
    LOCAL_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    LOCAL_BACKUP_DIR = Path("/tmp/backups")
    LOCAL_BACKUP_DIR.mkdir(parents=True, exist_ok=True)

LAST_LOGIN_BACKUP_FILE = LOCAL_BACKUP_DIR / ".last_admin_backup_timestamp"
COOLDOWN_MINUTES = 30


def get_gdrive_sync_dir() -> Path | None:
    """Detecta a pasta de sincronização do Google Drive para Desktop no macOS."""
    custom_path = os.environ.get("GDRIVE_BACKUP_DIR")
    if custom_path:
        p = Path(custom_path).expanduser()
        if p.exists():
            return p

    cloud_storage = Path.home() / "Library" / "CloudStorage"
    if cloud_storage.exists():
        # 1. Prioriza conta corporativa oficial MAJ
        maj_drive = cloud_storage / "GoogleDrive-marketingmajv@gmail.com" / "Meu Drive"
        if maj_drive.exists():
            target = maj_drive / "M-One-Backups"
            target.mkdir(parents=True, exist_ok=True)
            return target

        # 2. Outras contas Google Drive encontradas no Mac
        for entry in cloud_storage.glob("GoogleDrive-*"):
            my_drive = entry / "Meu Drive"
            if my_drive.exists():
                target = my_drive / "M-One-Backups"
                target.mkdir(parents=True, exist_ok=True)
                return target

    legacy_drive = Path.home() / "Google Drive" / "M-One-Backups"
    if legacy_drive.parent.exists():
        legacy_drive.mkdir(parents=True, exist_ok=True)
        return legacy_drive

    return None


def get_public_tables(conn) -> list[str]:
    """Retorna todas as tabelas públicas do banco de dados atual."""
    try:
        cur = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name"
        )
        return [r["table_name"] for r in cur.fetchall()]
    except Exception:
        # Fallback para SQLite se estiver rodando local
        try:
            cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            return [r["name"] for r in cur.fetchall()]
        except Exception as e:
            logger.error("Erro ao listar tabelas: %s", e)
            return []


def sql_quote(val) -> str:
    """Formata valor para instrução SQL INSERT segura."""
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, (datetime,)):
        return f"'{val.isoformat()}'"
    val_str = str(val).replace("'", "''")
    return f"'{val_str}'"


def generate_backup_package(triggered_by: str = "manual") -> dict:
    """
    Extrai todos os dados do banco e monta o pacote completo de contingência (.zip).
    Retorna metadados do backup gerado.
    """
    timestamp = datetime.now()
    timestamp_str = timestamp.strftime("%Y-%m-%d_%H-%M-%S")
    backup_filename = f"mone_backup_{timestamp_str}.zip"
    final_local_path = LOCAL_BACKUP_DIR / backup_filename

    logger.info("Iniciando geração de backup físico (%s)...", triggered_by)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        package_root = tmp_path / f"mone_backup_{timestamp_str}"
        package_root.mkdir()

        csv_dir = package_root / "exports_csv"
        csv_dir.mkdir()
        json_dir = package_root / "exports_json"
        json_dir.mkdir()

        total_records = 0
        tables_data: dict[str, list[dict]] = {}

        # 1. Extração de dados da fonte única da verdade
        with database.db() as conn:
            tables = get_public_tables(conn)

            # Dump SQL estruturado
            dump_sql_path = package_root / "dump_supabase_postgres.sql"
            with open(dump_sql_path, "w", encoding="utf-8") as sql_file:
                sql_file.write(f"-- ==========================================================\n")
                sql_file.write(f"-- M-ONE OPERATING SYSTEM — DUMP DE CONTINGÊNCIA SUPABASE\n")
                sql_file.write(f"-- Gerado em: {timestamp.strftime('%d/%m/%Y %H:%M:%S')}\n")
                sql_file.write(f"-- Gatilho: {triggered_by}\n")
                sql_file.write(f"-- ==========================================================\n\n")
                sql_file.write("BEGIN;\n\n")

                for table in tables:
                    try:
                        cur = conn.execute(f'SELECT * FROM "{table}"')
                        rows = cur.fetchall() or []
                        table_rows = [dict(r) for r in rows]
                        tables_data[table] = table_rows
                        total_records += len(table_rows)

                        # CSV
                        if table_rows:
                            csv_file_path = csv_dir / f"{table}.csv"
                            with open(csv_file_path, "w", newline="", encoding="utf-8-sig") as cf:
                                writer = csv.DictWriter(cf, fieldnames=list(table_rows[0].keys()))
                                writer.writeheader()
                                writer.writerows(table_rows)

                        # SQL Inserts
                        sql_file.write(f"-- Tabela: {table} ({len(table_rows)} registros)\n")
                        for r in table_rows:
                            cols = [f'"{c}"' for c in r.keys()]
                            vals = [sql_quote(v) for v in r.values()]
                            sql_file.write(f'INSERT INTO "{table}" ({", ".join(cols)}) VALUES ({", ".join(vals)}) ON CONFLICT DO NOTHING;\n')
                        sql_file.write("\n")
                    except Exception as e:
                        logger.warning("Falha ao exportar tabela %s: %s", table, e)

                sql_file.write("COMMIT;\n")

        # 2. Dump em JSON completo
        json_file_path = json_dir / "database_snapshot.json"
        with open(json_file_path, "w", encoding="utf-8") as jf:
            json.dump(tables_data, jf, default=str, indent=2, ensure_ascii=False)

        # 3. Banco SQLite Offline Espelhado (m_one_offline.db)
        sqlite_offline_path = package_root / "m_one_offline.db"
        sqlite_conn = sqlite3.connect(sqlite_offline_path)
        sqlite_conn.row_factory = sqlite3.Row

        # Inicializa tabelas no SQLite
        for table, rows in tables_data.items():
            if not rows:
                continue
            cols = list(rows[0].keys())
            cols_def = ", ".join([f'"{c}" TEXT' for c in cols])
            sqlite_conn.execute(f'CREATE TABLE IF NOT EXISTS "{table}" ({cols_def})')
            placeholders = ", ".join(["?"] * len(cols))
            for r in rows:
                vals = [str(v) if v is not None else None for v in r.values()]
                sqlite_conn.execute(f'INSERT INTO "{table}" VALUES ({placeholders})', vals)
        sqlite_conn.commit()
        sqlite_conn.close()

        # 4. Manual de Restauração em caso de pane
        manual_path = package_root / "MANUAL_DE_RESTAURACAO.md"
        with open(manual_path, "w", encoding="utf-8") as mf:
            mf.write(f"""# Manual de Restauração de Emergência — M-One (MAJ OS)

**Data do Backup:** {timestamp.strftime('%d/%m/%Y %H:%M:%S')}
**Total de Registros:** {total_records} registros em {len(tables_data)} tabelas

## Cenário A: Pane no Supabase (Rodar M-One 100% Offline)
1. Copie o arquivo `m_one_offline.db` deste pacote para a raiz do M-One com o nome `m_one.db`.
2. No terminal do Mac Studio, inicie o servidor forçando o banco local:
   ```bash
   USE_LOCAL_DB=1 PORT=5001 .venv/bin/python3 app.py
   ```
3. O sistema funcionará localmente sem depender de internet nem da nuvem.

## Cenário B: Restauração Completa no PostgreSQL / Supabase
1. Conecte ao banco do Supabase via terminal:
   ```bash
   psql "postgresql://postgres...pooler.supabase.com:6543/postgres?sslmode=require" < dump_supabase_postgres.sql
   ```
2. Todos os dados serão reinseridos mantendo a integridade.

## Cenário C: Consulta Rápida das Planilhas
* Acesse a pasta `exports_csv/` para abrir qualquer tabela diretamente no Excel ou Numbers.
""")

        # 5. Compactar Pacote Final .zip
        shutil.make_archive(str(package_root), "zip", root_dir=tmp_path, base_dir=f"mone_backup_{timestamp_str}")

        # Mover para pasta local definitiva
        generated_zip = tmp_path / f"mone_backup_{timestamp_str}.zip"
        shutil.move(str(generated_zip), str(final_local_path))

    # 6. Sincronização automática para o Google Drive Desktop (caso instalado no Mac Studio)
    gdrive_dir = get_gdrive_sync_dir()
    gdrive_synced = False
    gdrive_target_file = None
    if gdrive_dir and gdrive_dir.exists():
        try:
            gdrive_target_file = gdrive_dir / backup_filename
            shutil.copy2(str(final_local_path), str(gdrive_target_file))
            gdrive_synced = True
            logger.info("Backup sincronizado no Google Drive Desktop: %s", gdrive_target_file)
        except Exception as ex:
            logger.warning("Falha ao copiar backup para Google Drive Desktop: %s", ex)

    # 7. Housekeeping / Rotação de backups antigos (30 dias)
    rotate_old_backups(LOCAL_BACKUP_DIR, keep_days=30)
    if gdrive_dir and gdrive_dir.exists():
        rotate_old_backups(gdrive_dir, keep_days=30)

    # 8. Registrar na trilha de auditoria
    dest_str = ["Mac Studio (Local)"]
    if gdrive_synced:
        dest_str.append("Google Drive Desktop")

    try:
        with database.db() as conn:
            conn.execute(
                "INSERT INTO audit_log (action, user_name, detail, created_at) VALUES (%s, %s, %s, %s)",
                (
                    "backup.generated",
                    triggered_by,
                    f"Backup {backup_filename} gerado com {total_records} registros. Armazenado em: {', '.join(dest_str)}",
                    datetime.now()
                )
            )
    except Exception:
        pass

    size_mb = round(final_local_path.stat().st_size / (1024 * 1024), 2)
    return {
        "success": True,
        "filename": backup_filename,
        "local_path": str(final_local_path),
        "gdrive_synced": gdrive_synced,
        "gdrive_path": str(gdrive_target_file) if gdrive_target_file else None,
        "timestamp": timestamp.isoformat(),
        "total_records": total_records,
        "size_mb": size_mb,
        "triggered_by": triggered_by
    }


def rotate_old_backups(directory: Path, keep_days: int = 30):
    """Remove backups locais com mais de keep_days dias para liberar espaço."""
    if not directory.exists():
        return
    cutoff = datetime.now() - timedelta(days=keep_days)
    for f in directory.glob("mone_backup_*.zip"):
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime < cutoff:
                f.unlink()
                logger.info("Backup expirado removido pela rotação: %s", f.name)
        except Exception as e:
            logger.debug("Erro ao rotacionar backup %s: %s", f, e)


def trigger_admin_login_backup(admin_username: str):
    """Dispara o backup em segundo plano no login do admin, respeitando o cooldown."""
    now = datetime.now()
    if LAST_LOGIN_BACKUP_FILE.exists():
        try:
            last_time_str = LAST_LOGIN_BACKUP_FILE.read_text(encoding="utf-8").strip()
            last_time = datetime.fromisoformat(last_time_str)
            if now - last_time < timedelta(minutes=COOLDOWN_MINUTES):
                logger.debug("Backup em login ignorado por cooldown (%s min)", COOLDOWN_MINUTES)
                return
        except Exception:
            pass

    # Atualiza timestamp do cooldown
    try:
        LAST_LOGIN_BACKUP_FILE.write_text(now.isoformat(), encoding="utf-8")
    except Exception:
        pass

    # Dispara thread assíncrona
    t = threading.Thread(
        target=generate_backup_package,
        args=(f"admin_login:{admin_username}",),
        daemon=True
    )
    t.start()


def list_backups() -> list[dict]:
    """Lista todos os backups disponíveis ordenados pelo mais recente."""
    backups = []
    for f in LOCAL_BACKUP_DIR.glob("mone_backup_*.zip"):
        try:
            stat = f.stat()
            size_mb = round(stat.st_size / (1024 * 1024), 2)
            created_at = datetime.fromtimestamp(stat.st_mtime)
            backups.append({
                "filename": f.name,
                "path": str(f),
                "size_mb": size_mb,
                "created_at": created_at.strftime("%d/%m/%Y %H:%M:%S"),
                "timestamp": created_at.isoformat()
            })
        except Exception:
            continue

    backups.sort(key=lambda x: x["timestamp"], reverse=True)
    return backups


def get_backup_summary() -> dict:
    """Retorna o resumo executivo para o painel de backups."""
    backups = list_backups()
    gdrive_dir = get_gdrive_sync_dir()
    total_size_mb = round(sum(b["size_mb"] for b in backups), 2)

    return {
        "total_backups": len(backups),
        "total_size_mb": total_size_mb,
        "last_backup": backups[0] if backups else None,
        "gdrive_connected": gdrive_dir is not None and gdrive_dir.exists(),
        "gdrive_path": str(gdrive_dir) if gdrive_dir else None,
        "backups": backups[:15]
    }

