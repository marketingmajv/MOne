"""
M-One Freight Calculation Helpers (services/freight_calc_helpers.py)
Motor auxiliar de detecção inteligente de praça (Capital, Reg. Metropolitana, Interior),
variantes de faixa por UF e filtragem de transportadoras selecionadas.
Extraído de freight_service.py para conformidade Anti-Monólito (< 500 linhas).
"""

from __future__ import annotations

import unicodedata


STATE_CAPITALS = {
    "AC": "rio branco",
    "AL": "maceio",
    "AM": "manaus",
    "AP": "macapa",
    "BA": "salvador",
    "CE": "fortaleza",
    "DF": "brasilia",
    "ES": "vitoria",
    "GO": "goiania",
    "MA": "sao luis",
    "MG": "belo horizonte",
    "MS": "campo grande",
    "MT": "cuiaba",
    "PA": "belem",
    "PB": "joao pessoa",
    "PE": "recife",
    "PI": "teresina",
    "PR": "curitiba",
    "RJ": "rio de janeiro",
    "RN": "natal",
    "RO": "porto velho",
    "RR": "boa vista",
    "RS": "porto alegre",
    "SC": "florianopolis",
    "SE": "aracaju",
    "SP": "sao paulo",
    "TO": "palmas",
}

METRO_CITIES = {
    "ES": {
        "vila velha", "serra", "cariacica", "viana", "guarapari", "fundao",
    },
    "SP": {
        "guarulhos", "osasco", "santo andre", "sao bernardo do campo",
        "sao caetano do sul", "diadema", "maua", "barueri", "cotia",
        "taboao da serra", "suzano", "itaquaquecetuba", "mogi das cruzes",
    },
    "RJ": {
        "niteroi", "duque de caxias", "nova iguacu", "sao goncalo",
        "belford roxo", "sao joao de meriti", "nilopolis", "mesquita",
    },
    "MG": {
        "contagem", "betim", "nova lima", "ribeirao das neves",
        "santa luzia", "sabara", "ibirite", "vespasiano", "lagoa santa",
    },
    "PR": {
        "sao jose dos pinhais", "colombo", "araucaria", "pinhais",
        "campo largo", "fazenda rio grande", "almirante tamandare",
    },
    "SC": {
        "sao jose", "palhoca", "biguacu", "santo amaro da imperatriz",
    },
    "RS": {
        "canoas", "novo hamburgo", "sao leopoldo", "gravatai",
        "viamao", "alvorada", "cachoeirinha", "esteio", "guaiba",
    },
    "GO": {
        "aparecida de goiania", "senador canedo", "trindade", "goianira",
    },
    "BA": {
        "camacari", "lauro de freitas", "simoes filho", "candeias",
    },
    "PE": {
        "jaboatao dos guararapes", "olinda", "paulista", "cabo de santo agostinho",
    },
    "CE": {
        "caucaia", "maracanau", "eusebio", "aquiraz",
    },
}


def norm_text(val: str | None) -> str:
    """Remove acentos e normaliza para comparação case-insensitive."""
    if not val:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(val).strip().lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def classify_dest_zone(uf: str, city: str) -> str:
    """Classifica a cidade de destino em 'capital', 'metro' ou 'interior'."""
    uf_up = (uf or "").upper().strip()
    c_norm = norm_text(city)
    if not c_norm:
        return "capital"
    if STATE_CAPITALS.get(uf_up) == c_norm:
        return "capital"
    if c_norm in METRO_CITIES.get(uf_up, set()):
        return "metro"
    return "interior"


def score_rate_for_destination(rate_city: str, uf_dest: str, city_dest: str, has_cep_match: bool) -> int:
    """
    Pontua o quão bem a praça/região da linha da tabela (`rate_city`) casa com `city_dest`.
    Maior pontuação = melhor encaixe automático.
    """
    if has_cep_match:
        return 100

    rc = norm_text(rate_city)
    cd = norm_text(city_dest)
    zone = classify_dest_zone(uf_dest, city_dest)

    if not rc:
        return 40

    # 1. Casamento direto do nome da cidade/polo (ex: "cachoeiro", "colatina", "campinas", "juiz de fora")
    if cd and len(cd) >= 4:
        base_polo = rc.split("(")[0].strip()
        if cd == rc or (base_polo and len(base_polo) >= 4 and (cd in base_polo or base_polo in cd)):
            if "capital" in rc or "polo" in rc:
                return 95
            if "metro" in rc:
                return 90
            return 88

    # 2. Casamento por zona (Capital vs Reg. Metropolitana vs Interior)
    if zone == "capital":
        cap_name = STATE_CAPITALS.get((uf_dest or "").upper(), "")
        if cap_name and cap_name in rc and ("capital" in rc or "polo" in rc):
            return 92
        if rc in ("capital", "capital/polo", "capital e metropolitana"):
            return 90
        if "capital" in rc:
            return 82
        if "metro" in rc:
            return 60
        return 20

    if zone == "metro":
        cap_name = STATE_CAPITALS.get((uf_dest or "").upper(), "")
        if cap_name and cap_name in rc and "metro" in rc:
            return 92
        if "metro" in rc:
            return 90
        if "interior i" in rc and "interior ii" not in rc:
            return 80
        if "capital" in rc:
            return 65
        return 40

    # zone == "interior"
    if rc in ("interior", "interior i", "interior ii"):
        return 86 if rc != "interior ii" else 84
    if "interior" in rc:
        cap_name = STATE_CAPITALS.get((uf_dest or "").upper(), "")
        if cap_name and cap_name in rc:
            return 82
        return 78
    if "metro" in rc:
        return 45
    if "capital" in rc:
        return 25
    return 50


def evaluate_carrier_rates(
    all_rates: list,
    clean_cep_fn,
    format_cep_fn,
    clean_dest: str,
    uf_dest: str,
    city_dest: str,
    total_weight: float,
    total_volume_m3: float,
    total_insurance_value: float,
    selected_carrier_ids: list[int] | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Avalia todas as tarifas ativas, agrupa variantes por transportadora (Capital/Metro/Interior)
    e seleciona automaticamente a melhor faixa para a cidade do CEP, preservando `rate_variants`
    para troca manual pelo vendedor no card.
    """
    dest_int = int(clean_dest)
    allowed_set = set(int(x) for x in selected_carrier_ids if str(x).isdigit()) if selected_carrier_ids else None

    active_carriers = {}
    carrier_rates_map = {}
    carrier_variants_map = {}

    for r_raw in all_rates:
        r = dict(r_raw) if hasattr(r_raw, "keys") else r_raw
        c_id = int(r["carrier_id"])
        c_name = r["carrier_name"]
        t_name = r.get("table_name") or ""

        if c_id not in active_carriers:
            active_carriers[c_id] = {"id": c_id, "name": c_name, "table_name": t_name}
            carrier_rates_map[c_id] = []
            carrier_variants_map[c_id] = []

        if allowed_set and c_id not in allowed_set:
            continue

        carrier_rates_map[c_id].append(r)

        r_cep_start = clean_cep_fn(r.get("cep_start"))
        r_cep_end = clean_cep_fn(r.get("cep_end"))
        r_uf = str(r.get("uf") or "").upper().strip()

        match_cep = False
        if r_cep_start and r_cep_end:
            try:
                if int(r_cep_start) <= dest_int <= int(r_cep_end):
                    match_cep = True
            except Exception:
                pass

        match_uf = bool(r_uf and uf_dest and r_uf == uf_dest)
        if not (match_cep or match_uf or (not r_cep_start and not r_uf)):
            continue

        cubing_factor = float(r.get("cubing_factor") or 300.0)
        cubic_weight = total_volume_m3 * cubing_factor
        charged_weight = max(total_weight, cubic_weight)

        min_w = float(r.get("min_weight") or 0)
        max_w = float(r.get("max_weight") or 999999)
        check_w = charged_weight if charged_weight > 0 else total_weight
        if check_w > 0 and not (min_w <= check_w <= max_w):
            continue

        fixed_p = float(r.get("fixed_price") or 0)
        w_per_kg = float(r.get("weight_price_per_kg") or 0)
        ad_val_pct = float(r.get("ad_valorem_percent") or 0)
        gris_pct = float(r.get("gris_percent") or 0)
        min_f = float(r.get("min_freight_price") or 0)
        days = int(r.get("delivery_days") or 1)

        weight_cost = check_w * w_per_kg
        insurance_cost = total_insurance_value * ((ad_val_pct + gris_pct) / 100.0)
        total_price = max(fixed_p + weight_cost + insurance_cost, min_f)

        city_label = (r.get("city") or r_uf or "Padrão").strip()
        score = score_rate_for_destination(city_label, uf_dest, city_dest, match_cep)

        carrier_variants_map[c_id].append({
            "carrier_id": c_id,
            "carrier_name": c_name,
            "table_name": t_name,
            "city_label": city_label,
            "uf": r_uf or uf_dest,
            "total_price": round(total_price, 2),
            "fixed_price": round(fixed_p, 2),
            "insurance_cost": round(insurance_cost, 2),
            "delivery_days": days,
            "gross_weight_kg": round(total_weight, 2),
            "cubic_weight_kg": round(cubic_weight, 2),
            "charged_weight_kg": round(charged_weight, 2),
            "cubing_factor": cubing_factor,
            "notes": r.get("notes") or "",
            "_score": score,
        })

    options = []
    served_ids = set()

    for c_id, variants in carrier_variants_map.items():
        if not variants:
            continue
        # Deduplica por city_label mantendo o menor preço dentro da mesma praça
        dedup = {}
        for v in variants:
            lbl = v["city_label"]
            if lbl not in dedup or v["total_price"] < dedup[lbl]["total_price"]:
                dedup[lbl] = v

        unique_variants = list(dedup.values())
        # Ordena pelo melhor score de localidade; em empate, pelo menor preço
        unique_variants.sort(key=lambda x: (-x["_score"], x["total_price"], x["delivery_days"]))
        best = dict(unique_variants[0])
        best.pop("_score", None)

        # Lista limpa de variantes para o dropdown de praça no card
        clean_variants = []
        for uv in sorted(unique_variants, key=lambda x: (x["total_price"], x["city_label"])):
            cv = {
                "city_label": uv["city_label"],
                "total_price": uv["total_price"],
                "delivery_days": uv["delivery_days"],
                "fixed_price": uv["fixed_price"],
                "insurance_cost": uv["insurance_cost"],
            }
            clean_variants.append(cv)

        best["rate_variants"] = clean_variants
        options.append(best)
        served_ids.add(c_id)

    unserved_carriers = []
    for c_id, c_info in active_carriers.items():
        if allowed_set and c_id not in allowed_set:
            continue
        if c_id in served_ids:
            continue
        c_rates = carrier_rates_map.get(c_id, [])
        if not c_rates:
            reason = "Sem faixas tarifárias cadastradas na tabela."
        else:
            dest_matching = []
            for r in c_rates:
                s_c = clean_cep_fn(r.get("cep_start"))
                e_c = clean_cep_fn(r.get("cep_end"))
                u_c = str(r.get("uf") or "").upper().strip()
                m_cep = False
                if s_c and e_c:
                    try:
                        if int(s_c) <= dest_int <= int(e_c):
                            m_cep = True
                    except Exception:
                        pass
                m_uf = bool(u_c and uf_dest and u_c == uf_dest)
                if m_cep or m_uf or (not s_c and not u_c):
                    dest_matching.append(r)

            if not dest_matching:
                dest_str = f"{city_dest}/{uf_dest}" if (city_dest and uf_dest) else (uf_dest or format_cep_fn(clean_dest))
                reason = f"Não atende esta localidade ({dest_str})."
            else:
                max_w_list = [float(r.get("max_weight") or 0) for r in dest_matching if float(r.get("max_weight") or 0) > 0]
                min_w_list = [float(r.get("min_weight") or 0) for r in dest_matching]
                highest_max = max(max_w_list) if max_w_list else 0
                lowest_min = min(min_w_list) if min_w_list else 0

                check_w = max(total_weight, total_volume_m3 * 300.0)
                w_gross_str = f"{total_weight:.1f}".replace(".", ",")
                w_charged_str = f"{check_w:.1f}".replace(".", ",")
                if highest_max > 0 and check_w > highest_max:
                    max_str = f"{highest_max:.1f}".replace(".", ",")
                    reason = f"Peso tarifado ({w_charged_str} kg [Bruto: {w_gross_str}kg]) excede o limite máximo da tabela (até {max_str} kg)."
                elif check_w < lowest_min:
                    min_str = f"{lowest_min:.1f}".replace(".", ",")
                    reason = f"Peso tarifado ({w_charged_str} kg) abaixo do limite mínimo da tabela ({min_str} kg)."
                else:
                    reason = "Faixa tarifária não contempla os parâmetros da rota."

        unserved_carriers.append({
            "carrier_id": c_id,
            "carrier_name": c_info["name"],
            "table_name": c_info["table_name"],
            "reason": reason,
        })

    all_active_list = list(active_carriers.values())
    return options, unserved_carriers, all_active_list

