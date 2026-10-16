# 🏍️ Plano de Replicagem — Showroom MAJ Mobilidade

> **Documento Oficial de Handover e Continuidade Operacional**  
> Destinado ao desenvolvedor/operador que assumirá a continuidade da criação e ativação dos modelos no Showroom MAJ (`/show-room/<slug>`).

---

## ⚡ 1. Como Iniciar os Trabalhos (Passo Zero)

Ao abrir o projeto no chat do Antigravity / IDE, execute imediatamente:

```text
[start]
```

O agente executará o **Protocolo START**:
1. `git fetch origin` e análise de sincronização com o repositório remoto.
2. Inicialização do servidor local na porta `5001` (`http://localhost:5001`).
3. Auditoria anti-monólito (`scripts/monolith_watcher.py --scan`).

Em seguida, basta digitar no chat:
> *"Continuar o Plano de Replicagem e Modelos para o modelo [NOME DO MODELO]"* (Ex: *"Continuar com o FLOW ONE"*).

---

## 🚨 2. ATENÇÃO CRÍTICA: Resolução da Foto Hero (Topo Widescreen)

> [!CAUTION]
> **NUNCA COLE OU ARRASTE A IMAGEM DO HERO DIRETAMENTE NA JANELA DO CHAT!**  
> A interface web do chat reduz automaticamente qualquer imagem colada para `1024 × 576 pixels`, o que resulta em um banner borrado e pixelado na tela do cliente.

### ✅ O Procedimento Correto (Apontar o Arquivo no Computador):
1. **Onde estão os arquivos masters em 2K (2560 × 1440):**  
   Os arquivos de estúdio oficiais de alta definição ficam na pasta do Google Drive sincronizada no Mac:  
   📂 **`/Users/macstudio-maj/Library/CloudStorage/GoogleDrive-marketingmajv@gmail.com/Meu Drive/M-ONE/SITE- MODELOS/OUT/`**  
   *(Exemplos já existentes lá: `FLOW ONE - topo 2k.jpeg`, `GP100 - topo 2k.png`, `MAX 12 MAJ - topo 2k.png`)*.
2. **Se você exportou uma nova arte (Photoshop / Canva / Figma):**  
   * Exporte em **`2560 × 1440 pixels`** (proporção 16:9 Widescreen).
   * Salve na pasta acima ou na sua **Mesa (Desktop)**: `/Users/macstudio-maj/Desktop/nome_do_modelo.png`.
3. **No Chat:**  
   Apenas forneça o caminho do arquivo para o agente. Exemplo:  
   > *"O banner 2K do FLOW ONE está em: `/Users/macstudio-maj/Library/CloudStorage/GoogleDrive-marketingmajv@gmail.com/Meu Drive/M-ONE/SITE- MODELOS/OUT/FLOW ONE - topo 2k.jpeg`"*

O agente usará o Python/Pillow para ler o arquivo original sem compressão, gerando o WebP otimizado de altíssima fidelidade.

---

## 📊 3. Status Consolidado do Catálogo

| Modelo | Slug | Categoria | Banner Hero 2K | Galeria de Fotos | Status Showroom |
| :--- | :--- | :--- | :---: | :---: | :---: |
| **MAX 12 MAJ** | `max-12` | Scooter | ✅ Ativo (2560x1440) | ✅ 8 fotos estúdio | 🟢 **100% Concluído & Em Produção** |
| **GP 1000** | `gp-1000` | Scooter | ✅ Ativo (2560x1440) | ✅ 8 fotos estúdio | 🟢 **100% Concluído & Em Produção** |
| **FLOW ONE** | `flow-one` | Scooter | ✅ Ativo (2560x1440) | ✅ 8 fotos estúdio | 🟢 **100% Concluído & Em Produção** |
| **CLASSIC 1000** | `classic-1000` | Scooter | ✅ Ativo (2560x1440) | ✅ 8 fotos estúdio | 🟢 **100% Concluído & Em Produção** |
| **DB-ZERO** | `db-zero` | Scooter | ✅ Ativo (2560x1440) | ✅ 6 fotos estúdio | 🟢 **100% Concluído & Em Produção** |
| **VITTÓRIA** | `vittoria` | Scooter | ✅ Ativo (2560x1440) | ✅ 8 fotos estúdio | 🟢 **100% Concluído & Em Produção** |
| **NOVA** | `nova` | Scooter | ✅ Ativo (2560x1440) | ✅ 8 fotos estúdio | 🟢 **100% Concluído & Em Produção** |
| **RIDE ON** | `ride-on` | Scooter | ✅ Ativo (2560x1440) | ✅ 8 fotos estúdio | 🟢 **100% Concluído & Em Produção** |
| **M2** | `m2` | Scooter | ✅ Ativo (2560x1440) | ✅ 8 fotos estúdio | 🟢 **100% Concluído & Em Produção** |
| **M9 PRO** | `m9-pro` | Bike | ✅ Ativo (2560x1440) | ✅ 8 fotos estúdio | 🟢 **100% Concluído & Em Produção** |
| **V20 ULTRA** | `v20-ultra` | Bike | ✅ Ativo (2560x1440 R1) | ✅ 7 fotos estúdio (M9 PRO removida) | 🟢 **100% Concluído & Em Produção** |
| **V8 MINI ULTRA**| `v8-mini` | Bike | ✅ Ativo (2560x1440) | ✅ 8 fotos estúdio | 🟢 **100% Concluído & Em Produção** |
| **RZ 110** | `rz-110` | Scooter | ✅ Ativo (2560x1440) | ✅ 8 fotos estúdio | 🟢 **100% Concluído & Em Produção** |
| **M50 PRO** | `m50-pro` | Bike | ⏳ Imagem 2K disponível no Drive | ✅ 5 fotos prontas | 🎯 **Próximo da Fila** |
| **SPORT 701 SHORT**| `sport-701-short`| Scooter | — | — | 🚫 **Oculto do Menu (Inativo)** |
| **V80 PRO** | `v80-pro` | Bike | — | — | 🚫 **Oculto do Menu (Inativo)** |
| **X15 PRO** | `x15-pro` | Scooter | ⏳ Aguardando apontamento | ✅ 8 fotos prontas | 📋 Aguardando banner |
| **JM 125** | `jm-125` | Moto | ⏳ Aguardando apontamento | ✅ 8 fotos prontas | 📋 Aguardando banner |
| **MANTIS** | `mantis` | Scooter | ⏳ Aguardando apontamento | ✅ 8 fotos prontas | 📋 Aguardando banner |
| **Q8** | `q8` | Bike | ⏳ Aguardando apontamento | ✅ 8 fotos prontas | 📋 Aguardando banner |

---

## 🛠️ 4. Fluxo Passo a Passo para Replicar Cada Novo Modelo

Sempre que for iniciar a replicação de um novo modelo, siga exatamente este roteiro:

### Passo 1 — Fazer o Diagnóstico de Assets do Modelo
1. **Verificar se a pasta de fotos já existe:**
   As fotos de estúdio ficam em `public/images/<slug>/` (ex: `public/images/flow-one/`).
2. **Verificar se o modelo consta no Google Sheets ou precisa ser suplementar:**
   * Modelos padrão do Sheets: Já estão mapeados em `services/maj_models_sync_service.py` (`SLUG_ALIASES`).
   * Modelos adicionais (como GP 1000): São cadastrados em `static/data/supplemental_models.json`.
3. **Solicitar ao usuário / operador:**
   * *"Onde está o arquivo do banner 2K no seu computador/Google Drive?"*
   * *"Confirmar dados da bateria: Voltagem (ex: 60V ou 48V), Ah (ex: 20Ah) e Wh (ex: 1200Wh)."*

---

### Passo 2 — Processar e Otimizar o Banner 2K
O agente deve executar o script Python para converter o master original para WebP 2560x1440 (alta fidelidade e peso leve):

```python
import shutil, os
from PIL import Image

src = "/caminho/informado/pelo/usuario.png" # ou .jpeg
slug = "slug-do-modelo" # ex: flow-one

dest_orig = f"public/images/models/banners/{slug}-original.png"
dest_webp_2k = f"public/images/models/banners/{slug}-banner.webp"
dest_webp_hd = f"public/images/models/banners/{slug}-banner-2x.webp"

shutil.copyfile(src, dest_orig)
img = Image.open(src)
img_rgb = img.convert("RGB")

# 2560x1440 QHD nativo
res_2k = img_rgb.resize((2560, 1440), Image.Resampling.LANCZOS)
res_2k.save(dest_webp_2k, "WEBP", quality=92, method=6)

# 2048x1152 HD
res_hd = img_rgb.resize((2048, 1152), Image.Resampling.LANCZOS)
res_hd.save(dest_webp_hd, "WEBP", quality=90, method=6)

# Sincronizar pastas estáticas
for sub in ["api/static/img/models/banners", "static/img/models/banners", "static/images/models/banners"]:
    os.makedirs(sub, exist_ok=True)
    shutil.copyfile(dest_webp_2k, f"{sub}/{slug}-banner.webp")
    shutil.copyfile(dest_webp_hd, f"{sub}/{slug}-banner-2x.webp")
```

---

### Passo 3 — Cadastrar o Banner no Frontend
Atualizar o dicionário `banner_lookup` e `bannerMap` para o novo slug:

1. **Em `templates/showroom/models.html`:**
   ```jinja2
   {% set banner_lookup = {
     'max-12': '/public/images/models/banners/max-12-banner.webp',
     'gp-1000': '/public/images/models/banners/gp-1000-banner.webp',
     'flow-one': '/public/images/models/banners/flow-one-banner.webp'
   } %}
   ```
2. **Em `static/js/showroom.js`:**
   ```javascript
   const bannerMap = {
     'max-12': '/public/images/models/banners/max-12-banner.webp',
     'gp-1000': '/public/images/models/banners/gp-1000-banner.webp',
     'flow-one': '/public/images/models/banners/flow-one-banner.webp'
   };
   ```

---

### Passo 4 — Garantir Paridade Vercel (`api/`)
Sempre execute a cópia de sincronização para a Vercel:

```bash
cp templates/showroom/models.html api/templates/models.html
cp static/js/showroom.js api/static/js/showroom.js
cp static/data/maj_models.json api/static/data/maj_models.json
cp static/data/supplemental_models.json api/static/data/supplemental_models.json 2>/dev/null || true
```

---

### Passo 5 — Auditoria de Regras Inegociáveis
Antes de mostrar ao usuário, o agente **DEVE EXECUTAR**:
1. **Auditoria Anti-Monólito:**
   ```bash
   .venv/bin/python3 scripts/monolith_watcher.py --scan
   ```
   *(Nenhum arquivo JS, template ou rota pode exceder 500 linhas. Atualmente `showroom.js` tem ~493 linhas e `models.html` tem ~440 linhas).*
2. **Validação Geral de Integridade:**
   ```bash
   .venv/bin/python3 scripts/validate.py
   ```
3. **Teste no Navegador:**
   Acessar `http://localhost:5001/show-room/<slug>` e conferir:
   * Banner 2K cristalino no topo
   * Pílula ativa no carrossel de modelos
   * Contadores do Cockpit Digital funcionando
   * Botão `Capacidade de Passageiros`
   * Bateria com `60v 20ah` (primário) e `1200 WH` (secundário) com texto `Bateria de Lítio`
   * Seção `GALERIA DE FOTOS` limpa com as fotos de estúdio (sem banners publicitários)

---

### Passo 6 — Publicação (Deploy)
Quando o operador aprovar o modelo, digite no chat:

```text
[deploy]
```

O agente executará a validação de 6 etapas, criará o commit, fará o push para o GitHub e testará a URL oficial da Vercel.

---

## 📌 5. Próximo Passo Imediato Recomendado: VITTÓRIA

O modelo **VITTÓRIA** é o próximo da fila:
* 📁 **Fotos de Estúdio:** `public/images/vittoria/` (8 fotos já disponíveis)
* ⚙️ **Especificações:** Motor 1000W, 32 km/h, 60V Lítio, acabamento elegante branco perolizado.
* 🎯 **Ação Necessária:** Apontar onde está o arquivo Hero Widescreen 2K no computador/Google Drive (pasta `Meu Drive/M-ONE/SITE- MODELOS/OUT/`).
