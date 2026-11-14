import urllib.request

print("Проверяем связь с Telegram...")
try:
    urllib.request.urlopen("https://api.telegram.org", timeout=5)
    print("✅ СВЯЗЬ ЕСТЬ! Терминал видит Telegram.")
except Exception as e:
    print(f"❌ СВЯЗИ НЕТ! Провайдер или брандмауэр блокирует терминал: {e}")