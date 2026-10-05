# FC27 Market Radar

Automatyczny radar okazji FUT 27. System ma tylko analizować i alarmować — nie kupuje, nie licytuje i nie klika za użytkownika.

## Architektura
- frontend: GitHub Pages
- dane: JSON generowane przez worker
- alerts: Telegram
- market provider: adapter, bez udawania danych gdy provider nie jest dostępny
- TOTW Radar: osobny scoring kandydatów

## Status
Szkielet v1 został wdrożony. Kolejny etap: źródła contentu, provider cen, scoring podaży/popytu, Telegram i automatyczny worker.
