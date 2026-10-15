# Northwind Assistant Bot - Przewodnik Instalacji dla Administratora

Ten przewodnik opisuje jak skonfigurować bota Northwind Assistant w Twojej organizacji Microsoft 365.

**Szacowany czas:** 10-15 minut

---

## Przegląd

Bot Northwind Assistant wykorzystuje **model wdrożenia single-tenant**. Jest to wymagane przez Microsoft - od lipca 2025 tworzenie botów multi-tenant nie jest już wspierane.

Pracujemy nad publikacją w Microsoft Teams Store, co uprości przyszłe wdrożenia.

**Zalety wdrożenia single-tenant:**

- Bot działa wyłącznie w TWOIM tenancie Azure
- Twoje dane nigdy nie opuszczają organizacji
- Masz pełną kontrolę i widoczność wszystkich zasobów Azure
- Możesz cofnąć nasz dostęp po wdrożeniu

---

## Część 1: Co Musisz Dostarczyć

Zanim będziemy mogli wdrożyć bota, administrator Azure/Microsoft 365 musi dostarczyć:

### Wymagane Informacje

| Informacja | Opis | Przykład |
|------------|------|----------|
| **Azure Tenant ID** | ID Twojej organizacji Microsoft 365 | `12345678-abcd-1234-abcd-1234567890ab` |
| **Azure Subscription ID** | Subskrypcja Azure dla zasobów bota | `87654321-dcba-4321-dcba-0987654321ba` |
| **Preferowany Region Azure** | Gdzie hostować zasoby | West Europe, North Europe, itp. |
| **Email Kontaktowy Admina** | Do koordynacji wdrożenia | admin@twojafirma.com |

### Jak Znaleźć Tenant ID

Twój Tenant ID to to samo co ID organizacji Microsoft 365.

1. Przejdź do [portal.azure.com](https://portal.azure.com)
2. Wyszukaj **Microsoft Entra ID** (lub "Azure Active Directory")
3. Na stronie Przegląd znajdź **Tenant ID** (Identyfikator dzierżawy)
4. Skopiuj wartość GUID

### Jak Znaleźć Subscription ID

1. Przejdź do [portal.azure.com](https://portal.azure.com)
2. Wyszukaj **Subskrypcje** (Subscriptions)
3. Wybierz subskrypcję, której chcesz użyć dla bota
4. Skopiuj **Subscription ID** (Identyfikator subskrypcji) ze strony Przegląd

---

## Część 2: Przyznanie Dostępu do Wdrożenia

Potrzebujemy tymczasowego dostępu do wdrożenia zasobów bota.

### Przyznaj Dostęp Contributor

1. Przejdź do Azure Portal → **Subskrypcje** → Wybierz swoją subskrypcję
2. Kliknij **Kontrola dostępu (IAM)** → **Dodaj** → **Dodaj przypisanie roli**
3. Rola: **Contributor**
4. Członkowie: Dodaj `guest-admin@example.com` jako użytkownika-gościa
5. Kliknij **Zapisz**

Potrzebujemy również roli **Application Administrator** w Microsoft Entra ID do utworzenia rejestracji aplikacji bota. Proszę przyznać tę rolę do tego samego konta (`guest-admin@example.com`).

**Po wdrożeniu:** Możesz cofnąć ten dostęp. Potrzebujemy go tylko podczas początkowej konfiguracji i aktualizacji.

---

## Część 3: Co Zobaczysz w Azure Portal

Po wdrożeniu zobaczysz wszystkie zasoby w Azure Portal:

```
Resource Groups → rg-northwind-prod
├── bot-northwind-prod-xxxxx     (Bot Service)
├── func-northwind-prod-xxxxx    (Function App)
├── stnorthwindprod-xxxxx        (Storage Account)
└── kv-northwind-prod-xxxxx      (Key Vault)
```

### Konfiguracja Alertów Kosztowych (Zalecane)

1. Azure Portal → **Cost Management** → **Budgets**
2. Kliknij **+ Add**
3. Ustaw miesięczny budżet
4. Dodaj alert przy 80% i 100%
5. Powiadomienia email do admina

### Cofnięcie Dostępu Po Wdrożeniu

Po zakończeniu wdrożenia:

1. Przejdź do **Subskrypcje** → **Kontrola dostępu (IAM)**
2. Znajdź konto użytkownika-gościa
3. Kliknij **Usuń**

Dla przyszłych aktualizacji możesz ponownie przyznać tymczasowy dostęp.

---

## Wyślij Nam Te Informacje

Proszę wysłać następujące informacje do kontaktu w Ragstone:

```
Azure Tenant ID:       ___________________________________
Azure Subscription ID: ___________________________________
Preferowany Region:    ___________________________________
Email Admina:          ___________________________________
```

Po otrzymaniu tych informacji wdrożymy infrastrukturę bota i dostarczymy Ci pakiet aplikacji Teams.

---

## Część 4: Zainstaluj Aplikację w Teams

Po wdrożeniu infrastruktury otrzymasz plik `northwind-ai-prod.zip` dostosowany do Twojej organizacji.

### Wymagania

- Konto administratora Microsoft 365 (Teams Admin lub Global Admin)
- Dostęp do Teams Admin Center
- Plik `northwind-ai-prod.zip` (otrzymasz od nas)

### 4.1 Otwórz Teams Admin Center

1. Przejdź do [admin.teams.microsoft.com](https://admin.teams.microsoft.com)
2. Zaloguj się kontem administratora

### 4.2 Prześlij Aplikację

1. W menu bocznym wybierz: **Aplikacje Teams** → **Zarządzaj aplikacjami**
2. Kliknij **+ Prześlij nową aplikację**
3. Wybierz plik `northwind-ai-prod.zip`
4. Poczekaj na walidację (10-30 sekund)

### 4.3 Zatwierdź Aplikację

Po przesłaniu aplikacja pojawi się na liście. Status powinien być "Dozwolona".

---

## Część 5: Skonfiguruj Dostęp dla Użytkowników

Bot powinien być dostępny tylko dla wybranych pracowników.

### 5.1 Utwórz Grupę Bezpieczeństwa (opcjonalnie)

Jeśli nie masz jeszcze grupy dla użytkowników bota:

1. Przejdź do [portal.azure.com](https://portal.azure.com)
2. Wyszukaj **Microsoft Entra ID** → **Grupy**
3. Kliknij **+ Nowa grupa**
   - Typ: **Zabezpieczenia**
   - Nazwa: `Northwind Assistant Users`
   - Opis: `Pracownicy z dostępem do bota AI`
4. Dodaj członków (pracownicy którzy mają korzystać z bota)
5. Kliknij **Utwórz**

### 5.2 Przypisz Politykę Uprawnień

1. W Teams Admin Center przejdź do: **Aplikacje Teams** → **Zasady uprawnień**
2. Możesz:
   - **Opcja A:** Edytować globalną politykę (wszyscy użytkownicy)
   - **Opcja B:** Utworzyć nową politykę dla wybranej grupy

#### Opcja A: Globalna polityka

1. Kliknij **Globalne (domyślne dla całej organizacji)**
2. W sekcji **Aplikacje niestandardowe** wybierz **Zezwól na określone aplikacje**
3. Kliknij **Zezwól na aplikacje** → Wyszukaj `Northwind Assistant` → **Dodaj**
4. Kliknij **Zapisz**

#### Opcja B: Nowa polityka dla grupy

1. Kliknij **+ Dodaj**
2. Nazwa: `Northwind Assistant Access`
3. W sekcji **Aplikacje niestandardowe** wybierz **Zezwól na określone aplikacje**
4. Dodaj `Northwind Assistant`
5. Zapisz, następnie przypisz politykę do grupy bezpieczeństwa

---

## Część 6: Zweryfikuj Instalację (admin)

1. Otwórz Microsoft Teams → **Aplikacje** → wyszukaj **Northwind Assistant** → **Dodaj** lub **Otwórz**.
2. Wyślij wiadomość testową (np. `Cześć`).
3. Potwierdź, że bot odpowiada w ciągu ok. 5–15 sekund.

Przekaż pracownikom z dostępem przewodnik użytkownika:

- polski: [BOT-USAGE-PL.md](BOT-USAGE-PL.md)
- angielski: [BOT-USAGE-EN.md](BOT-USAGE-EN.md)

---

## Co Wdrażamy w Twoim Tenancie Azure

Dla przejrzystości, oto zasoby Azure które tworzymy:

| Zasób | Cel |
|-------|-----|
| **Resource Group** | Kontener dla wszystkich zasobów |
| **Azure Bot Service** | Integracja z Teams |
| **Azure Functions** | Logika backendu bota |
| **Storage Account** | Historia rozmów |
| **Key Vault** | Bezpieczne przechowywanie kluczy API |
| **App Registration** | Tożsamość bota |

---

## Kontakt

W razie problemów skontaktuj się z nami:

- Email: contact@example.com
- Telefon: +48 000 000 000

---

*Ostatnia aktualizacja: Styczeń 2026*
