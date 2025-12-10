# Script para criar uma Nota Fiscal de mentira para teste
xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<nfeProc version="4.00" xmlns="http://www.portalfiscal.inf.br/nfe">
  <NFe>
    <infNFe>
      <ide>
        <dhEmi>2024-03-15T10:00:00-03:00</dhEmi>
      </ide>
      <emit>
        <xNome>SUPERMERCADO DO ESTAGIARIO LTDA</xNome>
      </emit>
      <det nItem="1">
        <prod>
          <cEAN>7891000053508</cEAN>
          <xProd>REFRIGERANTE COCA COLA 2L</xProd>
          <qCom>2.0000</qCom>
          <vUnCom>8.99</vUnCom>
        </prod>
      </det>
      <det nItem="2">
        <prod>
          <cEAN>7896004001234</cEAN>
          <xProd>BISC RECH OREO 90G</xProd>
          <qCom>3.0000</qCom>
          <vUnCom>3.50</vUnCom>
        </prod>
      </det>
      <det nItem="3">
        <prod>
          <cEAN>SEM GTIN</cEAN>
          <xProd>PAO FRANCES KG</xProd>
          <qCom>0.500</qCom>
          <vUnCom>12.00</vUnCom>
        </prod>
      </det>
    </infNFe>
  </NFe>
</nfeProc>
"""

with open("nota_teste.xml", "w", encoding="utf-8") as f:
    f.write(xml_content)

print("✅ Arquivo 'nota_teste.xml' criado com sucesso!")