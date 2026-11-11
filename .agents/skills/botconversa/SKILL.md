---
name: botconversa
description: Integração oficial do BotConversa (MCP e API) para automações de WhatsApp na MAJ Mobilidade. Permite consultar contatos/leads por telefone, listar fluxos e tags, aplicar etiquetas de vendas/chassi, inscrever contatos em fluxos (Follow-Up Atacado, Outlet, Black Friday) e auditar conversas e funis.
---

# Skill BotConversa — Inteligência & Automação de WhatsApp (MAJ Mobilidade)

Esta skill capacita o agente a interagir de ponta a ponta com a plataforma **BotConversa** da MAJ Mobilidade, unindo os dados do WhatsApp aos módulos do **M-One** (banco Supabase, estoque de chassis, faturas de importação e pedidos Bling).

---

## 🛠️ Comandos Operacionais da Ferramenta (`scripts/botconversa_tool.py`)

O agente pode executar comandos diretos no terminal usando o interpretador do ambiente virtual:

### 1. Consultar Contato / Lead por Telefone
Busca os dados cadastrais, ID do assinante, etiquetas ativas e variáveis customizadas do lead (ex: `ResumoTriagemMAJ`, `Resposta_Catalogo`):
```bash
.venv/bin/python3 scripts/botconversa_tool.py get-contact --phone "27999998888"
```

### 2. Listar Todas as Etiquetas (Tags)
Lista todas as 70+ tags cadastradas no BotConversa com seus IDs:
```bash
.venv/bin/python3 scripts/botconversa_tool.py list-tags
```

### 3. Listar Fluxos de Automação
Lista todos os fluxos de conversa ativos na plataforma (ex: *Folow-up Outlet*, *Fluxo Prospecção Atacado*, *FLUXO OUTLET BLACK NOVEMBER*):
```bash
.venv/bin/python3 scripts/botconversa_tool.py list-flows
```

### 4. Aplicar Etiqueta ao Contato
Aplica uma etiqueta ao contato pelo ID numérico do contato e pelo nome ou ID da tag:
```bash
.venv/bin/python3 scripts/botconversa_tool.py add-tag --subscriber-id <ID> --tag "ATACADO_11+"
```

### 5. Remover Etiqueta do Contato
Remove uma etiqueta do contato:
```bash
.venv/bin/python3 scripts/botconversa_tool.py remove-tag --subscriber-id <ID> --tag "Não_respondeu"
```

### 6. Disparar / Inscrever Contato em um Fluxo
Inscreve o contato em um fluxo de atendimento pelo nome ou ID do fluxo:
```bash
.venv/bin/python3 scripts/botconversa_tool.py send-flow --subscriber-id <ID> --flow "Folow-up Outlet"
```

### 7. Enviar Mensagem Direta de Texto
Envia uma mensagem de texto rápida e pontual para o contato:
```bash
.venv/bin/python3 scripts/botconversa_tool.py send-message --subscriber-id <ID> --text "Olá! Aqui é da MAJ Mobilidade..."
```

### 8. Transbordo Automático Multicanal (Instagram -> WhatsApp)
Quando o lead informa o número no Instagram Direct, cadastra/localiza o contato, aplica as tags reais da MAJ (`VAREJO-INTERESSE` ou `atacado_revenda` + modelo) e dispara o fluxo rotativo do vendedor:
```bash
.venv/bin/python3 scripts/botconversa_tool.py onboard-lead --phone "27999998888" --name "Cliente Teste" --segment varejo --model "V20"
```

---

## 🛡️ Diretrizes de Segurança & Boas Práticas

1. **Aprovação Prévia para Disparos em Massa**: Nunca disparar fluxos ou mensagens para mais de 5 contatos simultaneamente sem confirmação prévia do usuário.
2. **Preservação de Dados de Clientes**: Nunca remover tags de vendedores (`Atacado_jose_gabriel`, `Varejo_Leonardo`) sem motivo operacional explícito.
3. **Casamento com Estoque Real**: Antes de recomendar modelos ou disparar ofertas, conferir no M-One a disponibilidade de chassis em `/stock` ou na tabela `chassis`.
