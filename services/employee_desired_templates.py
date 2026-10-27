"""
M-One Employee Desired Answers Templates (services/employee_desired_templates.py)
Define os padrões ouro (respostas desejadas / expectativas de excelência)
extraídos das cartilhas oficiais de função da MAJ Mobilidade.
Utilizado como gabarito base pré-carregado nos modais de aferição da Diretoria.
"""

from __future__ import annotations
from typing import Dict, Optional

DEFAULT_DESIRED_ANSWERS: Dict[str, Dict[str, str]] = {
    "marisa": {
        "faturamento_nfs": (
            "Relato detalhado do faturamento semanal discriminando NFs de atacado B2B, vendas de balcão e saídas especiais. "
            "Todas as notas fiscais emitidas no Bling devem estar sincronizadas sem divergência fiscal e com CFOP correto."
        ),
        "entradas_pendentes": (
            "Conferência diária do caixa físico e conciliação integral com os comprovantes repassados por Jhon. "
            "Discriminação exata de valores a receber com vencimento na semana e saldo em aberto com justificativa."
        ),
        "contas_vencimentos": (
            "Todas as contas a pagar da semana seguinte (fornecedores, impostos, concessionárias e aluguel) organizadas "
            "com 48h de antecedência em planilha/pasta física e repassadas para autorização e pagamento de Geysa."
        ),
        "docs_faltantes": (
            "Cobrança ativa e lista nominal de fornecedores, despachantes ou prestadores de serviço com NFs pendentes de envio. "
            "Meta: zero notas fiscais ou boletos retidos sem entrada no sistema fiscal."
        ),
        "recibos_pendentes": (
            "Conferência e arquivamento dos canhotos de NFs e checklists assinados pelo cliente e trazidos pelo motorista. "
            "Nenhuma entrega de veículo pode permanecer sem recibo assinado por mais de 24h após a expedição."
        ),
        "piloto_mercado_pago": (
            "Relatório de conciliação do Mercado Pago: total bruto transacionado, taxas percentuais descontadas, "
            "antecipações realizadas e confirmação do valor líquido creditado na conta bancária da MAJ."
        ),
        "prioridades_proxima_semana": (
            "Cronograma de vencimentos críticos da semana seguinte, previsão de fechamento de folha/impostos "
            "e pontos de atenção que necessitam de intervenção ou aprovação prévia de Geysa e Jam."
        ),
    },
    "jhon": {
        "contagem_rotativa": (
            "Contagem física presencial realizada rigorosamente na sexta-feira à tarde. Apresentação dos números exatos "
            "de unidades estocadas no Galpão MAJ e no Galpão COLVIX / M-One por modelo (ex: Falcon, Chopper, Scooters)."
        ),
        "divergencias": (
            "Zero divergências não explicadas. Se houver diferença entre a contagem física e o saldo do sistema/Bling, "
            "apresentar o chassi específico, a causa raiz investigada e a correção imediata já solicitada."
        ),
        "nfs_demonstracao": (
            "100% dos veículos em exposição no Showroom e nas áreas comuns com NFs de demonstração impressas, plastificadas "
            "e visíveis. Identificação e renovação preventiva das notas com prazo de validade próximo ao vencimento."
        ),
        "movimentacoes_localizacao": (
            "Registro de todas as transferências entre galpões com checklist de movimentação. Veículos organizados por lotes, "
            "com separação clara entre lotes promocionais de desova do Outlet e veículos de atacado B2B de pronta entrega."
        ),
        "codigo_barras": (
            "Status da etiquetagem e leitura ótica dos chassis e embalagens de peças. Todos os veículos recebidos devem estar "
            "etiquetados e conferidos via leitor de código de barras para acelerar expedições."
        ),
        "despesas_saidas": (
            "Prestação de contas das despesas miúdas de suprimentos do galpão (fita, plástico bolha, ferramentas) fechada "
            "diariamente com Marisa, com comprovantes fiscais anexados e saldo conferido."
        ),
        "prioridades_proxima_semana": (
            "Planejamento de espaço físico para recebimento de contêineres previstos, organização de paletes para expedições "
            "pesadas de atacado e requisição de insumos de embalagem antes que o estoque zere."
        ),
    },
    "ricardo": {
        "servicos_concluidos": (
            "Lista consolidada de todas as revisões de entrega (PDI) realizadas, motos montadas para pronta entrega e OS de clientes "
            "concluídas com checklist de qualidade assinado e baixa imediata no sistema de oficina."
        ),
        "os_pendentes": (
            "Mapeamento claro de veículos retidos na oficina: motivo exato de cada OS aberta (peça em falta, aguardando aprovação "
            "de orçamento pelo cliente ou diagnóstico complexo) e prazo limite estimado para liberação."
        ),
        "retrabalhos": (
            "Zero retrabalhos por descuido de montagem ou falta de aperto de parafusos/chicote. Relato transparente de qualquer "
            "retorno de cliente na garantia com ação preventiva adotada no processo da bancada."
        ),
        "diagnosticos_complexos": (
            "Registro técnico de falhas elétricas intermitentes, testes de baterias de lítio, controladores ou motores. "
            "Compartilhamento da solução encontrada para alimentar a base de conhecimento técnico da MAJ."
        ),
        "defeitos_recorrentes": (
            "Identificação de padrões de falhas de componentes de fábrica (ex: manetes, chicotes, módulos) para embasar "
            "a cobrança de garantia do fornecedor internacional ou ajuste na montagem inicial."
        ),
        "necessidade_pecas": (
            "Lista preventiva e codificada de peças de giro rápido com estoque baixo na oficina (pastilhas, cabos, pneus, chicotes) "
            "e ferramentas necessárias, enviada antes de gerar paralisação de serviços."
        ),
        "equipe_apoio": (
            "Distribuição equilibrada das tarefas técnicas para os mecânicos (Leandro e Rafael), mantendo o foco do gerente em "
            "supervisão de qualidade e liberação final, apoiado pelo motorista no translado de peças."
        ),
    },
    "luiza": {
        "modelos_procurados": (
            "Ranking dos 3 modelos de veículos e autopropelidos mais procurados pelos clientes que visitaram o showroom ou "
            "chamaram no canal de atendimento, detalhando os diferenciais valorizados pelos compradores."
        ),
        "objecoes_perdas": (
            "Mapeamento objetivo das principais objeções que travaram o fechamento (ex: valor da entrada, taxa do parcelamento no cartão, "
            "prazo de entrega de cor específica ou dúvidas sobre autonomia da bateria)."
        ),
        "precos_altos": (
            "Feedback realista dos clientes sobre percepção de preço frente à concorrência, identificando modelos que necessitam "
            "de condições promocionais especiais ou ativação de gatilhos do Outlet."
        ),
        "reclamacoes_elogios": (
            "Registro das impressões dos clientes quanto à recepção na loja, test-ride, clareza das explicações técnicas "
            "e eventuais pontos de atrito no processo de compra."
        ),
        "qualidade_bot": (
            "Avaliação do fluxo de triagem do BotConversa: se os leads chegam quentes e bem qualificados ou se clientes estão "
            "abandonando o fluxo por excesso de opções ou respostas demoradas."
        ),
        "conteudo_video": (
            "Indicação de qual veículo necessita urgentemente de material em vídeo (stories, reels de detalhes, demonstração de "
            "subida em ladeiras ou autonomia) para sanar dúvidas recorrentes e acelerar vendas."
        ),
        "sugestao_comercial": (
            "Proposta prática de ação de vendas para a semana (ex: brinde de capacete, condição de frete grátis local, combo de revisão "
            "ou campanha de fim de mês) para deliberação na reunião de segunda."
        ),
    },
    "leo": {
        "os_da_semana": (
            "Métricas exatas de atendimento pós-venda: total de OS abertas na semana, total concluídas pela oficina e saldo "
            "em aberto, garantindo que nenhum cliente fique sem número de protocolo ou status atualizado."
        ),
        "atrasos_servicos": (
            "Acompanhamento proativo de serviços com previsão estourada. Todos os clientes com serviços atrasados devem ter sido "
            "contactados preventivamente antes de cobrarem a loja, com nova data acordada."
        ),
        "clientes_sensiveis": (
            "Relato detalhado de casos sensíveis, clientes com mais de 2 visitas na garantia ou risco de reclamação externa/jurídica, "
            "com histórico completo e plano de contenção alinhado com Geysa."
        ),
        "orcamentos_oficina": (
            "Status dos orçamentos de serviços e peças enviados para clientes: percentual de aprovação, valores totais orçados "
            "e follow-up ativo nos orçamentos pendentes de resposta há mais de 48 horas."
        ),
        "garantia_triagem": (
            "Triagem rigorosa das solicitações de garantia com fotos/vídeos e número do chassi antes do envio para a oficina técnica, "
            "evitando ocupação desnecessária dos mecânicos com casos fora de garantia."
        ),
        "concessoes_semana": (
            "Prestação de contas de qualquer cortesia, desconto ou benefício concedido a clientes, respeitando estritamente a "
            "alçada autorizada pela Diretoria e registrando os motivos."
        ),
        "pagamentos_oficina": (
            "Controle rigoroso dos recebimentos de serviços da oficina: confirmação de que nenhum veículo foi liberado sem o devido "
            "comprovante de pagamento validado junto à Marisa."
        ),
        "pendencias_decisao": (
            "Lista enxuta de 1 a 3 casos de pós-venda complexos que exigem decisão direta de Jam e Geysa na reunião de segunda-feira "
            "(ex: substituição de peça onerosa em garantia ou acordo especial)."
        ),
    },
    "gabriel": {
        "prospeccao": (
            "Mapeamento quantitativo e qualitativo de novos contatos iniciados na semana com lojistas e revendas (Pessoa Jurídica), "
            "identificando o segmento e as reais oportunidades de negócios."
        ),
        "follow_up": (
            "Acompanhamento ativo e constante da carteira de lojistas ativos e antigos, destacando negociações quentes em "
            "andamento com potencial e previsão clara de fechamento."
        ),
        "fechamentos": (
            "Demonstrativo dos pedidos fechados na semana (modelos como Max 12, GP1000, Vittoria e bikes V80), com alinhamento "
            "imediato junto à Marisa para controle de faturamento e notas fiscais."
        ),
        "objecoes_atacado": (
            "Registro detalhado das principais barreiras dos revendedores (preço, frete, prazo ou concorrência desleal nos modelos "
            "Max 12 e V20 Ultra) e proposição de alternativas para destravar pedidos."
        ),
        "sinais_mercado": (
            "Leitura do comportamento do mercado atacadista: modelos mais procurados, produtos com menor giro e monitoramento "
            "de movimentações de preços e promoções da concorrência."
        ),
        "pendencias_direcao": (
            "Pauta executiva de pendências para deliberação de Jam e Geysa, com cumprimento rigoroso da regra técnica "
            "(não emitir diagnósticos técnicos) e alinhamento de emissão de NF de comissão de 1%."
        ),
    },
    "fauzer": {
        "marketing_investimento": (
            "Demonstrativo do investimento semanal em tráfego pago (Meta Ads / Google Ads), CPL apurado por canal, volume de leads "
            "gerados, taxa de conversão do comercial e direcionamento dos melhores criativos."
        ),
        "processos_sistemas": (
            "Evolução das entregas técnicas no M-One, integrações automatizadas (Bling ERP, Mercado Pago, BotConversa), "
            "manutenção de estabilidade dos servidores Vercel/Supabase e governança de dados."
        ),
        "falhas_desvios": (
            "Mapeamento de falhas de processo ocorridas na operação (ex: omissão de checklists, falha de conferência de chassi, "
            "ruídos de comunicação) com a proposta de melhoria sistêmica correspondente."
        ),
        "treinamentos_alinhamentos": (
            "Sessões de alinhamento com a equipe sobre o uso do M-One, conscientização das rotinas de preenchimento dos relatórios "
            "semanais e acompanhamento do nível de adoção das ferramentas."
        ),
        "pontos_decisao_diretoria": (
            "Pauta executiva direta para a reunião de 20-30 minutos com Jam Penitenti e Geysa: deliberações de investimento, "
            "ajustes de cartilhas de funções e aprovações estratégicas necessárias."
        ),
    },
}


def get_default_desired_answer(employee_key: str, question_id: str) -> str:
    """Retorna a resposta desejada padrão para um colaborador e pergunta específicos."""
    emp_map = DEFAULT_DESIRED_ANSWERS.get((employee_key or "").strip().lower(), {})
    return emp_map.get(question_id, "Padrão de excelência operacional conforme a cartilha de funções oficial.")


def get_employee_default_desired_map(employee_key: str) -> Dict[str, str]:
    """Retorna o dicionário completo com todas as respostas desejadas padrão do colaborador."""
    return dict(DEFAULT_DESIRED_ANSWERS.get((employee_key or "").strip().lower(), {}))
