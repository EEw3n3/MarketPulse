# MarketPulse - Mārketinga automatizācija komerckompānijai

## Projekta apraksts

Šis ir kvalifikācijas darba projekts, kura mērķis ir izstrādāt inteliģentu cenu monitoringa un tirgus analīzes sistēmu "MarketPulse". Projekts automatizē datu iegūšanu (web scraping) no e-komercijas veikaliem, izmantojot hibrīdu pieeju (ātrus HTTP pieprasījumus kombinācijā ar pilnu pārlūkprogrammas emulāciju).

Gala produkts ir spējīgs:
*   Meklēt produktus dažādos interneta veikalos (piemēram, rdveikals.lv, nike.com).
*   Izmantot mākslīgo intelektu (AI), lai automātiski atpazītu produktu cenas un datus.
*   Grupēt identiskus produktus no dažādiem avotiem vienotā sistēmā.
*   Analizēt cenu izmaiņas un identificēt izdevīgākos piedāvājumus.

## Izmantotās tehnoloģijas

Projektā tiek izmantots:

*   **Python 3.10+**
*   **FastAPI** (tīmekļa ietvars)
*   **SQLModel / PostgreSQL** (datu bāze)
*   **Playwright** (pārlūkprogrammas automatizācija)
*   **Docker** (konteinerizācija)

## Izmantotie avoti

1.  [FastAPI Documentation](https://fastapi.tiangolo.com/) - izmantots kā pamats aplikācijas arhitektūras un asinhrono procesu veidošanai.
2.  [Playwright for Python](https://playwright.dev/python/) - apgūts, kā veikt pārlūkprogrammas automatizāciju un apiet aizsardzības mehānismus.
3.  [SQLModel Documentation](https://sqlmodel.tiangolo.com/) - izmantots datu bāzes shēmu projektēšanai un ORM implementācijai.
4.  [Parsel Documentation](https://parsel.readthedocs.io/) - izmantots CSS un XPath selektoru pielietošanai datu parsēšanā.
