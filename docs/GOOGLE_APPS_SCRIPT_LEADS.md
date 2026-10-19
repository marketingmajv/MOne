# Script do Google Sheets para Receber Leads do M-One

Copie e cole o código abaixo no seu **Google Planilhas**:
1. Abra a sua planilha do Google Sheets.
2. No menu superior, clique em **Extensões** ➔ **Apps Script**.
3. Apague qualquer código existente no editor e cole o código abaixo.
4. Clique em **Implantar** ➔ **Nova implantação**.
5. Em tipo, selecione **App da Web** (ícone de engrenagem).
6. Configure:
   - **Executar como**: *Eu (seu e-mail)*
   - **Quem pode acessar**: *Qualquer pessoa*
7. Clique em **Implantar**, autorize os acessos e copie a **URL do App da Web**.
8. Cole essa URL no M-One na aba **Automação 24/7 & Integrações** do módulo de Prospecção!

---

```javascript
/**
 * Google Apps Script — Receptor Oficial de Leads M-One
 * Adiciona novos leads capturados e atualiza dados automaticamente.
 */
function doPost(e) {
  try {
    const rawData = e.postData.contents;
    const payload = JSON.parse(rawData);
    const leads = payload.leads || [];

    const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();

    // Se a planilha estiver vazia, cria o cabeçalho padronizado
    if (sheet.getLastRow() === 0) {
      sheet.appendRow([
        "ID M-One",
        "Data Captura",
        "Classe",
        "Score",
        "Empresa",
        "Decisor / Sócio",
        "Cargo Decisor",
        "Outros Sócios",
        "WhatsApp",
        "E-mail",
        "Nicho",
        "Cidade",
        "UF",
        "Endereço",
        "Site",
        "Instagram",
        "CNPJ",
        "Porte",
        "Raio-X (Resumo IA)",
        "Gancho Comercial de Abordagem",
        "Status do Contato",
        "Notas do Vendedor"
      ]);
      sheet.getRange(1, 1, 1, 22).setFontWeight("bold").setBackground("#0f172a").setFontColor("#38bdf8");
    }

    // Identificar IDs já presentes para evitar duplicatas
    const lastRow = sheet.getLastRow();
    const existingIds = lastRow > 1 ? sheet.getRange(2, 1, lastRow - 1, 1).getValues().flat().map(String) : [];

    leads.forEach(lead => {
      const idStr = String(lead.id);
      const rowIdx = existingIds.indexOf(idStr);

      const rowData = [
        idStr,
        lead.data_captura || "",
        lead.classe || "D",
        lead.score || 0,
        lead.empresa || "",
        lead.decisor || "",
        lead.decisor_cargo || "",
        lead.outros_socios || "",
        lead.whatsapp || "",
        lead.email || "",
        lead.nicho || "",
        lead.cidade || "",
        lead.uf || "",
        lead.endereco || "",
        lead.site || "",
        lead.instagram || "",
        lead.cnpj || "",
        lead.porte || "",
        lead.resumo_ia || "",
        lead.gancho_comercial || "",
        lead.status_contato || "Novo",
        "" // Notas do vendedor livres para preenchimento manual
      ];

      if (rowIdx !== -1) {
        // Atualiza a linha existente
        sheet.getRange(rowIdx + 2, 1, 1, rowData.length).setValues([rowData]);
      } else {
        // Insere nova linha
        sheet.appendRow(rowData);
      }
    });

    return ContentService.createTextOutput(JSON.stringify({
      status: "success",
      received: leads.length,
      message: "Leads gravados com sucesso na planilha!"
    })).setMimeType(ContentService.MimeType.JSON);

  } catch (error) {
    return ContentService.createTextOutput(JSON.stringify({
      status: "error",
      message: error.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}
```
