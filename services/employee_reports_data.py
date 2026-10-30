"""
M-One Employee Weekly Reports Configuration & Criteria (services/employee_reports_data.py)
Define os critérios oficiais de reporte semanal extraídos das cartilhas de função da MAJ Mobilidade:
Marisa, Jhon, Ricardo, Luiza, Leo, Gabriel e Fauzer.
"""

from __future__ import annotations

import urllib.parse
from typing import Any, Dict, List, Optional

# Usuários com acesso à visualização consolidada e gestão de prazos (Diretoria & Gerência)
ADMIN_MANAGERS = {"jam", "geysa", "fauzer", "support", "admin"}

# Mapeamento oficial dos colaboradores que enviam relatórios semanais
# Questionário padronizado para Vendedores Comerciais de Atacado B2B (Gabriel e Gustavo)
ATACADO_QUESTIONS = [
    {
        "id": "prospeccao",
        "label": "1. Prospecção (Novos Contatos, Segmentos e Oportunidades)",
        "placeholder": "Novos contatos iniciados, principais segmentos abordados e oportunidades relevantes da prospecção...",
        "help": "Mapeamento ativo de novos revendedores e lojistas B2B."
    },
    {
        "id": "follow_up",
        "label": "2. Follow-Up (Clientes Atuais e Negociações em Andamento)",
        "placeholder": "Clientes atuais/antigos trabalhados e negociações quentes com previsão de fechar em breve...",
        "help": "Manutenção do relacionamento ativo com a carteira de atacado."
    },
    {
        "id": "fechamentos",
        "label": "3. Fechamentos e Vendas no Período",
        "placeholder": "Vendas fechadas na semana, principais modelos (Max 12, GP1000, Vittoria, V80) e observações relevantes...",
        "help": "Desempenho comercial e pedidos faturados com lojistas."
    },
    {
        "id": "objecoes_atacado",
        "label": "4. Objeções Mais Frequentes nas Revendas",
        "placeholder": "Travas dos revendedores: Preço, Prazo, Frete, Produto, Concorrência e Outros...",
        "help": "Base para criação de pacotes comerciais atrativos e desova de estoque."
    },
    {
        "id": "sinais_mercado",
        "label": "5. Sinais do Mercado & Concorrência",
        "placeholder": "Produtos mais pedidos, produtos com dificuldade de saída e movimentações dos concorrentes...",
        "help": "Termômetro do mercado atacadista de mobilidade elétrica."
    },
    {
        "id": "pendencias_direcao",
        "label": "6. Pendências, Decisões da Direção & Regras",
        "placeholder": "Casos que exigem decisão de Jam e Geysa na reunião. Lembrete: Regra Técnica (não fornecer diagnóstico) e Regra de Remuneração (comissão 1% via NF)...",
        "help": "Pauta executiva de alinhamento com a Diretoria."
    }
]

REPORTING_EMPLOYEES: Dict[str, Dict[str, Any]] = {
    "marisa": {
        "key": "marisa",
        "username": "marisa",
        "name": "Marisa",
        "role_title": "Assistente Administrativo / Financeiro",
        "area": "Financeiro & Faturamento",
        "badge": "FINANCEIRO",
        "badge_color": "green",
        "phone": "5527999990001",
        "deadline_day": "Sexta-feira",
        "deadline_time": "18:00",
        "instructions": (
            "Preencha as informações do seu fechamento semanal. Seus dados serão consolidados para a "
            "reunião de gestão da diretoria na segunda-feira."
        ),
        "questions": [
            {
                "id": "faturamento_nfs",
                "label": "1. Faturamento e NFs Relevantes Emitidas",
                "placeholder": "Destaque os principais faturamentos da semana, NFs de atacado, devoluções, triangulações ou operações especiais...",
                "help": "Conforme item 8.1 da sua cartilha oficial."
            },
            {
                "id": "entradas_pendentes",
                "label": "2. Entradas e Recebimentos Pendentes",
                "placeholder": "Valores a receber em aberto, conferência do caixa físico vs registrado no fechamento diário com Jhon...",
                "help": "Registre qualquer discrepância ou valor aguardando quitação."
            },
            {
                "id": "contas_vencimentos",
                "label": "3. Contas e Vencimentos Repassados para Geysa",
                "placeholder": "Resumo das contas da próxima semana organizadas e encaminhadas para autorização e pagamento...",
                "help": "Garante que nenhuma conta sofra juros por falta de repasse prévio."
            },
            {
                "id": "docs_faltantes",
                "label": "4. Documentos Fiscais ou Comprovantes Faltantes",
                "placeholder": "NFs de fornecedores, comprovantes de despesas ou notas fiscais pendentes de envio...",
                "help": "Identifique fornecedores ou parceiros com pendências de documentação."
            },
            {
                "id": "recibos_pendentes",
                "label": "5. Recibos de Entrega Pendentes do Motorista",
                "placeholder": "Recibos assinados e checklists de entrega aguardando retorno do motorista para arquivamento...",
                "help": "Motorista deve entregar recibos assinados diretamente à Marisa."
            },
            {
                "id": "piloto_mercado_pago",
                "label": "6. Resultado do Piloto: Conciliação Mercado Pago",
                "placeholder": "Conferência semanal: valores brutos, taxas cobradas, estornos, antecipações e saldo líquido apurado...",
                "help": "Piloto de 30 dias para validação das taxas e conciliação do Mercado Pago."
            },
            {
                "id": "prioridades_proxima_semana",
                "label": "7. Ocorrências Relevantes e Prioridades da Próxima Semana",
                "placeholder": "Avisos, pontos de atenção ou prioridades financeiras que precisam de acompanhamento...",
                "help": "Fatos relevantes para conhecimento da Gerência Geral (Geysa)."
            }
        ]
    },
    "jhon": {
        "key": "jhon",
        "username": "jhon",
        "name": "Jhon",
        "role_title": "Assistente Administrativo / Estoque",
        "area": "Estoque & Expedição",
        "badge": "ESTOQUE",
        "badge_color": "amber",
        "phone": "5527999990002",
        "deadline_day": "Sexta-feira",
        "deadline_time": "18:00",
        "instructions": (
            "Relatório semanal da contagem rotativa de sexta-feira, conferência de NFs e integridade física "
            "dos veículos nos depósitos."
        ),
        "questions": [
            {
                "id": "contagem_rotativa",
                "label": "1. Contagem Rotativa Realizada na Sexta-feira",
                "placeholder": "Modelos e quantidades físicas conferidas no Galpão MAJ e no Galpão M-One / COLVIX...",
                "help": "A contagem de sexta-feira é obrigatória e nunca deve ser pulada."
            },
            {
                "id": "divergencias",
                "label": "2. Divergências Físicas Encontradas e Investigadas",
                "placeholder": "Diferenças entre o estoque físico contado e o saldo registrado no sistema / Bling, com as causas investigadas...",
                "help": "Nenhuma divergência pode ficar sem explicação ou apuração."
            },
            {
                "id": "nfs_demonstracao",
                "label": "3. NFs de Demonstração (Showroom e Galpões)",
                "placeholder": "Conferência das notas de demonstração coladas nos veículos em exposição: faltantes, renovadas ou corrigidas...",
                "help": "Todas as unidades em demonstração exigem NF visível e regularizada."
            },
            {
                "id": "movimentacoes_localizacao",
                "label": "4. Movimentações Físicas e Organização dos Galpões",
                "placeholder": "Transferências entre galpões, chassis organizados por lote e status dos lotes de desova vs pronta entrega...",
                "help": "Organização espacial e identificação clara de cada veículo."
            },
            {
                "id": "codigo_barras",
                "label": "5. Situação do Código de Barras e Etiquetas",
                "placeholder": "Avanço da etiquetagem e leitura de códigos de barras nas caixas e chassis para agilizar conferências...",
                "help": "Redução do tempo de conferência através da leitura ótica."
            },
            {
                "id": "despesas_saidas",
                "label": "6. Despesas e Saídas Operacionais do Estoque",
                "placeholder": "Prestação de despesas operacionais do estoque e fechamento diário realizado com Marisa...",
                "help": "Lançamento até o fechamento sem pendências financeiras."
            },
            {
                "id": "prioridades_proxima_semana",
                "label": "7. Prioridades e Demandas do Estoque para a Próxima Semana",
                "placeholder": "Previsão de contêineres a receber, paletização, insumos para embalagem ou necessidades estruturais...",
                "help": "Planejamento operacional para evitar gargalos na expedição."
            }
        ]
    },
    "ricardo": {
        "key": "ricardo",
        "username": "ricardo",
        "name": "Ricardo Bourguignon",
        "role_title": "Gerente de Oficina e Pós-Vendas",
        "area": "Oficina Técnica",
        "badge": "OFICINA",
        "badge_color": "cyan",
        "phone": "5527998846260",
        "deadline_day": "Sexta-feira",
        "deadline_time": "18:00",
        "instructions": (
            "Reporte semanal da oficina técnica (Consolação): produtividade, ordens de serviço, qualidade "
            "e necessidades de peças."
        ),
        "questions": [
            {
                "id": "servicos_concluidos",
                "label": "1. Serviços e Reparos Concluídos na Semana",
                "placeholder": "Resumo das revisões de entrega (PDI), montagens de motos novas e reparos entregues aos clientes com OS baixada...",
                "help": "Total de veículos prontos e liberados pela oficina técnica."
            },
            {
                "id": "os_pendentes",
                "label": "2. Ordens de Serviço Pendentes ou Atrasadas e Motivos",
                "placeholder": "Motos paradas na oficina: clientes aguardando, falta de peça específica, autorização pendente ou diagnóstico em andamento...",
                "help": "Identifique o motivo exato de qualquer atraso ou fila na bancada."
            },
            {
                "id": "retrabalhos",
                "label": "3. Retrabalhos Ocorridos na Semana",
                "placeholder": "Veículos que precisaram de correção após liberação inicial, ajustes de montagem ou retorno de serviço...",
                "help": "Crucial para mapear qualidade técnica e ajustar o checklist final."
            },
            {
                "id": "diagnosticos_complexos",
                "label": "4. Diagnósticos Técnicos Complexos e Casos Atípicos",
                "placeholder": "Falhas elétricas intermitentes, controladores, motores brushless ou problemas incomuns identificados...",
                "help": "Compartilhe para registro de conhecimento técnico corporativo."
            },
            {
                "id": "defeitos_recorrentes",
                "label": "5. Defeitos Recorrentes Observados nos Modelos",
                "placeholder": "Problemas frequentes de fábrica ou de lote (ex: freios, chicotes, display, amortecedores)...",
                "help": "Alimenta o feedback direto para o fornecedor / compras internacionais."
            },
            {
                "id": "necessidade_pecas",
                "label": "6. Necessidade de Peças de Reposição e Ferramentas",
                "placeholder": "Itens com estoque baixo na oficina, peças urgentes necessárias e ferramentas/equipamentos requeridos...",
                "help": "Permite compras programadas sem paralisar serviços."
            },
            {
                "id": "equipe_apoio",
                "label": "7. Situação da Equipe Técnica (Leandro, Rafael e Motorista)",
                "placeholder": "Desempenho dos mecânicos na montagem/elétrica, organização das bancadas e apoio do motorista para liberar seu tempo...",
                "help": "Avalie se sua rotina gerencial está desimpedida para foco em qualidade e prazos."
            }
        ]
    },
    "luiza": {
        "key": "luiza",
        "username": "luiza",
        "name": "Luiza",
        "role_title": "Vendedora Comercial / Voz do Cliente",
        "area": "Comercial & Vendas",
        "badge": "VENDAS",
        "badge_color": "emerald",
        "phone": "5527999990004",
        "deadline_day": "Sexta-feira",
        "deadline_time": "18:00",
        "instructions": (
            "Relatório de Voz do Cliente e Inteligência Comercial. Seus dados orientam as decisões de marketing "
            "e suprimentos da direção."
        ),
        "questions": [
            {
                "id": "modelos_procurados",
                "label": "1. Modelos Mais Procurados pelos Clientes",
                "placeholder": "Quais modelos de motos ou autopropelidos tiveram maior volume de interesse, perguntas e orçamentos na semana?",
                "help": "Indica a preferência atual da demanda no atendimento comercial."
            },
            {
                "id": "objecoes_perdas",
                "label": "2. Objeções Mais Comuns e Motivos de Perda de Vendas",
                "placeholder": "Por que clientes desistiram ou não fecharam? (ex: prazo de entrega, forma de pagamento, parcelamento, desconfiança)...",
                "help": "Ajuda a equipe a ajustar argumentos de venda e processos de pagamento."
            },
            {
                "id": "precos_altos",
                "label": "3. Preços Considerados Altos pelos Clientes",
                "placeholder": "Houve algum modelo ou condição em que os clientes reclamaram diretamente do valor comparado ao mercado?",
                "help": "Sinaliza elasticidade de preço para estratégias de Outlet e descontos."
            },
            {
                "id": "reclamacoes_elogios",
                "label": "4. Reclamações e Elogios Recorrentes",
                "placeholder": "O que os clientes mais elogiaram e do que mais reclamaram no processo de compra e atendimento?",
                "help": "Mapeia a percepção de valor do público em relação à MAJ."
            },
            {
                "id": "qualidade_bot",
                "label": "5. Qualidade Percebida do BotConversa (WhatsApp)",
                "placeholder": "Onde os clientes estão travando? As mensagens automáticas estão claras ou há ruído na triagem?",
                "help": "Permite ao Fauzer calibrar os fluxos automáticos do bot."
            },
            {
                "id": "conteudo_video",
                "label": "6. Produtos que Precisam de Vídeo / Conteúdo Novo e Por Quê",
                "placeholder": "Qual modelo precisa urgente de fotos reais, vídeos de uso, detalhes de bateria ou tutorial demonstrativo?",
                "help": "Direciona a produção de novos criativos de marketing e materiais visuais."
            },
            {
                "id": "sugestao_comercial",
                "label": "7. Uma Sugestão Comercial da Semana",
                "placeholder": "Ideia prática para alavancar vendas, campanha pontual, brinde, combo ou melhoria na abordagem...",
                "help": "Sua sugestão oficial que será analisada na reunião de gestão de segunda-feira."
            }
        ]
    },
    "leo": {
        "key": "leo",
        "username": "leo",
        "name": "Léo",
        "role_title": "Pós-Venda & Atendimento ao Cliente",
        "area": "Pós-Venda & Triagem de Oficina",
        "badge": "PÓS-VENDA",
        "badge_color": "cyan",
        "phone": "5527999990005",
        "deadline_day": "Sexta-feira",
        "deadline_time": "18:00",
        "instructions": (
            "Relatório semanal de pós-venda: controle de OS, atrasos de serviços, clientes sensíveis, "
            "orçamentos, triagem de garantia e interface com a oficina técnica."
        ),
        "questions": [
            {
                "id": "os_da_semana",
                "label": "1. OS da Semana (Abertas, Concluídas e Pendentes)",
                "placeholder": "Quantidade de OS abertas, concluídas e ainda pendentes na oficina...",
                "help": "Métricas semanais de entrada e saída de ordens de serviço."
            },
            {
                "id": "atrasos_servicos",
                "label": "2. Atrasos em Serviços, Motivos e Atualização dos Clientes",
                "placeholder": "Serviços atrasados, motivos de cada atraso e se os clientes foram devidamente avisados...",
                "help": "Garante alinhamento prévio e combate frustração do cliente."
            },
            {
                "id": "clientes_sensiveis",
                "label": "3. Clientes Sensíveis, Reclamações ou Riscos de Conflito",
                "placeholder": "Relate clientes insatisfeitos, veículos com histórico complexo ou risco de conflito...",
                "help": "Alerta a gerência para atuação preventiva e blindagem da marca."
            },
            {
                "id": "orcamentos_oficina",
                "label": "4. Orçamentos da Oficina (Aguardando Aprovação e Aprovados)",
                "placeholder": "Orçamentos aguardando resposta do cliente e aprovados ainda em execução...",
                "help": "Visibilidade do fluxo financeiro e operacional da oficina."
            },
            {
                "id": "garantia_triagem",
                "label": "5. Casos de Garantia / Triagem Encaminhados ao Ricardo",
                "placeholder": "Casos encaminhados à oficina para diagnóstico técnico e casos aguardando dados/vídeos...",
                "help": "Léo realiza a triagem de dados; Ricardo executa o diagnóstico técnico."
            },
            {
                "id": "concessoes_semana",
                "label": "6. Concessões Utilizadas na Semana e Benefícios Concedidos",
                "placeholder": "Concessões e benefícios concedidos a clientes, motivos e valores estimados...",
                "help": "Alinhado aos limites financeiros autorizados pela diretoria."
            },
            {
                "id": "pagamentos_oficina",
                "label": "7. Pagamentos da Oficina e Registros Pendentes",
                "placeholder": "Pendências de pagamento de serviços, comprovantes ou quitações em aberto...",
                "help": "Garante que nenhuma moto saia da oficina sem liquidação financeira."
            },
            {
                "id": "pendencias_decisao",
                "label": "8. Pendências que Precisam de Decisão da Diretoria",
                "placeholder": "Casos atípicos, impasses ou concessões fora de alçada para pauta de segunda-feira...",
                "help": "Prioridades executivas para deliberação de Jam e Geysa."
            }
        ]
    },
    "gabriel": {
        "key": "gabriel",
        "username": "gabriel",
        "name": "Gabriel",
        "role_title": "Vendedor Comercial / Atacado B2B",
        "area": "Comercial (Atacado & Expansão)",
        "badge": "ATACADO B2B",
        "badge_color": "indigo",
        "phone": "5527998867335",
        "deadline_day": "Sexta-feira",
        "deadline_time": "18:00",
        "instructions": (
            "Resumo comercial semanal de resultados, sinais do mercado atacadista e relacionamento com revendedores."
        ),
        "questions": ATACADO_QUESTIONS
    },
    "gustavo": {
        "key": "gustavo",
        "username": "gustavo",
        "name": "Gustavo",
        "role_title": "Vendedor Comercial / Atacado B2B",
        "area": "Comercial (Atacado & Expansão)",
        "badge": "ATACADO B2B",
        "badge_color": "indigo",
        "phone": "5527993161803",
        "deadline_day": "Sexta-feira",
        "deadline_time": "18:00",
        "instructions": (
            "Resumo comercial semanal de resultados, sinais do mercado atacadista e relacionamento com revendedores."
        ),
        "questions": ATACADO_QUESTIONS
    },
    "fauzer": {
        "key": "fauzer",
        "username": "fauzer",
        "name": "Fauzer",
        "role_title": "Sistemas, Processos & Marketing",
        "area": "Tecnologia, Processos & Marketing",
        "badge": "SISTEMAS & PROCESSOS",
        "badge_color": "purple",
        "phone": "5527999990007",
        "deadline_day": "Sexta-feira",
        "deadline_time": "18:00",
        "instructions": (
            "Relatório próprio semanal de marketing, processos e sistemas corporativos. Este relatório "
            "integra o briefing da reunião de segunda-feira."
        ),
        "questions": [
            {
                "id": "marketing_investimento",
                "label": "1. Desempenho de Marketing, Mídia & Tráfego",
                "placeholder": "Investimento semanal em anúncios Meta/Google, CPL apurado, conversões, criativos com melhor e pior desempenho...",
                "help": "Leitura objetiva do retorno dos investimentos de mídia paga."
            },
            {
                "id": "processos_sistemas",
                "label": "2. Status dos Sistemas Corporativos (M-One, Bling, BotConversa)",
                "placeholder": "Melhorias implantadas no M-One, integrações Bling, ajustes de fluxo no BotConversa, automações e segurança/2FA...",
                "help": "Evolução contínua da infraestrutura tecnológica da MAJ."
            },
            {
                "id": "falhas_desvios",
                "label": "3. Falhas Operacionais e Desvios de Processo Mapeados",
                "placeholder": "Falhas em entregas, omissões de checklist, desalinhamento de alçadas ou problemas recorrentes observados...",
                "help": "Permite correção preventiva e alinhamento sem aplicar advertências."
            },
            {
                "id": "treinamentos_alinhamentos",
                "label": "4. Treinamentos Realizados e Status de Implantação",
                "placeholder": "Alinhamentos com colaboradores sobre ferramentas, adoção das rotinas e suporte operacional prestado...",
                "help": "Acompanhamento do avanço das fases da implantação corporativa."
            },
            {
                "id": "pontos_decisao_diretoria",
                "label": "5. Pontos Críticos e Decisões para a Reunião de Segunda-feira",
                "placeholder": "Decisões que exigem definição imediata de Jam Penitenti e Geysa na reunião de gestão de 20-30 minutos...",
                "help": "Pauta executiva prioritária para alinhamento estratégico."
            }
        ]
    }
}


def get_reporting_employee_meta(employee_key: str) -> Optional[Dict[str, Any]]:
    """Retorna os metadados e perguntas do colaborador pelo identificador."""
    return REPORTING_EMPLOYEES.get(employee_key.lower().strip())


def is_admin_viewer(username: Optional[str], role: Optional[str] = None) -> bool:
    """
    Verifica se o usuário possui perfil de Diretoria/Gerência para visualizar a Gestão Interna.
    Restrito estritamente a Jam Penitenti, Geysa, Fauzer, administradores e suporte técnico.
    """
    u = (username or "").lower().strip()
    r = (role or "").lower().strip()
    return u in ADMIN_MANAGERS or r in {"admin", "support"}


def generate_whatsapp_charge_url(
    employee_name: str,
    phone: str,
    cycle_title: str,
    deadline_str: str,
    status_label: str = "Pendente"
) -> str:
    """Gera link direto para WhatsApp com mensagem oficial e respeitosa de lembrete/cobrança."""
    clean_phone = "".join(c for c in phone if c.isdigit())
    if not clean_phone.startswith("55") and len(clean_phone) <= 11:
        clean_phone = f"55{clean_phone}"

    msg = (
        f"Olá {employee_name}, tudo bem? 👋\n\n"
        f"Lembramos que o preenchimento do seu *Relatório Semanal da MAJ Mobilidade* ({cycle_title}) "
        f"está com status: *{status_label}*.\n\n"
        f"📅 *Prazo Oficial:* {deadline_str}\n"
        f"🔗 *Acesse para preencher:* https://m-one.majmobilidade.com.br/admin/plano\n\n"
        f"Seus dados são fundamentais para alinharmos as prioridades na reunião de gestão de segunda-feira. "
        f"Qualquer dúvida, conte com a gente! ⚡"
    )

    encoded_msg = urllib.parse.quote(msg)
    return f"https://wa.me/{clean_phone}?text={encoded_msg}"
