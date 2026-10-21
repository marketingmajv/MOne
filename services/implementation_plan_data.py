"""
M-One Implementation Plan Seed Data (services/implementation_plan_data.py)
Dados estruturados da equipe (11 colaboradores), 4 fases do cronograma e diagnóstico por área.
"""

from typing import Any, Dict, List


def get_default_phases_data() -> List[Dict[str, Any]]:
    """Retorna a matriz oficial das 4 fases levantadas no diagnóstico da MAJ."""
    return [
        {
            "phase_number": 1,
            "title": "Controles Essenciais",
            "period": "Semanas 1–4",
            "description": "Estabilização financeira imediata, dupla conferência de mercadorias na expedição e saneamento das pendências da oficina técnica.",
            "status": "Em Andamento",
            "progress_percent": 35,
            "start_date": "Semana 1",
            "end_date": "Semana 4",
            "notes": "Foco prioritário em fechamento de caixa diário e eliminação de OS pendentes sem lançamento no Bling.",
            "tasks": [
                {"title": "Fechamento Diário de Caixa", "responsible": "Marisa", "done": True, "detail": "Registro rigoroso de entradas, saídas e conciliação bancária diária."},
                {"title": "Registro Rigoroso de Despesas", "responsible": "Marisa / Geysa", "done": True, "detail": "Nenhuma despesa sem comprovante e aprovação conforme política de alçadas."},
                {"title": "Dupla Conferência na Expedição", "responsible": "Jhon", "done": False, "detail": "Conferência cruzada de nota fiscal e carga física antes do despacho das transportadoras."},
                {"title": "Saneamento de Pendências de OS", "responsible": "Ricardo", "done": False, "detail": "Abertura, status e baixa formal de ordens de serviço da oficina no Bling."}
            ],
            "responsibles": ["Marisa", "Geysa", "Jhon", "Ricardo"]
        },
        {
            "phase_number": 2,
            "title": "Organização Operacional",
            "period": "Semanas 5–8",
            "description": "Rotinas de inventário rotativo semanal nos dois galpões, padronização de procedimentos diários e relatórios gerenciais iniciais.",
            "status": "Planejada",
            "progress_percent": 0,
            "start_date": "Semana 5",
            "end_date": "Semana 8",
            "notes": "Implantação do checklist semanal de contagem física para Jhon alternando entre os galpões.",
            "tasks": [
                {"title": "Inventários Rotativos Semanais", "responsible": "Jhon", "done": False, "detail": "Contagem física periódica no Galpão M-One e Galpão MAJ Antiga comparando com o Bling."},
                {"title": "Rotinas Padronizadas de Vendas", "responsible": "Leo / Luiza / Gabriel", "done": False, "detail": "Checklist de follow-up, orçamentos e consulta obrigatória de chassi liberado."},
                {"title": "Fluxo de Peças e Serviços da Oficina", "responsible": "Ricardo / Mecânicos", "done": False, "detail": "Requisição prévia de peças atrelada à OS e checagem de qualidade antes da entrega."},
                {"title": "Primeiros Relatórios Operacionais", "responsible": "Geysa / Fauzer", "done": False, "detail": "Acompanhamento de indicadores de vendas, estoque e prazos de reparo."}
            ],
            "responsibles": ["Jhon", "Ricardo", "Leo", "Marisa", "Geysa", "Fauzer"]
        },
        {
            "phase_number": 3,
            "title": "Gestão e Recursos Humanos",
            "period": "Semanas 9–12",
            "description": "Estruturação do programa de integração e treinamento de colaboradores, regulamento interno e reuniões semanais de gestão.",
            "status": "Planejada",
            "progress_percent": 0,
            "start_date": "Semana 9",
            "end_date": "Semana 12",
            "notes": "Criação do Programa de Integração MAJ (1º dia, 1ª semana, 30 e 90 dias) e atas formais de reunião.",
            "tasks": [
                {"title": "Programa de Integração e Treinamento", "responsible": "Geysa / Fauzer", "done": False, "detail": "Manual de boas-vindas, apresentação das ferramentas e treinamento técnico inicial."},
                {"title": "Regulamento Interno & Conduta", "responsible": "Geysa / Jam", "done": False, "detail": "Definição clara de horários, regras de convivência, uso de equipamentos e responsabilidades."},
                {"title": "Reuniões Semanais de Resultados", "responsible": "Geysa", "done": False, "detail": "Reuniões periódicas com metas, distribuição de tarefas e cobrança do que foi acordado."},
                {"title": "Avaliações de Experiência (45 e 90 dias)", "responsible": "Geysa", "done": False, "detail": "Critérios objetivos de adaptação e evolução profissional dos colaboradores."}
            ],
            "responsibles": ["Geysa", "Jam", "Fauzer", "Toda a Equipe"]
        },
        {
            "phase_number": 4,
            "title": "Indicadores e Melhorias",
            "period": "Meses 4–6",
            "description": "Metas comerciais estruturadas, custos por empresa, análise de rentabilidade, automações de processos e orçamento por departamento.",
            "status": "Planejada",
            "progress_percent": 0,
            "start_date": "Mês 4",
            "end_date": "Mês 6",
            "notes": "Avanço para maturidade corporativa após os controles fundamentais estarem consolidados.",
            "tasks": [
                {"title": "Metas Comerciais Estruturadas", "responsible": "Comercial / Geysa", "done": False, "detail": "Metas de vendas no atacado e varejo com acompanhamento em tempo real."},
                {"title": "Análise de Rentabilidade por Canal", "responsible": "Jam / Geysa", "done": False, "detail": "Apuração de margens líquidas reais de Varejo, Outlet e Atacado CNPJ."},
                {"title": "Automações Avançadas de Processos", "responsible": "Fauzer", "done": False, "detail": "Integrações M-One com Bling ERP, notificações e eliminação de burocracias manuais."},
                {"title": "Orçamento por Departamento", "responsible": "Jam / Geysa", "done": False, "detail": "Fixação de limites de despesas operacionais por centro de custo."}
            ],
            "responsibles": ["Jam", "Geysa", "Fauzer", "Comercial"]
        }
    ]


def get_team_members_data() -> List[Dict[str, Any]]:
    """Retorna os dados oficiais e atribuições práticas dos 11 profissionais da MAJ."""
    return [
        {
            "name": "Jam",
            "role": "Administrador / Proprietário",
            "area": "Direção Executiva & Estratégia",
            "avatar_icon": "👑",
            "badge": "DIREÇÃO GERAL",
            "badge_color": "gold",
            "responsibilities": [
                "Definição estratégica e decisões finais da MAJ Mobilidade",
                "Aprovação e validação dos novos procedimentos e manuais operacionais",
                "Compras internacionais e nacionais de mercadorias para revenda",
                "Aprovação exclusiva de despesas operacionais superiores a R$ 5.000",
                "Análise dos relatórios gerenciais e acompanhamento dos resultados corporativos"
            ],
            "limits": "Não deve ser acionado para autorizações operacionais abaixo de R$ 5.000 ou rotinas de execução que competem à gerência."
        },
        {
            "name": "Geysa",
            "role": "Gerente Geral",
            "area": "Gestão Operacional, Comercial & DP",
            "avatar_icon": "⭐",
            "badge": "GERÊNCIA GERAL",
            "badge_color": "blue",
            "responsibilities": [
                "Liderança e supervisão direta de toda a operação (Vendas, Oficina, Estoque, Financeiro)",
                "Autoridade e alçada para aprovar despesas operacionais rotineiras até R$ 5.000",
                "Acompanhamento da rotina financeira e cobrança com Marisa",
                "Supervisão dos atendimentos comerciais e pós-vendas com Ricardo",
                "Gestão de DP/RH (integração, medicina do trabalho, plano de saúde e contabilidade)",
                "Condução das reuniões semanais de gestão com atas e metas"
            ],
            "limits": "Não aprova compras de mercadorias para revenda nem despesas acima de R$ 5.000 (competência de Jam); não faz redigitação operacional."
        },
        {
            "name": "Fauzer",
            "role": "Assistente do Jam / Sistemas & Processos",
            "area": "Processos, Treinamento & Tecnologia",
            "avatar_icon": "⚡",
            "badge": "SISTEMAS & PROCESSOS",
            "badge_color": "purple",
            "responsibilities": [
                "Treinamento remoto da equipe sobre processos, rotinas e ferramentas",
                "Acompanhamento do cumprimento dos procedimentos e cobrança de entregas",
                "Identificação de falhas nos fluxos e proposição de melhorias práticas",
                "Gestão e evolução das plataformas e sistemas (M-One, Bling, materiais visuais)",
                "Suporte ao Jam na consolidação de dados e acompanhamento da implantação"
            ],
            "limits": "Não faz retrabalho de digitação manual de dados que competem aos colaboradores; não trata questões disciplinares/pessoais (competência de Geysa)."
        },
        {
            "name": "Marisa",
            "role": "Assistente Administrativo / Financeiro",
            "area": "Administrativo & Financeiro",
            "avatar_icon": "💰",
            "badge": "FINANCEIRO",
            "badge_color": "green",
            "responsibilities": [
                "Fechamento diário do caixa das operações",
                "Controle e lançamento rigoroso de contas a pagar e contas a receber",
                "Emissão de notas fiscais, boletos e conciliação bancária no Bling",
                "Registro de todas as despesas autorizadas na planilha/sistema",
                "Relatórios de inadimplência e suporte nos recebimentos para Geysa"
            ],
            "limits": "Não autoriza despesas ou descontos extraordinários sem aprovação; não mantém planilhas paralelas concorrentes ao Bling/M-One."
        },
        {
            "name": "Jhon",
            "role": "Assistente Administrativo / Estoque",
            "area": "Estoque & Expedição",
            "avatar_icon": "📦",
            "badge": "ESTOQUE & LOGÍSTICA",
            "badge_color": "amber",
            "responsibilities": [
                "Inventários rotativos semanais obrigatórios nos 2 galpões (M-One e MAJ Antiga)",
                "Conferência física rigorosa no recebimento de cargas e contêineres",
                "Dupla conferência na expedição de mercadorias antes do embarque",
                "Comparação das quantidades físicas com os saldos do Bling e registro de divergências",
                "Organização física dos depósitos e identificação visual dos lotes"
            ],
            "limits": "Não pode adiar inventários semanais; não realiza ajustes manuais ou baixas de estoque sem prévia autorização da Direção."
        },
        {
            "name": "Ricardo",
            "role": "Gerente de Oficina e Pós-Vendas",
            "area": "Oficina Técnica & Pós-Vendas",
            "avatar_icon": "🔧",
            "badge": "OFICINA & PÓS-VENDAS",
            "badge_color": "cyan",
            "responsibilities": [
                "Gestão diária da oficina técnica (unidade Consolação)",
                "Abertura, atualização de status e fechamento obrigatório de todas as Ordens de Serviço (OS) no Bling",
                "Controle rigoroso de prazos de atendimento, garantias e revisões preventivas",
                "Atendimento ao cliente para esclarecimentos técnicos e pós-venda, sob orientação de Geysa",
                "Requisição organizada de peças de reposição e controle de ferramentas"
            ],
            "limits": "Não libera nenhum veículo ou serviço sem OS aberta no sistema; não autoriza garantias fora da política oficial sem consulta prévia."
        },
        {
            "name": "Leo",
            "role": "Vendas & Atendimento Comercial",
            "area": "Comercial (Vendas & Atendimento)",
            "avatar_icon": "💼",
            "badge": "VENDAS & ATENDIMENTO",
            "badge_color": "emerald",
            "responsibilities": [
                "Vendas ativas e atendimento tanto no Atacado quanto no Varejo",
                "Apoio em rotinas comerciais, demonstração técnica de veículos e prospecção",
                "Cumprimento das metas de vendas e registro completo dos pedidos no Bling",
                "Consulta obrigatória de chassi liberado no M-One antes de fechar qualquer pedido"
            ],
            "limits": "Não concede descontos fora das tabelas oficiais de Outlet ou Atacado sem autorização da Direção."
        },
        {
            "name": "Luiza",
            "role": "Vendedora Comercial",
            "area": "Comercial (Atacado & Varejo)",
            "avatar_icon": "🛍️",
            "badge": "COMERCIAL",
            "badge_color": "emerald",
            "responsibilities": [
                "Atendimento receptivo e ativo de clientes de atacado e varejo",
                "Elaboração de orçamentos, negociações conforme tabela e emissão de pedidos",
                "Follow-up de propostas comerciais e pós-venda inicial de relacionamento",
                "Registro dos dados dos clientes para formação de carteira corporativa"
            ],
            "limits": "Não negocia prazos ou condições de pagamento fora das regras homologadas pela gerência."
        },
        {
            "name": "Gabriel",
            "role": "Vendedor Comercial",
            "area": "Comercial (Atacado & Varejo)",
            "avatar_icon": "🚀",
            "badge": "COMERCIAL",
            "badge_color": "emerald",
            "responsibilities": [
                "Prospecção ativa de novos clientes e lojistas de mobilidade elétrica",
                "Apresentação do catálogo MAJ Atacado CNPJ e esclarecimento de especificações",
                "Acompanhamento de cotações de frete via M-One e fechamento de vendas",
                "Cumprimento de metas comerciais estabelecidas nas reuniões semanais"
            ],
            "limits": "Não formaliza prazos de entrega ao cliente sem validação com a expedição e estoque."
        },
        {
            "name": "Leandro",
            "role": "Mecânico Especialista",
            "area": "Oficina Técnica",
            "avatar_icon": "🛠️",
            "badge": "MECÂNICA",
            "badge_color": "slate",
            "responsibilities": [
                "Montagem, revisão de entrega (PDI) e checklists de veículos novos",
                "Diagnóstico e manutenção preventiva e corretiva mecânica e estrutural",
                "Cumprimento dos procedimentos técnicos e preenchimento dos laudos da OS",
                "Preservação de ferramentas e organização da bancada de trabalho"
            ],
            "limits": "Não executa serviços sem a respectiva OS aberta por Ricardo; não descarta peças substituídas sem inspeção."
        },
        {
            "name": "Rafael",
            "role": "Mecânico Especialista",
            "area": "Oficina Técnica",
            "avatar_icon": "⚙️",
            "badge": "ELÉTRICA & MECÂNICA",
            "badge_color": "slate",
            "responsibilities": [
                "Diagnóstico e reparo elétrico (baterias, controladores, motores brushless e chicotes)",
                "Montagem de modelos especiais e testes dinâmicos de rodagem e segurança",
                "Registro de tempo de serviço e peças aplicadas na OS",
                "Cumprimento das normas de segurança e uso de EPIs na oficina"
            ],
            "limits": "Não libera veículos para entrega sem o teste final e assinatura do checklist de qualidade."
        }
    ]


def get_departments_data() -> List[Dict[str, Any]]:
    """Retorna o diagnóstico e as diretrizes por departamento da MAJ."""
    return [
        {
            "name": "Financeiro",
            "lead": "Marisa / Supervisão Geysa",
            "complexity": "Alta",
            "status_color": "green",
            "diagnosis": "Controles manuais em transição para o Bling. Necessidade de rotina diária sem acúmulo de notas e extratos.",
            "rules": [
                "Fechamento de caixa obrigatório até às 18h de cada dia útil",
                "Lançamento de todas as despesas imediatamente após a autorização",
                "Conciliação bancária diária comparando extratos com o Bling"
            ]
        },
        {
            "name": "Estoque & Galpões",
            "lead": "Jhon / Supervisão Geysa",
            "complexity": "Alta",
            "status_color": "amber",
            "diagnosis": "Estoque dividido em 2 galpões (M-One e MAJ Antiga). Risco de divergências sem inventários periódicos.",
            "rules": [
                "Inventário rotativo semanal obrigatório (sem permitir nenhuma semana sem contagem)",
                "Dupla conferência na expedição de mercadorias",
                "Toda entrada de mercadoria conferida física e fiscalmente no ato do descarregamento"
            ]
        },
        {
            "name": "Oficina Técnica",
            "lead": "Ricardo / Apoio Leandro e Rafael",
            "complexity": "Média",
            "status_color": "cyan",
            "diagnosis": "Unidade Consolação operando com OS no Bling, mas com oportunidade de melhoria no controle de prazos.",
            "rules": [
                "Nenhum veículo entra ou sai sem Ordem de Serviço (OS) formal no Bling",
                "Checklist de inspeção obrigatório na entrada e na liberação do cliente",
                "Controle de garantia com retenção das peças substituídas para análise"
            ]
        },
        {
            "name": "Comercial & Vendas",
            "lead": "Leo, Luiza, Gabriel / Gestão Geysa",
            "complexity": "Média",
            "status_color": "emerald",
            "diagnosis": "Atuação mista em atacado e varejo. Necessidade de metas formais e uso padronizado do M-One.",
            "rules": [
                "Toda venda exige chassi existente, liberado (available) e não duplicado",
                "Proibido conceder descontos fora das regras oficiais de Outlet e Atacado",
                "Acompanhamento semanal de orçamentos e conversão de propostas"
            ]
        },
        {
            "name": "Recursos Humanos & DP",
            "lead": "Geysa / Apoio Fauzer e Jam",
            "complexity": "Alta",
            "status_color": "purple",
            "diagnosis": "Ausência de processo formal de onboarding e treinamento. Aprendizado acontecia apenas por observação.",
            "rules": [
                "Programa de Integração MAJ (1º dia, 1ª semana, 30 e 90 dias)",
                "Avaliações formais de experiência nos marcos de 45 e 90 dias",
                "Reuniões de alinhamento com atas de decisões e prazos"
            ]
        },
        {
            "name": "Tecnologia & Governança",
            "lead": "Fauzer / Decisão Jam",
            "complexity": "Média",
            "status_color": "gold",
            "diagnosis": "Sistemas robustos (M-One, Bling, Google Sheets), necessitando de padronização anti-retrabalho.",
            "rules": [
                "Regra de Ouro: dados cadastrados uma única vez na fonte canônica",
                "Alçadas: Geysa autoriza até R$ 5.000; Jam autoriza acima de R$ 5.000 e compras de revenda",
                "Fauzer atua no acompanhamento e treinamento, sem retrabalho manual"
            ]
        }
    ]
