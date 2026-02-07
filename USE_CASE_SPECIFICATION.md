# Market Pulse: Paplašinātā Use Case Diagramma & Specifikācija

Šis dokuments apraksta pilno sistēmas funkcionalitāti, aptverot visas iespējas, kas būs pieejamas pabeigtā tīmekļa platformā.

## 1. Use Case Diagramma (Mermaid)

```mermaid
useCaseDiagram
    actor "Lietotājs (User)" as U
    actor "Administrators (Admin)" as A

    package "Market Pulse Platform" {
        %% User UC
        usecase "Meklēt un filtrēt parfimēriju" as UC1
        usecase "Skatīt cenu grafikus un analītiku" as UC2
        usecase "Pievienot Watchlist (Sekot cenai)" as UC3
        usecase "Iestatīt cenas slieksni" as UC4
        usecase "Saņemt paziņojumus (Email/Push)" as UC5
        usecase "Autorizēties / Pārvaldīt profilu" as UC6
        usecase "Eksportēt datus (Excel/CSV)" as UC7
        
        %% Admin UC
        usecase "Pārvaldīt skenēšanas mērķus un grafiku" as UC8
        usecase "Pārraudzīt sistēmas veselības stāvokli" as UC9
        usecase "Validēt un labot AI noteikumus" as UC10
        usecase "Manuāli koriģēt preču sasaisti" as UC11
        usecase "Pārvaldīt lietotāju kontus" as UC12
        usecase "Analizēt tirgus kopskata statistiku" as UC13
        
        %% Internal/Included
        usecase "Veikt datu normalizāciju un Chaining" as UC14
        usecase "Fiksēt cenu un krājumu izmaiņas" as UC15
        usecase "Ģenerēt un 'pašdziedināt' AI noteikumus" as UC16
    }

    %% User Connections
    U --> UC1
    U --> UC2
    U --> UC6
    U --> UC7
    
    %% Relationships User
    UC1 ..> UC14 : <<include>>
    UC2 ..> UC6 : <<include>>
    UC3 ..> UC1 : <<extend>>
    UC4 ..> UC3 : <<include>>
    UC5 ..> UC3 : <<include>>
    UC5 ..> UC15 : <<include>>
    UC7 ..> UC6 : <<include>>

    %% Admin Connections
    A --> UC8
    A --> UC9
    A --> UC12
    A --> UC13
    A --> UC6
    
    %% Relationships Admin
    UC8 ..> UC16 : <<include>>
    UC10 ..> UC9 : <<extend>>
    UC11 ..> UC10 : <<extend>>
    UC14 ..> UC16 : <<include>>
    UC15 ..> UC14 : <<include>>
```

## 2. Detalizēts skaidrojums (Paplašinātais)

### 2.1. Aktori
*   **Lietotājs:** Meklē izdevīgākos piedāvājumus, analizē grafikus un saņem automātiskus brīdinājumus.
*   **Administrators:** Atbild par sistēmas nepārtrauktu darbību, datu kvalitāti un lietotāju bāzi.

### 2.2. Relācijas (Loģika)

#### <<include>> (Obligātās darbības)
1. **Meklēšana ➙ Normalizācija/Chaining:** Lai lietotājs redzētu pareizus rezultātus, sistēma fonā obligāti veic datu salīdzināšanu.
2. **Cenas slieksnis ➙ Watchlist:** Tu nevari iestatīt vēlamo cenu produktam, kuram tu neseko.
3. **Paziņojumi ➙ Watchlist & Izmaiņu fiksēšana:** Paziņojums tiek sūtīts tikai tad, ja prece ir sarakstā UN sistēma ir fiksējusi cenu kritumu.
4. **Skenēšanas mērķi ➙ AI Self-Healing:** Pievienojot jaunu veikalu vai mainoties esošajam, sistēma automātiski iedarbina AI noteikumu ģenerēšanu.

#### <<extend>> (Papildus iespējas)
1. **Watchlist ➙ Meklēšana:** Lietotājs meklē preci un *pēc izvēles* var to pievienot sekošanai.
2. **AI Noteikumu korekcija ➙ Veselības monitors:** Admin skatās sistēmas stāvokli un *gadījumā, ja redz kļūdas*, veic manuālu noteikumu korekciju.
3. **Manuāla sasaistes korekcija ➙ AI Noteikumu korekcija:** Ja AI ir kļūdījies sasaistē, admins to var labot manuāli kā paplašinājumu noteikumu pārbaudei.
