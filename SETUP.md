# FC27 Market Radar — jednorazowa konfiguracja

## A. Market data — PARSE_API_KEY
Używamy monitorowanego wrappera FUT.GG dostępnego w Parse. To nie jest oficjalne publiczne API FUT.GG; system nie będzie udawał, że nim jest.

1. Wejdź na stronę API FUT.GG w Parse.
2. Załóż konto / zaloguj się i utwórz API key.
3. W GitHub: Settings → Secrets and variables → Actions → New repository secret.
4. Name: PARSE_API_KEY
5. Value: Twój klucz.

Nie wklejaj klucza do czatu.

## B. GitHub Pages
Settings → Pages → Build and deployment → Source: GitHub Actions.

## C. Telegram
1. Telegram → @BotFather → /newbot.
2. Nadaj nazwę i username bota.
3. Zapisz token lokalnie — nie wysyłaj go na czat.
4. Otwórz rozmowę z botem i wyślij /start.
5. Dodaj do GitHub Actions secrets:
   TELEGRAM_BOT_TOKEN
   TELEGRAM_CHAT_ID

## D. Ważne
Radar wyłącznie analizuje i alarmuje. Nie wykonuje zakupów, licytacji ani innych działań w Web App.
