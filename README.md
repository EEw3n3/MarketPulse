# MarketPulse — Mārketinga automatizācija komerckompānijai

> Inteliģentas smaržu cenu uzraudzības un analīzes sistēmas izstrāde Latvijas e-komercijas segmentā

## Projekta apraksts

**MarketPulse** ir augsti automatizēta sistēma, kas patstāvīgi vāc, normalizē un analizē datus par vīriešu parfimērijas produktiem no vadošajiem Latvijas interneta veikaliem (Douglas, Notino, 220.lv, Makeup.lv, 1a.lv). Sistēma ļauj lietotājam vienuviet salīdzināt vienas un tās pašas preces cenas dažādos veikalos, sekot līdzi cenu vēsturei un saņemt paziņojumus par izdevīgām cenu izmaiņām.

Galvenās realizētās funkcijas:

* **Adaptīvā datu ieguve (Self-Healing AI):** ja mainās veikala vietnes struktūra un vecie selektori vairs nestrādā, sistēma ar Google Gemini mākslīgā intelekta palīdzību automātiski ģenerē jaunus CSS selektorus — bez cilvēka iejaukšanās.
* **Hibrīdais datu ieguves dzinējs:** ātrā `curl_cffi` metode SSR vietnēm un pilna `Playwright` pārlūkprogrammas automatizācija JavaScript vietnēm, ar aizsardzību pret bloķēšanu.
* **Produktu sasaiste (Chaining):** identisku preču atpazīšana un grupēšana starp veikaliem pēc zīmola, nosaukuma, tilpuma un koncentrācijas (EDP/EDT), nodrošinot precīzu cenu salīdzināšanu.
* **Cenu vēsture un analītika:** katra cenu izmaiņa tiek fiksēta; interaktīvie grafiki rāda cenu dinamiku pa veikaliem, tirgus tendences un volatilitāti.
* **Paziņojumi:** lietotājs pievieno preces sekošanas sarakstam (Watchlist) un saņem brīdinājumus pa **Telegram** un **e-pastu**, kad cenas izmaiņa pārsniedz iestatīto slieksni.
* **Izkliedētais skenēšanas dzinējs (Distributed Worker):** serveris izvieto skenēšanas uzdevumus Redis rindā, bet pati datu ieguve notiek caur lokālo darbinieku (worker), izmantojot lietotāja IP adresi.
* **Datu eksports:** preču un kataloga dati eksportējami CSV, JSON, Excel un PDF formātos.

## Izmantotās tehnoloģijas

**Servera daļa (Backend):**
* **Python 3.11** — galvenā izstrādes valoda
* **FastAPI** — asinhronais tīmekļa ietvars (REST API)
* **SQLModel** — ORM datu bāzes manipulācijām
* **Alembic** — datu bāzes shēmas migrācijas

**Datu bāze un kešatmiņa:**
* **PostgreSQL 15** — galvenā relāciju datu bāze (`asyncpg` draiveris)
* **Redis** — kešatmiņa un izkliedētā skenēšanas uzdevumu rinda

**Klienta daļa (Frontend):**
* **React + TypeScript** (Vite būvētājs)
* **Tailwind CSS** + **shadcn/ui** — saskarnes komponenti
* **Recharts** — interaktīvie analītiskie grafiki

**Datu ieguve (Scraping):**
* **Playwright + Stealth** — pārlūkprogrammas automatizācija ar aizsardzību pret bloķēšanu
* **curl_cffi** — ātrais HTTP klients ar TLS pirkstu nospiedumu emulāciju
* **thefuzz** — neskaidrā (fuzzy) salīdzināšana produktu sasaistei

**Mākslīgais intelekts:**
* **Google Gemini** (`google-genai`) — CSS selektoru ģenerēšana un pašārstēšanās

**Paziņojumi:**
* **Telegram Bot API** — momentānie paziņojumi
* **Resend** (HTTP API) — e-pasta paziņojumi

**Infrastruktūra:**
* **Docker + Docker Compose** — konteinerizācija
* **Caddy** — reversais starpniekserveris ar automātisku HTTPS (Let's Encrypt)
* **DigitalOcean** — mākoņa serveris
* **GitHub Actions** — CI/CD automātiskā izvietošana

**Eksporta dzinējs:**
* **openpyxl** (Excel), **ReportLab** + **matplotlib** (PDF ar grafikiem)

## Izmantotie avoti

1. [FastAPI Documentation](https://fastapi.tiangolo.com/) — aplikācijas arhitektūras un asinhrono procesu pamats.
2. [Playwright for Python](https://playwright.dev/python/) — pārlūkprogrammas automatizācija un aizsardzības mehānismu apiešana.
3. [SQLModel Documentation](https://sqlmodel.tiangolo.com/) — datu bāzes shēmu projektēšana un ORM.
4. [Google Gemini API](https://ai.google.dev/docs) — mākslīgā intelekta integrācija selektoru ģenerēšanai.
5. [PostgreSQL Documentation](https://www.postgresql.org/docs/) — datu bāzes optimizācija un sarežģīti vaicājumi.
6. [React Documentation](https://react.dev/) — klienta puses komponenšu arhitektūra.
7. [Vite Documentation](https://vitejs.dev/) — frontend būvēšanas rīks un dev serveris.
8. [Tailwind CSS](https://tailwindcss.com/docs) un [shadcn/ui](https://ui.shadcn.com/) — saskarnes stilizācija un komponenti.
9. [Recharts](https://recharts.org/) — datu vizualizācijas grafiki.
10. [Caddy Documentation](https://caddyserver.com/docs/) — reversais starpniekserveris un automātisks HTTPS.
11. [Resend Documentation](https://resend.com/docs) — e-pasta sūtīšana caur HTTP API.
12. [Docker Documentation](https://docs.docker.com/) — konteinerizācija un vides standartizācija.

## Uzstādīšanas instrukcijas

Projekts ir pilnībā konteinerizēts ar Docker, tāpēc lokālai palaišanai nav nepieciešams manuāli instalēt Python, PostgreSQL vai Node.js.

### Priekšnosacījumi
* Instalēts [Docker Desktop](https://www.docker.com/products/docker-desktop/) (iekļauj Docker Compose)
* Instalēts [Git](https://git-scm.com/downloads)

### Soļi

1. **Klonēt repozitoriju:**
   ```bash
   git clone https://github.com/pikcrvt-students/26_d43-ErvinsUbinins-Marketinga-automizacija-komerckompanijai.git
   cd 26_d43-ErvinsUbinins-Marketinga-automizacija-komerckompanijai
   ```

2. **Izveidot konfigurācijas failu** no parauga un aizpildīt savas atslēgas:
   ```bash
   cp .env.example .env
   ```
   Atver `.env` un norādi vismaz `GOOGLE_API_KEY` un `JWT_SECRET` (pārējie nepieciešami konkrētām funkcijām — Telegram, e-pasts, worker). Skaidrojumi par katru mainīgo ir `.env.example` failā.

3. **Palaist sistēmu:**
   ```bash
   docker compose up -d --build
   ```
   Komanda automātiski uzbūvē un palaiž PostgreSQL, Redis, backend (FastAPI) un frontend (Vite) konteinerus, kā arī pielieto datu bāzes migrācijas (`alembic upgrade head`).

4. **Atvērt sistēmu pārlūkprogrammā:**
   * Frontend (lietotāja saskarne): http://localhost:8080
   * Backend API dokumentācija (Swagger): http://localhost:8000/docs

5. **(Neobligāti) Palaist datu ieguves darbinieku** datu savākšanai no veikaliem. Atsevišķā terminālī:
   ```bash
   docker compose exec app python scripts/scrape_worker.py
   ```
   Pēc tam administratora panelī (Admin → Scraping) var izvietot skenēšanas uzdevumus, kurus apstrādās šis darbinieks.

### Administratora konts
Lietotājs, kura e-pasts norādīts `.env` mainīgajā `ADMIN_EMAIL`, pēc reģistrācijas automātiski iegūst administratora tiesības (piekļuvi Admin panelim).
