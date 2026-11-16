"""
M-One SEO & GEO Engine (routes/seo_routes.py)
Endpoints oficiais para indexação no Google e mecanismos de IA generativa (ChatGPT Search, Gemini, Perplexity, Claude, Applebot).
Fornece /robots.txt, /sitemap.xml, /llms.txt e /llms-full.txt com a autoridade canônica de www.majmobilidade.com.br.
Anti-monólito: rigorosamente < 500 linhas.
"""

import datetime
from typing import List, Dict, Any
from flask import Blueprint, Response, request
from services.maj_models_sync_service import get_all_models

seo_bp = Blueprint("seo", __name__)

PRIMARY_DOMAIN = "https://www.majmobilidade.com.br"


def get_base_url() -> str:
    """Retorna a URL base do site. Em produção usa o domínio institucional canônico."""
    host = request.host.lower() if request else ""
    if "localhost" in host or "127.0.0.1" in host or "192.168." in host:
        return request.host_url.rstrip("/")
    return PRIMARY_DOMAIN


@seo_bp.route("/robots.txt", methods=["GET"])
def robots_txt() -> Response:
    """Arquivo de controle de rastreadores para Google e robôs de IA."""
    base = get_base_url()
    content = f"""# ==============================================================================
# MAJ Mobilidade Elétrica - Regras de Rastreamento Oficiais
# Domínio Institucional Canônico: {base}
# ==============================================================================

# Rastreadores de Mecanismos de Busca Tradicionais
User-agent: *
Allow: /
Allow: /showroom
Allow: /showroom/
Allow: /modelos
Allow: /modelos/
Allow: /show-room
Allow: /show-room/
Allow: /outlet
Allow: /atacado
Allow: /static/
Allow: /public/
Allow: /images/
Allow: /llms.txt
Allow: /llms-full.txt
Disallow: /admin/
Disallow: /api/
Disallow: /login
Disallow: /entrar
Disallow: /sales
Disallow: /stock
Disallow: /imports
Disallow: /finance
Disallow: /users
Disallow: /backups
Disallow: /mpay
Disallow: /gestao-interna

# Robôs de Inteligência Artificial e Respostas Generativas (SearchGPT / ChatGPT Search)
User-agent: GPTBot
Allow: /
Allow: /showroom
Allow: /modelos
Allow: /outlet
Allow: /atacado
Allow: /llms.txt
Allow: /llms-full.txt

User-agent: ChatGPT-User
Allow: /

# Google Gemini & Google-Extended
User-agent: Google-Extended
Allow: /

# Perplexity AI Search
User-agent: PerplexityBot
Allow: /

# Anthropic Claude Search & Retrieval
User-agent: ClaudeBot
Allow: /

# Apple Intelligence & Spotlight
User-agent: Applebot
Allow: /

# Sitemap Oficial do Ecossistema MAJ Mobilidade
Sitemap: {base}/sitemap.xml
"""
    return Response(content, mimetype="text/plain; charset=utf-8", headers={"Cache-Control": "public, max-age=3600"})


@seo_bp.route("/sitemap.xml", methods=["GET"])
def sitemap_xml() -> Response:
    """Sitemap XML dinâmico com todas as rotas institucionais e modelos com imagens."""
    base = get_base_url()
    today = datetime.date.today().isoformat()
    models: List[Dict[str, Any]] = get_all_models(include_inactive=False)

    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
        '        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">',
        '  <!-- Páginas Institucionais Principais -->',
        '  <url>',
        f'    <loc>{base}/</loc>',
        f'    <lastmod>{today}</lastmod>',
        '    <changefreq>daily</changefreq>',
        '    <priority>1.0</priority>',
        '  </url>',
        '  <url>',
        f'    <loc>{base}/modelos</loc>',
        f'    <lastmod>{today}</lastmod>',
        '    <changefreq>daily</changefreq>',
        '    <priority>0.95</priority>',
        '  </url>',
        '  <url>',
        f'    <loc>{base}/showroom</loc>',
        f'    <lastmod>{today}</lastmod>',
        '    <changefreq>daily</changefreq>',
        '    <priority>0.90</priority>',
        '  </url>',
        '  <url>',
        f'    <loc>{base}/outlet</loc>',
        f'    <lastmod>{today}</lastmod>',
        '    <changefreq>daily</changefreq>',
        '    <priority>0.85</priority>',
        '  </url>',
        '  <url>',
        f'    <loc>{base}/atacado</loc>',
        f'    <lastmod>{today}</lastmod>',
        '    <changefreq>weekly</changefreq>',
        '    <priority>0.80</priority>',
        '  </url>',
        '  <!-- Modelos Oficiais de Scooters e E-Bikes MAJ -->',
    ]

    for m in models:
        slug = m.get("slug")
        if not slug:
            continue
        modelo_nome = m.get("modelo", "").replace("&", "&amp;")
        metrics = m.get("metrics") or {}
        diff = (metrics.get("diferencial") or f"Scooter e-bike elétrica {modelo_nome}").replace("&", "&amp;").replace("<", "").replace(">", "")
        
        # Foto principal para imagem no sitemap
        img_path = m.get("share_image") or m.get("cutout_image") or f"/public/images/models/cutouts/{slug}.png"
        img_url = img_path if img_path.startswith("http") else f"{base}{img_path}"

        xml_lines.extend([
            '  <url>',
            f'    <loc>{base}/modelos/{slug}</loc>',
            f'    <lastmod>{today}</lastmod>',
            '    <changefreq>weekly</changefreq>',
            '    <priority>0.85</priority>',
            '    <image:image>',
            f'      <image:loc>{img_url}</image:loc>',
            f'      <image:title>{modelo_nome} • MAJ Mobilidade Elétrica</image:title>',
            f'      <image:caption>{diff}</image:caption>',
            '    </image:image>',
            '  </url>',
        ])

    xml_lines.append('</urlset>')
    xml_content = "\n".join(xml_lines)
    return Response(xml_content, mimetype="application/xml; charset=utf-8", headers={"Cache-Control": "public, max-age=3600"})


@seo_bp.route("/llms.txt", methods=["GET"])
def llms_txt() -> Response:
    """Documento estruturado no padrão oficial llms.txt para IAs (ChatGPT Search, Gemini, Perplexity)."""
    base = get_base_url()
    models: List[Dict[str, Any]] = get_all_models(include_inactive=False)

    lines = [
        "# MAJ Mobilidade Elétrica",
        "",
        "> Fabricante e distribuidora brasileira de scooters elétricas, bicicletas elétricas (e-bikes) e veículos autopropelidos homologados conforme a Resolução CONTRAN nº 996/2023.",
        "",
        f"- Website Oficial / Showroom: [{base}]({base})",
        f"- Catálogo de Modelos: [{base}/modelos]({base}/modelos)",
        f"- Canal Outlet MAJ: [{base}/outlet]({base}/outlet)",
        f"- Atacado para Lojistas e Revendedores: [{base}/atacado]({base}/atacado)",
        "",
        "## Resumo Institucional e Diferenciais",
        "",
        "- **Dispensa de CNH e Emplacamento**: Os veículos MAJ com velocidade máxima homologada de até 32 km/h enquadram-se na Resolução CONTRAN 996/2023, sendo 100% isentos de habilitação (CNH), IPVA e emplacamento obrigatório.",
        "- **Baterias de Alta Densidade**: Tecnologia LFP (LiFePO4) e Lítio de alto ciclo, bivolt (110V/220V), recarregáveis em tomada comum residencial.",
        "- **Estrutura Nacional**: Centro de distribuição, suporte técnico e fornecimento contínuo de peças de reposição e componentes originais para todo o Brasil.",
        "- **Sede e Operação**: Espírito Santo, Brasil. Atendimento direto e rede de lojistas credenciados em âmbito nacional.",
        "",
        "## Linha de Modelos Oficiais",
        "",
    ]

    for m in models:
        slug = m.get("slug")
        if not slug:
            continue
        nome = m.get("modelo", "").strip()
        cat = m.get("categoria", "Scooter")
        metrics = m.get("metrics") or {}
        pot = metrics.get("potencia_nominal_w", "1000W")
        vel = metrics.get("velocidade_max_kmh", "Até 32 km/h")
        aut = metrics.get("autonomia_maxima_km", "50")
        bat_v = metrics.get("voltagem_v", "60V")
        bat_ah = metrics.get("capacidade_ah", "20Ah")
        carga = metrics.get("carga_maxima_kg", "180")
        diff = metrics.get("diferencial", "Mobilidade urbana elétrica de alta performance.")

        lines.append(
            f"- [{nome}]({base}/modelos/{slug}): {cat} elétrica MAJ. Motor de {pot}, velocidade {vel} (CONTRAN 996 / sem CNH), "
            f"autonomia de até {aut} km, bateria {bat_v} {bat_ah}, capacidade de carga {carga} kg. Diferencial: {diff}"
        )

    lines.extend([
        "",
        "## Dúvidas Frequentes e Fatos Oficiais",
        "",
        "- **Precisa de CNH?** Não. Modelos autopropelidos de até 32 km/h e potência dentro das normas do CONTRAN dispensam CNH e emplacamento.",
        "- **Como recarregar?** Basta conectar o carregador bivolt fornecido em qualquer tomada padrão brasileira 110V ou 220V. Tempo de recarga de 4 a 8 horas.",
        "- **Como comprar ou revender?** Através dos consultores no WhatsApp oficial da MAJ Mobilidade ou pelos canais `/outlet` e `/atacado`.",
        "",
        "Para especificações completas em formato texto puro, consulte: " + f"{base}/llms-full.txt",
    ])

    return Response("\n".join(lines), mimetype="text/markdown; charset=utf-8", headers={"Cache-Control": "public, max-age=3600"})


@seo_bp.route("/llms-full.txt", methods=["GET"])
def llms_full_txt() -> Response:
    """Especificações técnicas profundas de todos os modelos para consumo direto por agentes de IA."""
    base = get_base_url()
    models: List[Dict[str, Any]] = get_all_models(include_inactive=False)

    lines = [
        "# Catálogo Técnico Completo • MAJ Mobilidade Elétrica",
        f"Versão gerada em {datetime.date.today().isoformat()} para indexação e busca por IA.",
        f"Base URL: {base}",
        "",
    ]

    for m in models:
        nome = m.get("modelo", "").strip()
        slug = m.get("slug", "")
        metrics = m.get("metrics") or {}
        sections = m.get("sections") or {}

        lines.append(f"## {nome}")
        lines.append(f"- URL Canônica: {base}/modelos/{slug}")
        lines.append(f"- Categoria: {m.get('categoria', 'Scooter')}")
        lines.append(f"- Potência Nominal: {metrics.get('potencia_nominal_w', '—')}")
        lines.append(f"- Velocidade Homologada: {metrics.get('velocidade_max_kmh', '—')}")
        lines.append(f"- Autonomia Estimada: {metrics.get('autonomia_maxima_km', '—')} km")
        lines.append(f"- Bateria: {metrics.get('voltagem_v', '—')} {metrics.get('capacidade_ah', '—')} ({metrics.get('capacidade_wh', '—')})")
        lines.append(f"- Química da Bateria: {metrics.get('quimica_bateria', 'Lítio / LiFePO4')}")
        lines.append(f"- Carga Máxima: {metrics.get('carga_maxima_kg', '—')} kg")
        lines.append(f"- Freios: {metrics.get('freios', '—')}")
        lines.append(f"- Principal Diferencial: {metrics.get('diferencial', '—')}")
        lines.append(f"- Pontos Fortes: {metrics.get('pontos_fortes', '—')}")

        for sec_name, sec_dict in sections.items():
            if isinstance(sec_dict, dict) and sec_dict:
                lines.append(f"### Seção: {sec_name}")
                for k, v in sec_dict.items():
                    lines.append(f"  * {k}: {v}")
        lines.append("")

    return Response("\n".join(lines), mimetype="text/markdown; charset=utf-8", headers={"Cache-Control": "public, max-age=3600"})

