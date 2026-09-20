from dotenv import load_dotenv
import os, urllib.parse

load_dotenv(dotenv_path='.env', encoding='utf-8')

host = os.getenv('DB_HOST', 'NAO DEFINIDO')
user = os.getenv('DB_USER', 'NAO DEFINIDO')
pwd  = os.getenv('DB_PASSWORD', 'NAO DEFINIDO')
port = os.getenv('DB_PORT', '5432')
name = os.getenv('DB_NAME', 'postgres')

print("DB_HOST   =", host)
print("DB_USER   =", user)
print("DB_PORT   =", port)
print("DB_NAME   =", name)
print("DB_PASSWORD exists:", pwd != 'NAO DEFINIDO')

if pwd != 'NAO DEFINIDO':
    encoded = urllib.parse.quote(pwd, safe='')
    url = "postgresql+psycopg2://" + user + ":" + encoded + "@" + host + ":" + port + "/" + name + "?sslmode=require"
    print("URL segura gerada: OK, tamanho =", len(url))
    # Testa se a URL e toda ASCII (sem bytes especiais)
    try:
        url.encode('ascii')
        print("URL: 100% ASCII - sem caracteres especiais")
    except UnicodeEncodeError as e:
        print("URL tem char especial:", e)
