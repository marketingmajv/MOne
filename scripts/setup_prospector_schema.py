"""
M-One Setup Prospector Schema (scripts/setup_prospector_schema.py)
Cria o schema 'prospeccao', tabelas de leads e nichos, índices e pré-carrega
os nichos padrão da MAJ Mobilidade Elétrica.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from database import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DDL_SCRIPT = """
-- 1. Criação do Schema dedicado
CREATE SCHEMA IF NOT EXISTS prospeccao;

-- 2. Tabela de Nichos e Regras de Segmentação
CREATE TABLE IF NOT EXISTS prospeccao.nichos (
    id SERIAL PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,
    rotulo TEXT NOT NULL,
    termos JSONB NOT NULL DEFAULT '[]'::jsonb,
    pracas_sugeridas JSONB NOT NULL DEFAULT '[]'::jsonb,
    pesos JSONB NOT NULL DEFAULT '{}'::jsonb,
    requisitos JSONB NOT NULL DEFAULT '{}'::jsonb,
    aderencia JSONB NOT NULL DEFAULT '{}'::jsonb,
    gancho_comercial_padrao TEXT,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Tabela de Leads Qualificados Capturados
CREATE TABLE IF NOT EXISTS prospeccao.leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    google_id TEXT UNIQUE NOT NULL,

    -- Origem da busca
    nicho_slug TEXT NOT NULL,
    praca TEXT,
    termo_busca TEXT,

    -- Identidade Comercial (Google Maps)
    nome TEXT,
    nome_limpo TEXT,
    categoria TEXT,
    endereco TEXT,
    cidade TEXT,
    uf TEXT,
    cep TEXT,
    lat DOUBLE PRECISION,
    lng DOUBLE PRECISION,
    google_maps_url TEXT,
    avaliacao NUMERIC(2,1),
    total_avaliacoes INTEGER,
    telefone_google TEXT,

    -- Presença Digital & Contatos
    site TEXT,
    site_status INTEGER,
    site_vivo BOOLEAN DEFAULT FALSE,
    site_titulo TEXT,
    site_erro TEXT,
    whatsapp TEXT,
    telefones_site TEXT[] DEFAULT '{}',
    emails TEXT[] DEFAULT '{}',
    instagram TEXT,
    instagram_perfil JSONB,
    facebook TEXT,
    linkedin TEXT,

    -- Dados da Receita Federal (CNPJ)
    cnpj TEXT,
    razao_social TEXT,
    nome_fantasia TEXT,
    situacao_cnpj TEXT,
    porte TEXT,
    capital_social NUMERIC,
    cnae_principal TEXT,
    cnae_descricao TEXT,
    data_abertura DATE,
    socios JSONB DEFAULT '[]'::jsonb,
    decisor_nome TEXT,
    decisor_cargo TEXT,
    cnpj_dados JSONB,

    -- Inteligência Artificial (Raio-X & Scoring)
    resumo_ia TEXT,
    porte_estimado TEXT,
    servicos_detectados TEXT[] DEFAULT '{}',
    do_nicho BOOLEAN,
    motivo_aderencia TEXT,
    gancho_comercial TEXT,
    score INTEGER DEFAULT 0,
    classificacao TEXT DEFAULT 'D', -- A | B | C | D
    sinais_score JSONB DEFAULT '{}'::jsonb,

    -- Sincronização & Status Comercial
    status_contato TEXT NOT NULL DEFAULT 'novo', -- novo | contatado | em_negociacao | convertido | descartado
    sincronizado_sheets BOOLEAN DEFAULT FALSE,
    sincronizado_sheets_em TIMESTAMPTZ,
    notas_comerciais TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Índices Estratégicos
CREATE INDEX IF NOT EXISTS idx_prospeccao_leads_google_id ON prospeccao.leads(google_id);
CREATE INDEX IF NOT EXISTS idx_prospeccao_leads_nicho ON prospeccao.leads(nicho_slug);
CREATE INDEX IF NOT EXISTS idx_prospeccao_leads_classe ON prospeccao.leads(classificacao);
CREATE INDEX IF NOT EXISTS idx_prospeccao_leads_score ON prospeccao.leads(score DESC);
CREATE INDEX IF NOT EXISTS idx_prospeccao_leads_status ON prospeccao.leads(status_contato);
CREATE INDEX IF NOT EXISTS idx_prospeccao_leads_uf_cidade ON prospeccao.leads(uf, cidade);
CREATE INDEX IF NOT EXISTS idx_prospeccao_leads_sheets ON prospeccao.leads(sincronizado_sheets);

-- 5. Tabela de Configurações do Módulo
CREATE TABLE IF NOT EXISTS prospeccao.config (
    chave TEXT PRIMARY KEY,
    valor TEXT,
    descricao TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

DEFAULT_NICHOS = [
    {
        "slug": "revenda-motos",
        "rotulo": "Revendas de Motos e Scooters Multimarcas",
        "termos": [
            "loja de motos",
            "revenda de motos",
            "concessionaria de motos",
            "motos eletricas",
            "scooter eletrica",
            "veiculos eletricos multimarcas"
        ],
        "pracas_sugeridas": [
            "Vitoria ES",
            "Vila Velha ES",
            "Serra ES",
            "Belo Horizonte MG",
            "Rio de Janeiro RJ",
            "Sao Paulo SP",
            "Curitiba PR"
        ],
        "pesos": {
            "site_vivo": 20,
            "whatsapp": 20,
            "cnpj": 15,
            "instagram": 15,
            "email": 10,
            "telefone": 10,
            "reputacao": 10
        },
        "requisitos": {
            "avaliacoes_min": 10,
            "avaliacoes_max": 500,
            "exige_celular": True,
            "exige_site": False
        },
        "aderencia": {
            "confirma": ["moto", "scooter", "veiculo", "concessionaria", "multimarcas", "duas rodas", "eletrica"],
            "descarta_forte": ["autoescola", "despachante", "leilao", "desmanche", "borracharia"],
            "descarta": ["caminhao", "trator", "guincho", "seguradora"]
        },
        "gancho_comercial_padrao": "Distribuição oficial direta de fábrica MAJ Mobilidade: motos e scooters elétricas com margem atrativa para lojistas, pronta entrega e faturamento B2B."
    },
    {
        "slug": "bicicletarias",
        "rotulo": "Bicicletarias, E-Bikes e Mobilidade Leve",
        "termos": [
            "bicicletaria",
            "loja de bicicletas",
            "bike shop",
            "patinetes eletricos",
            "bicicletas eletricas",
            "e-bike"
        ],
        "pracas_sugeridas": [
            "Vitoria ES",
            "Vila Velha ES",
            "Belo Horizonte MG",
            "Campinas SP",
            "Sao Paulo SP",
            "Florianopolis SC"
        ],
        "pesos": {
            "site_vivo": 20,
            "whatsapp": 25,
            "cnpj": 15,
            "instagram": 15,
            "email": 10,
            "telefone": 10,
            "reputacao": 5
        },
        "requisitos": {
            "avaliacoes_min": 8,
            "avaliacoes_max": 400,
            "exige_celular": True,
            "exige_site": False
        },
        "aderencia": {
            "confirma": ["bike", "bicicleta", "ciclo", "patinete", "pedal", "e-bike", "mobilidade"],
            "descarta_forte": ["academia de spinning", "aluguel compartilhado", "estacionamento"],
            "descarta": ["infantil apenas", "brinquedos"]
        },
        "gancho_comercial_padrao": "Parceria de revenda para bicicletarias ampliarem faturamento com a linha de patinetes e e-bikes MAJ com garantia nacional e peças de reposição."
    },
    {
        "slug": "frotas-delivery",
        "rotulo": "Empresas de Delivery, Logística e Locadoras",
        "termos": [
            "empresa de delivery",
            "logistica express",
            "entregas rapidas",
            "locadora de motos",
            "aluguel de motos"
        ],
        "pracas_sugeridas": [
            "Vitoria ES",
            "Serra ES",
            "Belo Horizonte MG",
            "Sao Paulo SP",
            "Rio de Janeiro RJ"
        ],
        "pesos": {
            "site_vivo": 25,
            "cnpj": 25,
            "whatsapp": 20,
            "email": 10,
            "telefone": 10,
            "reputacao": 10
        },
        "requisitos": {
            "avaliacoes_min": 5,
            "avaliacoes_max": 600,
            "exige_celular": True,
            "exige_site": False
        },
        "aderencia": {
            "confirma": ["delivery", "entrega", "logistica", "motoboy", "frota", "locacao", "aluguel"],
            "descarta_forte": ["comida", "restaurante", "pizzaria", "hamburgueria"],
            "descarta": ["mudancas residenciais", "guincho"]
        },
        "gancho_comercial_padrao": "Eletrificação de frota de entregas MAJ: redução de até 80% nos custos de combustível e manutenção preventiva para operações urbanas."
    }
]


def setup_schema():
    print("⚡ [1/2] Criando schema 'prospeccao' e tabelas no Supabase...")
    with db() as conn:
        conn.executescript(DDL_SCRIPT)
        conn.commit()
    print("  ✓ Schema e tabelas criados com sucesso.")

    print("📊 [2/2] Inserindo nichos padrão de Mobilidade Elétrica MAJ...")
    with db() as conn:
        for n in DEFAULT_NICHOS:
            conn.execute(
                """
                INSERT INTO prospeccao.nichos (
                    slug, rotulo, termos, pracas_sugeridas, pesos, requisitos, aderencia, gancho_comercial_padrao, ativo
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                ON CONFLICT (slug) DO UPDATE SET
                    rotulo = EXCLUDED.rotulo,
                    termos = EXCLUDED.termos,
                    pracas_sugeridas = EXCLUDED.pracas_sugeridas,
                    pesos = EXCLUDED.pesos,
                    requisitos = EXCLUDED.requisitos,
                    aderencia = EXCLUDED.aderencia,
                    gancho_comercial_padrao = EXCLUDED.gancho_comercial_padrao,
                    updated_at = NOW();
                """,
                [
                    n["slug"],
                    n["rotulo"],
                    json.dumps(n["termos"]),
                    json.dumps(n["pracas_sugeridas"]),
                    json.dumps(n["pesos"]),
                    json.dumps(n["requisitos"]),
                    json.dumps(n["aderencia"]),
                    n["gancho_comercial_padrao"],
                ]
            )
        conn.commit()
    print("  ✓ Nichos MAJ configurados com sucesso!")


if __name__ == "__main__":
    setup_schema()
