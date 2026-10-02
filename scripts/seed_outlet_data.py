"""
Script para sincronizar e semear os produtos do Outlet MAJ no banco de dados
com base no CSV oficial (uploads/outlet/tabela_precos_outlet.csv) e fotos locais.
"""

from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path

from services.outlet_service import (
    ensure_outlet_schema,
    parse_currency,
    run_exec,
    save_outlet_item,
    set_outlet_setting,
    slugify,
)
from database import db

BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = BASE_DIR / "uploads" / "outlet" / "tabela_precos_outlet.csv"
ENSAIO_DIR = BASE_DIR / "static" / "img" / "outlet"

MODEL_SPECS = {
    "MAX 12": {
        "category": "Scooter Elétrica",
        "description": "A scooter elétrica mais vendida e amada do Brasil. Design clássico, excelente estabilidade, iluminação full LED e potência de sobra para o dia a dia.",
        "specs": {
            "Motor": "1200W High Torque",
            "Velocidade Máxima": "Até 45 km/h",
            "Autonomia": "Até 45 km por recarga",
            "Bateria": "Lítio 60V removível",
            "Carga Máxima": "160 kg",
            "Freios": "Disco hidráulico dianteiro e traseiro"
        },
        "badge": "MAIS VENDIDO",
        "folder_aliases": ["MAX 12 MAJ", "MAX 12", "MAX12"]
    },
    "X15 PRO": {
        "category": "Scooter Elétrica",
        "description": "Linhas esportivas arrojadas e suspensão reforçada com duplo amortecedor. Ideal para quem busca performance e presença marcante.",
        "specs": {
            "Motor": "1500W Brushless",
            "Velocidade Máxima": "Até 50 km/h",
            "Autonomia": "Até 50 km",
            "Bateria": "Lítio 60V 20Ah",
            "Freios": "Disco duplo hidráulico",
            "Painel": "Display Digital Colorido"
        },
        "badge": "ALTA PERFORMANCE",
        "folder_aliases": ["MAJ X15 PRO", "X15 PRO", "X15"]
    },
    "Sport 701 short": {
        "category": "Scooter Elétrica",
        "description": "Design esportivo 'short wheelbase' exclusivo, aceleração rápida e manobrabilidade impecável no trânsito urbano.",
        "specs": {
            "Motor": "1500W",
            "Velocidade Máxima": "Até 50 km/h",
            "Autonomia": "Até 45 km",
            "Bateria": "Lítio 60V",
            "Suspensão": "Invertida esportiva"
        },
        "badge": "EDIÇÃO LIMITADA",
        "folder_aliases": ["SPORT 701 SHORT", "701 SHORT"]
    },
    "V20 ULTRA": {
        "category": "Bicicleta Elétrica Fat Tire",
        "description": "A rainha das e-bikes fat tire. Pneus largos 20x4.0 que encaram asfalto, areia ou trilha com conforto absoluto e muito estilo.",
        "specs": {
            "Motor": "750W Peak 1000W",
            "Velocidade Máxima": "Até 45 km/h",
            "Autonomia": "Até 65 km no pedal assistido",
            "Bateria": "48V 15Ah Removível com chave",
            "Pneus": "Fat Tire 20x4.0 todo terreno",
            "Câmbio": "Shimano 7 velocidades"
        },
        "badge": "MAIOR ESTOQUE",
        "folder_aliases": ["BIKE ELÉTRICA - V20 ULTRA", "V20 ULTRA", "V20"]
    },
    "M9 PRO": {
        "category": "Bicicleta Elétrica",
        "description": "Visual retrô café racer autêntico com acabamento de banco premium em couro e quadro robusto. Condução macia e silenciosa.",
        "specs": {
            "Motor": "750W",
            "Velocidade Máxima": "Até 42 km/h",
            "Autonomia": "Até 55 km",
            "Bateria": "48V Lítio",
            "Farol": "Farol redondo vintage LED",
            "Assento": "Estofado Premium Confort"
        },
        "badge": "OFERTA DESTAQUE",
        "folder_aliases": ["BIKE ELÉTRICA - M9 PRO", "M9 PRO", "M9"]
    },
    "V80 PRO": {
        "category": "Bicicleta Elétrica",
        "description": "Versatilidade e robustez para todos os trajetos com design moderno e geometria ergonômica.",
        "specs": {
            "Motor": "750W",
            "Velocidade Máxima": "Até 40 km/h",
            "Autonomia": "Até 50 km",
            "Bateria": "48V Lítio",
            "Freios": "Disco mecânico/hidráulico"
        },
        "badge": "QUEIMA DE ESTOQUE",
        "folder_aliases": ["BIKE ELÉTRICA - V8 ULTRA MINI", "V80 PRO", "V80"]
    },
    "M50 PRO": {
        "category": "Bicicleta Elétrica",
        "description": "Quadro reforçado, motor potente e excelente autonomia para o deslocamento diário sem esforço.",
        "specs": {
            "Motor": "750W",
            "Velocidade Máxima": "Até 42 km/h",
            "Autonomia": "Até 50 km",
            "Bateria": "48V Lítio",
            "Quadro": "Alumínio aeroespacial"
        },
        "badge": "ÚLTIMAS UNIDADES",
        "folder_aliases": ["BIKE ELÉTRICA - M50 PRO", "M50 PRO", "M50"]
    },
    "RIDE ON": {
        "category": "Scooter / Mini Elétrica",
        "description": "Praticidade pura e diversão em duas rodas com cores vibrantes. Leve, econômica e perfeita para o transporte diário ágil.",
        "specs": {
            "Motor": "800W",
            "Velocidade Máxima": "Até 35 km/h",
            "Autonomia": "Até 40 km",
            "Bateria": "Lítio 48V/60V",
            "Peso": "Ultra leve e fácil de manobrar"
        },
        "badge": "PREÇO IMBATÍVEL",
        "folder_aliases": ["RIDE ON", "RIDEON"]
    },
    "NOVA": {
        "category": "Scooter Elétrica",
        "description": "A combinação perfeita entre tecnologia e elegância urbana. Visual refinado em Silver Black e pilotagem suave.",
        "specs": {
            "Motor": "1000W Brushless",
            "Velocidade Máxima": "Até 45 km/h",
            "Autonomia": "Até 45 km",
            "Bateria": "60V Lítio",
            "Alarme": "Partida sem chave e alarme integrado"
        },
        "badge": "DESIGN MODERNO",
        "folder_aliases": ["NOVA"]
    },
    "FLOW ONE": {
        "category": "Scooter Elétrica",
        "description": "Design europeu contemporâneo com curvas elegantes, paleta de cores exclusivas e conforto superior para dois ocupantes.",
        "specs": {
            "Motor": "1200W",
            "Velocidade Máxima": "Até 45 km/h",
            "Autonomia": "Até 50 km",
            "Bateria": "60V Lítio",
            "Porta-objetos": "Espaçoso porta-capacete"
        },
        "badge": "CORES EXCLUSIVAS",
        "folder_aliases": ["FLOW ONE", "FLOW"]
    },
    "CLASSIC 1000": {
        "category": "Scooter Elétrica Retrô",
        "description": "Charme clássico atemporal que remete às icônicas scooters italianas, agora 100% elétrica e ecológica.",
        "specs": {
            "Motor": "1000W Silencioso",
            "Velocidade Máxima": "Até 40 km/h",
            "Autonomia": "Até 45 km",
            "Bateria": "60V Lítio",
            "Estilo": "Retrô com retrovisores e para-lamas vintage"
        },
        "badge": "ESTILO RETRÔ",
        "folder_aliases": ["CLASSIC 1000", "CLASSIC"]
    },
    "DB-ZERO": {
        "category": "Scooter Elétrica",
        "description": "Linhas futuristas em Silver Black, peso reduzido e excelente resposta de torque instantâneo.",
        "specs": {
            "Motor": "1000W",
            "Velocidade Máxima": "Até 42 km/h",
            "Autonomia": "Até 40 km",
            "Bateria": "60V Lítio"
        },
        "badge": "FUTURISTA",
        "folder_aliases": ["DB ZERO", "DB-ZERO", "DBZERO"]
    },
    "RZ-110": {
        "category": "Scooter Elétrica",
        "description": "Agilidade e economia para o trânsito da cidade, com ótima aceleração e faróis ultra potentes.",
        "specs": {
            "Motor": "1000W",
            "Velocidade Máxima": "Até 45 km/h",
            "Autonomia": "Até 40 km",
            "Bateria": "60V Lítio"
        },
        "badge": "ÁGIL E PRÁTICA",
        "folder_aliases": ["RZ110", "RZ-110"]
    },
    "VITTORIA": {
        "category": "Scooter Elétrica Clássica",
        "description": "Elegância pura em acabamento branco perolizado. Um toque de classe para quem quer se locomover com sofisticação.",
        "specs": {
            "Motor": "1200W",
            "Velocidade Máxima": "Até 45 km/h",
            "Autonomia": "Até 45 km",
            "Bateria": "60V Lítio"
        },
        "badge": "PEÇA ÚNICA",
        "folder_aliases": ["VITTORIA"]
    },
    "V8 MINI": {
        "category": "Bicicleta Elétrica Compacta",
        "description": "A compacta favorita com rodas fat tire em proporção reduzida. Super divertida, prática de guardar e fácil de pilotar.",
        "specs": {
            "Motor": "500W Peak 750W",
            "Velocidade Máxima": "Até 35 km/h",
            "Autonomia": "Até 40 km",
            "Bateria": "48V Lítio",
            "Diferencial": "Quadro baixo ergonômico"
        },
        "badge": "MENOR PREÇO",
        "folder_aliases": ["BIKE ELÉTRICA - V8 ULTRA MINI", "V8 MINI"]
    },
    "Q8": {
        "category": "Bicicleta Elétrica",
        "description": "Quadro step-through rebaixado que facilita a montagem, ideal para passeios e mobilidade sem complicações.",
        "specs": {
            "Motor": "500W",
            "Velocidade Máxima": "Até 32 km/h",
            "Autonomia": "Até 45 km",
            "Bateria": "36V/48V Lítio"
        },
        "badge": "CONFORTO MÁXIMO",
        "folder_aliases": ["BIKE ELÉTRICA - Q8", "Q8"]
    },
    "MANTIS": {
        "category": "Scooter Elétrica",
        "description": "Chassi reforçado, design diferenciado e suspensão firme para resposta rápida e esportiva.",
        "specs": {
            "Motor": "1200W",
            "Velocidade Máxima": "Até 48 km/h",
            "Autonomia": "Até 45 km",
            "Bateria": "60V Lítio"
        },
        "badge": "ÚNICA UNIDADE",
        "folder_aliases": ["BIKE ELÉTRICA - MANTIS", "MANTIS"]
    },
    "JM 125": {
        "category": "Moto Elétrica",
        "description": "A gigante do outlet! Potência equivalente a uma moto 125cc a combustão, painel digital premium e máxima robustez.",
        "specs": {
            "Motor": "3000W High Output",
            "Velocidade Máxima": "Até 75 km/h",
            "Autonomia": "Até 70 km",
            "Bateria": "72V Alta Capacidade",
            "Freios": "Freios a disco duplo com CBS",
            "Homologação": "Painel digital completo e partida remota"
        },
        "badge": "POTÊNCIA TOTAL",
        "folder_aliases": ["JM 125", "JM125"]
    }
}


def find_photos_for_model(model_name: str) -> list[str]:
    """Procura fotos disponíveis em static/img/outlet para o modelo."""
    specs_info = MODEL_SPECS.get(model_name, {})
    aliases = specs_info.get("folder_aliases", [model_name])
    
    found_images = []
    
    # 1. Procurar nas subpastas do ENSAIO
    for root, dirs, files in os.walk(ENSAIO_DIR):
        root_name = Path(root).name
        # Verificar se o nome da pasta corresponde a algum alias
        matches_alias = any(alias.lower() in root_name.lower() or root_name.lower() in alias.lower() for alias in aliases)
        if matches_alias:
            for f in sorted(files):
                if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    # Relativo a static/
                    full_p = Path(root) / f
                    rel_p = os.path.relpath(full_p, BASE_DIR / "static")
                    found_images.append(f"/static/{rel_p}")
                    
    # 2. Se não achou na pasta específica, procurar arquivos que contenham o nome no próprio nome do arquivo
    if not found_images:
        for root, dirs, files in os.walk(ENSAIO_DIR):
            for f in sorted(files):
                if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    for alias in aliases:
                        if alias.lower() in f.lower():
                            full_p = Path(root) / f
                            rel_p = os.path.relpath(full_p, BASE_DIR / "static")
                            found_images.append(f"/static/{rel_p}")
                            break

    # Priorizar fotos limpas ou com 'Fundo Verde' / '01.jpg'
    def sort_key(img_url: str):
        u = img_url.lower()
        if "01.jpg" in u or "01.png" in u: return 0
        if "fundo verde" in u: return 1
        if "02.jpg" in u or "02.png" in u: return 2
        return 3

    found_images.sort(key=sort_key)
    return found_images


def seed_outlet():
    ensure_outlet_schema()
    
    # Configurações padrão
    set_outlet_setting("whatsapp_number", "5527999999999")
    set_outlet_setting("whatsapp_message", "Olá! Gostei do {model} no Outlet MAJ Mobilidade por {price} e quero aproveitar a promoção. Ainda está disponível?")
    set_outlet_setting("outlet_title", "OUTLET MAJ MOBILIDADE")
    set_outlet_setting("outlet_subtitle", "Queima de Estoque Oficial • Mais de 440 Veículos Elétricos com Descontos Exclusivos")
    set_outlet_setting("outlet_urgency_text", "ÚLTIMAS UNIDADES A PRONTA ENTREGA • PARCELAMENTO EM ATÉ 18X")

    if not CSV_PATH.exists():
        print(f"CSV não encontrado em {CSV_PATH}")
        return

    # Agregar linhas por modelo
    model_groups = {}
    with open(CSV_PATH, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_name = (row.get("Correspondência tabela") or "").strip()
            if not raw_name:
                continue
            
            qty = int(row.get("Qtd. Disponível") or 0)
            price_out = parse_currency(row.get("Preço promoção"))
            p12 = parse_currency(row.get("Promoção 12x (parcela R$)"))
            p18 = parse_currency(row.get("Promoção 18x (parcela R$)"))
            cond = (row.get("Condição") or "Na caixa").strip()
            color = (row.get("Cor / Banco") or "").strip()
            obs = (row.get("Observação") or "").strip()
            loc = (row.get("Localização") or "GALPÃO MAJ NOVO").strip()

            if raw_name not in model_groups:
                model_groups[raw_name] = {
                    "name": raw_name,
                    "total_qty": 0,
                    "min_price": price_out,
                    "max_price": price_out,
                    "installment_12": p12,
                    "installment_18": p18,
                    "conditions": set(),
                    "colors": set(),
                    "locations": set(),
                    "observations": set(),
                }
            
            grp = model_groups[raw_name]
            grp["total_qty"] += qty
            if price_out > 0:
                if grp["min_price"] == 0 or price_out < grp["min_price"]:
                    grp["min_price"] = price_out
                    grp["installment_12"] = p12
                    grp["installment_18"] = p18
                if price_out > grp["max_price"]:
                    grp["max_price"] = price_out
            if cond:
                grp["conditions"].add(cond)
            if color:
                grp["colors"].add(color)
            if loc:
                grp["locations"].add(loc)
            if obs:
                grp["observations"].add(obs)

    # Inserir ou atualizar na base de dados
    order = 1
    for model_name, grp in sorted(model_groups.items(), key=lambda x: x[1]["total_qty"], reverse=True):
        specs_data = MODEL_SPECS.get(model_name, {})
        category = specs_data.get("category", "Mobilidade Elétrica")
        desc = specs_data.get("description", f"Veículo elétrico MAJ {model_name} de alta qualidade.")
        specs = specs_data.get("specs", {})
        badge = specs_data.get("badge", "OFERTA OUTLET")

        # Preço original estimado (cerca de 20-30% acima para dar valor real de De/Por)
        price_out = grp["min_price"]
        price_orig = round(price_out * 1.25, 2)
        
        # Procurar fotos
        photos = find_photos_for_model(model_name)
        main_img = photos[0] if photos else "/static/logo.png"
        gallery = photos[1:10] if len(photos) > 1 else []

        colors_list = sorted(list(grp["colors"]))
        colors_str = ", ".join(colors_list) if colors_list else "Conforme lote"
        conditions_str = ", ".join(sorted(list(grp["conditions"])))

        item_dict = {
            "slug": slugify(model_name),
            "name": model_name,
            "category": category,
            "condition": conditions_str,
            "color": colors_str,
            "price_original": price_orig,
            "price_outlet": price_out,
            "installment_12": grp["installment_12"],
            "installment_18": grp["installment_18"],
            "installments_text": f"12x de R$ {grp['installment_12']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            "stock_qty": grp["total_qty"],
            "location": ", ".join(grp["locations"]),
            "badge": badge,
            "specs_json": specs,
            "description": desc,
            "image_main": main_img,
            "images_gallery": gallery,
            "status": "active" if grp["total_qty"] > 0 else "sold_out",
            "sort_order": order,
            "notes": f"Lote promocional. Cores: {colors_str}. Observações: {'; '.join(grp['observations'])}"
        }

        # Checar se já existe pelo slug
        existing = None
        with db() as conn:
            existing = run_exec(conn, "SELECT id FROM outlet_items WHERE slug = ?", (item_dict["slug"],)).fetchone()
        
        if existing:
            item_id = existing["id"] if isinstance(existing, dict) else existing[0]
            save_outlet_item(item_dict, item_id=item_id)
            print(f"Atualizado: {model_name} (ID {item_id}) | Fotos: {len(photos)}")
        else:
            nid = save_outlet_item(item_dict)
            print(f"Inserido: {model_name} (ID {nid}) | Fotos: {len(photos)}")
        order += 1

    print("\nSemeadura do Outlet MAJ concluída com sucesso!")


if __name__ == "__main__":
    seed_outlet()
