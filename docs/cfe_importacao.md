# Guia de Importação de Notas - SEFAZ GO 🚀

O sistema Gestão Compras V2.0 suporta três métodos de importação para garantir 100% de sucesso, mesmo com barreiras de segurança (CAPTCHA).

## 1. Importação Via Link do QR Code (Recomendado) ✅
Este é o método mais rápido e automático. Use o link completo impresso na nota ou lido pela câmera.
- **Como funciona:** O link contém um código de segurança (hash) que permite ao sistema baixar os dados estruturados instantaneamente, sem CAPTCHA.
- **O que colar:** `https://nfeweb.sefaz.go.gov.br/nfeweb/sites/nfce/danfeNFCe?p=5226...|2|1|...`

## 2. Importação Via HTML Colado (Pasted HTML) 📄
Use este método se o portal da SEFAZ exigir CAPTCHA ou se você estiver em uma página de consulta completa.
- **Como usar:** 
  1. Acesse o portal: [Consulta Pública SEFAZ GO](https://nfeweb.sefaz.go.gov.br/nfeweb/sites/nfe/consulta-publica)
  2. Digite a chave e resolva o CAPTCHA.
  3. Com a nota aberta na tela, pressione `Ctrl + U` (Exibir código fonte) ou `Ctrl + A` e copie todo o conteúdo.
  4. Cole o conteúdo no campo de importação do sistema.
- **Vantagem:** Bura qualquer bloqueio de bot, pois você já validou como humano.

## 3. Importação Via Chave de Acesso (44 dígitos) 🔑
Método clássico para quando você tem apenas os números.
- **Nota:** O sistema tentará acessar o portal automaticamente. Se houver CAPTCHA, ele poderá falhar e solicitar que você use o **Método 2**.

---

### Suporte a Modelos:
- **NFC-e (Modelo 65):** Cupons fiscais de supermercados, farmácias, etc.
- **NF-e (Modelo 55):** Notas fiscais grandes de compras online ou atacado.

*O sistema detecta o modelo e o layout da página automaticamente.*
