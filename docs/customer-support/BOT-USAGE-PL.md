# Northwind Assistant — jak korzystać z bota w Teams

Przewodnik dla **pracowników** korzystających z Northwind Assistant w Microsoft Teams (czat 1:1).

**Dla administratorów IT:** instalacja i uprawnienia — [CUSTOMER-SETUP-PL.md](CUSTOMER-SETUP-PL.md).

---

## Jak zacząć

1. Otwórz **Microsoft Teams** (aplikacja lub przeglądarka).
2. Kliknij **Aplikacje** na pasku bocznym.
3. Wyszukaj **Northwind Assistant**.
4. Kliknij **Dodaj** lub **Otwórz**.
5. Napisz pytanie zwykłym tekstem — jak do kolegi.

Bot odpowiada w **czacie 1:1**. Nie obsługuje na razie grupowych czatów ani kanałów zespołu.

Odpowiedź zwykle pojawia się w ciągu kilkunastu sekund. Przy dłuższym wyszukiwaniu zobaczysz krótkie komunikaty statusu (np. analiza pytania, przeszukiwanie dokumentów).

---

## O czym możesz pytać

Asystent przeszukuje **wewnętrzną dokumentację firmową** (umowy, instrukcje, procedury, załączniki). Przykłady:

- „Jakie są warunki wypowiedzenia umowy?”
- „Gdzie znajdę wzór protokółu zdawczo-odbiorczego?”
- „Jak rozliczyć kaucję?”
- „Jakie dokumenty są potrzebne przy przedłużeniu najmu?”

Pisz **po polsku** (domyślnie) lub po angielsku — bot stara się dopasować język odpowiedzi do pytania.

Gdy pytanie jest **niejednoznaczne** (np. pierwsza umowa vs przedłużenie), bot może zadać **krótkie pytanie doprecyzowujące** zamiast zgadywać.

---

## Źródła na końcu odpowiedzi

Na końcu wielu odpowiedzi jest sekcja **Źródła** — lista plików z **klikalnymi linkami** do SharePoint.

| Typ pliku | Co się dzieje po kliknięciu |
|-----------|----------------------------|
| **PDF** | Otwarcie w przeglądarce |
| **Word, Excel, PowerPoint** | Podgląd w Office w sieci (bez pobierania na dysk) |

Numery stron mogą być widoczne przy nazwie pliku; link zwykle otwiera **cały dokument**, nie pojedynczą stronę.

W treści odpowiedzi **nie ma numerków** typu „Źródło 1” — cytowania są tylko w sekcji **Źródła**.

---

## Komendy

| Komenda | Działanie |
|---------|-----------|
| `/style …` lub `/styl …` | Zapisuje **Twoje preferencje stylu** (np. `/style krótko, w punktach` lub `/style odpowiadaj po angielsku`) |
| `/style` lub `/styl` | Pokazuje aktualnie zapisane preferencje |
| `/style reset` lub `/styl reset` | Czyści zapisane preferencje |
| `/clean_chat_history` | Czyści **historię rozmowy** bota (bot „zapomina” wcześniejsze wiadomości w tym czacie) |
| `/wyczysc_historie` | To samo co `/clean_chat_history` |

**Uwaga:** preferencje `/style` są powiązane z **Twoim kontem Teams** i **nie znikają** po `/clean_chat_history`. Żeby je usunąć, użyj `/style reset`.

---

## Wskazówki

- **Jedno pytanie na raz** — przy złożonych tematach bot lepiej odpowiada na konkretne pytanie niż na listę w jednej wiadomości.
- **Doprecyzowanie** — możesz napisać „rozwiń” lub „a co z…?” w tej samej rozmowie; bot korzysta z kontekstu wcześniejszych wiadomości.
- **Brak informacji** — jeśli czegoś nie ma w dokumentacji, bot powie to wprost zamiast wymyślać odpowiedź.
- **Długie odpowiedzi** — często zawierają listę **Najważniejsze punkty** u góry lub na dole, żeby łatwiej skanować tekst.

---

## Kontakt przy problemach

Jeśli bot nie odpowiada, zwraca błąd lub odpowiedź jest ewidentnie błędna:

1. Spróbuj **`/clean_chat_history`** i zadaj pytanie ponownie.
2. Skontaktuj się z administratorem Teams w firmie lub z Ragstone:

- Email: contact@example.com
- Telefon: +48 000 000 000

---

*Ostatnia aktualizacja: maj 2026*
