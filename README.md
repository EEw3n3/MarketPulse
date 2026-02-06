# MarketPulse - Mārketinga automatizācija komerckompānijai

## Projekta apraksts

Šis ir kvalifikācijas darba projekts, kura tēma ir "Inteliģentas smaržu cenu uzraudzības un analīzes sistēmas izstrāde Latvijas e-komercijas segmentā". Projekta galvenais mērķis ir izveidot augsti automatizētu sistēmu, kas spēj patstāvīgi vākt un analizēt datus par vīriešu parfimērijas produktiem no vadošajiem Latvijas interneta veikaliem (Douglas, Notino, 220.lv, Makeup.lv, 1a.lv).

Projekta ietvaros tiek realizētas šādas inteliģentas funkcijas:
*   **Adaptīvā datu ieguve:** Izmantojot mākslīgo intelektu (AI), sistēma automātiski ģenerē un atjaunina datu ieguves noteikumus (CSS selektorus) gadījumos, ja mainās vietnes struktūra.
*   **Produktu sasaiste (Chaining):** Identisku produktu meklēšana un grupēšana starp dažādiem veikaliem, balstoties uz zīmolu, nosaukumu, tilpumu un koncentrāciju (EDP/EDT), nodrošinot precīzu cenu salīdzināšanu.
*   **Cenu dinamikas analīze:** Katra cenu maiņa tiek fiksēta vēsturē, ļaujot izsekot reālām atlaidēm un aprēķināt vidējo, labāko un dārgāko cenu tirgū.
*   **Izmaiņu monitorings:** Sistēma fiksē un ziņo par jaunu produktu pievienošanu, cenu svārstībām vai preces pieejamības izmaiņām noliktavā katrā no mērķa vietnēm.

## Izmantotās tehnoloģijas

Projektā tiek izmantots mūsdienīgs tehnoloģiju kopums stabilai un autononai darbībai:
*   **Python 3.10+** — galvenā izstrādes valoda.
*   **Playwright & Stealth** — pārlūkprogrammas automatizācija ar uzlabotu aizsardzību pret bloķēšanu.
*   **SQLModel / PostgreSQL** — relāciju datu bāze datu glabāšanai un analītikai.
*   **FastAPI** — tīmekļa ietvars datu apmaiņai un sistēmas vadībai.
*   **Docker & Docker Compose** — konteinerizācija un vides standartizācija.
*   **OpenAI API / LLM** — inteliģentai datu parsēšanai un automātiskai selektoru ģenerēšanai.

## Izmantotie avoti

1.  [FastAPI Documentation](https://fastapi.tiangolo.com/) - izmantots kā pamats aplikācijas arhitektūras un asinhrono procesu veidošanai.
2.  [Playwright for Python](https://playwright.dev/python/) - apgūts, kā veikt pārlūkprogrammas automatizāciju un apiet aizsardзības mehānismus.
3.  [SQLModel Documentation](https://sqlmodel.tiangolo.com/) - izmantots datu bāzes shēmu projektēšanai un ORM implementācijai.
4.  [Parsel Documentation](https://parsel.readthedocs.io/) - izmantots CSS un XPath selektoru pielietošanai datu parsēšanā.
5.  [OpenAI API Reference](https://platform.openai.com/docs/) - izmantots, lai integrētu mākslīgo intelektu datu atpazīšanā un kļūdu labošanā.
6.  [PostgreSQL Documentation](https://www.postgresql.org/docs/) - izmantots datu bāzes optimizācijai un sarežģītu vaicājumu veidošanai.
