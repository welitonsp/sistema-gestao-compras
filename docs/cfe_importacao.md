# Importacao por chave (SEFAZ GO)

## Objetivo
Importar NFC-e, NF-e de consumidor e CF-e a partir da chave de acesso, registrar os itens no historico de precos e cadastrar produtos ausentes usando a classificacao existente do projeto.

## Como o fluxo funciona
1. O usuario escolhe a opcao `11` no menu principal.
2. O sistema valida a chave com 44 digitos e confere o digito verificador.
3. O XML e procurado primeiro em `XML_DFE_GO/<chave>.xml`.
4. Se o arquivo nao existir localmente, o sistema tenta baixar o XML usando `SEFAZ_GO_XML_PROVIDER_URL_TEMPLATE`.
5. Os itens do XML sao parseados e cada item e salvo no banco com data, mercado, preco unitario e quantidade.

## Configuracao esperada
- `GOIAS_XML_DOWNLOAD_DIR`: diretorio opcional para cache local dos XMLs. Se nao for informado, o padrao sera `XML_DFE_GO`.
- `SEFAZ_GO_XML_PROVIDER_URL_TEMPLATE`: URL com o placeholder `{chave}` para buscar o XML ja autorizado por um provedor intermediario.
- `SEFAZ_GO_XML_PROVIDER_TOKEN`: token Bearer opcional para o provedor configurado acima.

## Observacoes importantes
- O sistema nao faz consulta publica direta ao portal da SEFAZ GO apenas com a chave. Ele depende de XML salvo localmente ou de um endpoint intermediario configurado para entregar o documento.
- Se a chave informada nao bater com a chave embutida no XML, a importacao e interrompida.
- XML invalido, sem emitente, sem data de emissao ou sem itens gera erro explicito para evitar gravacao incorreta.
