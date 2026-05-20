import sys
import time
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def consultar_sefaz_manual(chave):
    print(f"\n🚀 Iniciando Navegador para Consulta SEFAZ")
    print(f"🔑 Chave: {chave}")
    
    chrome_options = Options()
    # Não usamos headless para que o usuário possa resolver o CAPTCHA
    chrome_options.add_argument("--start-maximized")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        url = "https://nfeweb.sefaz.go.gov.br/nfeweb/sites/nfe/consulta-publica"
        driver.get(url)
        
        print("\n⏳ Aguardando carregamento da página...")
        wait = WebDriverWait(driver, 20)
        
        # Preenche a chave
        input_chave = wait.until(EC.presence_of_element_located((By.ID, "chaveAcesso")))
        input_chave.send_keys(chave)
        
        print("\n⚠️ AÇÃO NECESSÁRIA:")
        print("1. Resolva o CAPTCHA na janela do navegador.")
        print("2. Clique no botão 'Pesquisar'.")
        print("3. O sistema detectará automaticamente quando os dados aparecerem.")
        
        # Loop para detectar se a nota foi carregada (procura por tabResult ou estrutura de itens)
        dados_carregados = False
        while not dados_carregados:
            try:
                # Se encontrar o botão 'Imprimir' ou a tabela de itens, os dados estão na tela
                if "danfeNFCe" in driver.current_url or "consulta-completa" in driver.current_url:
                    if len(driver.find_elements(By.ID, "tabResult")) > 0 or len(driver.find_elements(By.CLASS_NAME, "txtTit")) > 0:
                        dados_carregados = True
                        print("\n✅ Dados detectados com sucesso!")
            except:
                pass
            time.sleep(1)
            
        # Extrai o HTML final
        html_final = driver.page_source
        
        # Salva para o backend processar
        with open("last_manual_import.html", "w", encoding="utf-8") as f:
            f.write(html_final)
            
        print("\n💾 HTML capturado e salvo em 'last_manual_import.html'")
        print("O backend agora pode processar esta nota sem CAPTCHA.")
        
        return html_final

    except Exception as e:
        print(f"\n❌ Erro durante a consulta: {e}")
    finally:
        print("\nEncerrando navegador em 5 segundos...")
        time.sleep(5)
        driver.quit()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        consultar_sefaz_manual(sys.argv[1])
    else:
        print("Uso: python importar_sefaz_navegador.py <CHAVE_DE_ACESSO>")
