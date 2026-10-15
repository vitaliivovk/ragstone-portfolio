<!-- Sync with pinecone-pipeline/source_data/opis folderów.docx when folder layout changes. See .cursor/skills/knowledge-base-curator/folder-map-prompt.md. -->

Mapa slugów do `retrieval_scopes` (filtr `corpusTopic`, OR). Pierwszy segment ścieżki w `pinecone-pipeline/source_data/` po normalizacji odpowiada slugowi w `RetrievalScope`. `corpus_path_prefixes` opcjonalnie zawęża do `root_slug/sub_slug` (dwa segmenty — patrz tabela niżej). Gdy niepewność lub pytanie cross-corpus → `["all"]` **samodzielnie** (nie łącz z innymi slugami).

## Slugi główne (`retrieval_scopes`)

| slug | zawartość |
|------|-----------|
| `1_najem_instytucjonalny` | Najem instytucjonalny B2C (**umowa I**): pierwsza umowa, OWU, akt notarialny, **przedłużenia**, załączniki, wersje językowe, **porozumienia** (szablony), lokalny dostawca energii, pełnomocnictwa. |
| `2_najem_firma` | Najem dla firm (**umowa F**): wzór umowy, aneksy/przedłużenia, OWU, załączniki. |
| `3_mieszkania_z_vatem_najem_zwyky` | Najem zwykły **z VAT** (literówka `zwyky` w slug — zamierzona). |
| `4_umowa_rezerwacyjna` | **Umowa rezerwacyjna** (RE) — draft + wpłata zaliczana na kaucję. **To nie to samo** co litera **(R)** w nazwie pliku przedłużenia. |
| `5_instrukcje` | Procedury operacyjne (CRM, proces wewnętrzny, maile przykładowe). **Nie zastępuje** wzorców umowy przy pytaniach o warunki umowne najemcy — łącz z slugiem umowy lub szukaj w obu, gdy pytanie dotyczy i procedury, i warunków. |
| `6_program_rabatowy_northwind_club_i_smart_home` | NORTHWIND CLUB / SMART HOME. |
| `zakwaterowanie` | **Zakwaterowanie** (Northwind): dokumenty procesu zakwaterowania w lokalach; różnice **najem vs zakwaterowanie**; obowiązkowe **słownictwo** w rozmowach z klientem (SMS/CRM, standardy ochrony dzieci). **Krytyczne:** nie mylić z najmem instytucjonalnym (`1_najem_instytucjonalny`) — **inny podatek VAT** i **inne zasady korzystania z lokalu**. Nie zastępuje `5_instrukcje` (proces najmu B2C). |
| `all` | Cały korpus (jedyny element listy). |

## Warianty w nazwach plików (katalog — nie odpowiedź merytoryczna)

| Oznaczenie | Znaczenie (typ szablonu) |
|------------|---------------------------|
| **I** | Umowa najmu **instytucjonalnego** (folder `1 Najem Instytucjonalny`). |
| **F** | Umowa najmu **firmy** (folder `2 Najem Firma`). |
| **(N)** | Przedłużenie / aneks **normalne** (umowa normalna). |
| **(W)** | Przedłużenie **z wypowiedzeniem** (opcja wypowiedzenia). |
| **(R)** | Przedłużenie **z rabatem** (w nazwie pliku — **nie** umowa rezerwacyjna). |
| **RE / rezerwacja** | Slug `4_umowa_rezerwacyjna` — **inny produkt** niż **(R)**. |

## Podfoldery `1_najem_instytucjonalny` (`corpus_path_prefixes`)

Wartość = `1_najem_instytucjonalny/<slug_drugiego_segmentu>` (jak w metadanych Pinecone `corpusPathPrefix`).

| `corpus_path_prefix` | Kiedy zawęzić wyszukiwanie (aspekt pytania) |
|----------------------|---------------------------------------------|
| `1_najem_instytucjonalny/1_umowa_najmu_i_owu_za_10` | Pierwsza umowa I, OWU, warunki podstawowe umowy (bez kontekstu przedłużenia). |
| `1_najem_instytucjonalny/2_przeduzenie_umowy_najmu_i_owu_za_10` | **Przedłużenie** umowy I — pliki `Przedłużenie najmu I (N/W/R)…`; pytania o warunki po przedłużeniu, okres przedłużenia, wcześniejsze rozwiązanie w kontekście umowy przedłużającej. |
| `1_najem_instytucjonalny/5_porozumienia_rozne` | Szablony **porozumień** (rozwiązanie, zwrot kaucji, zamiana itd.) — gdy pytanie wprost o **formularz / typ porozumienia**, nie o ogólne warunki umowy. |
| `1_najem_instytucjonalny/3_zalaczniki_do_umow_i_renajmow` | Załączniki (RODO, regulaminy dołączone do umów). |

Gdy pytanie dotyczy **warunków umownych najemcy** (opłaty, kaucja, wcześniejsze rozwiązanie, przedłużenie), preferuj **`1_najem_instytucjonalny`** (+ ewentualnie prefix przedłużenia lub pierwszej umowy) zamiast **`["all"]`** lub samego **`5_instrukcje`**. Gdy użytkownik mówi o **firmie** lub **VAT** — odpowiednio `2_najem_firma` lub `3_mieszkania_z_vatem_najem_zwyky`. Gdy o **rezerwacji** — `4_umowa_rezerwacyjna`. Gdy o **zakwaterowaniu** (Northwind, słownictwo w rozmowie z klientem, różnice najem vs zakwaterowanie, VAT/zasady lokalu) — **`zakwaterowanie`**, nie `1_najem_instytucjonalny` ani `5_instrukcje`.

Gdy **rodzina dokumentu** (pierwsza umowa vs przedłużenie vs rezerwacja vs VAT vs firma) nie wynika z pytania ani historii → **clarification_needed**, nie zgaduj slugów.
