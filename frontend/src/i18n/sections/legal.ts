// Privacy policy and terms of use (/privacy, /terms). Google's sign-in
// consent screen and the payment providers link to these pages.
// CONTACT must be a mailbox someone reads.

export const CONTACT = "privacy@marketpulse1.me";
const UPDATED = "2026-11-01";

type Section = { h: string; p: string[] };

const en = {
  privacyH: "Privacy policy",
  termsH: "Terms of use",
  updated: "Last updated",
  date: UPDATED,
  contact: "Contact",
  other: { privacy: "Terms of use", terms: "Privacy policy" },
  privacy: [
    {
      h: "Who we are",
      p: [
        "MarketPulse (marketpulse1.me) compares perfume prices in Latvian online shops. It is run by Ervin Ubinin, Riga, Latvia, who is responsible for your data.",
        `Questions about your data: ${CONTACT}.`,
      ],
    },
    {
      h: "What we keep",
      p: [
        "Your account: email address, name (if you give one) and, if you set a password, a one-way hash of it (never the password itself).",
        "If you sign in with Google: your Google account ID, email address and name, as Google sends them. We get nothing else from your Google account.",
        "Your settings: the shops and brands you follow, your favorites and alert settings.",
        "Your plan: whether you have Pro, until when, and a log of changes to it.",
        "The AI assistant: what you write to it is sent to Google's Gemini service to produce the answer. Please do not write personal information there.",
        "Technical records: the server keeps logs (IP address, time, requested address) for a short time, for security and to fix errors.",
        "In your browser we store your sign-in token and your language. We use no advertising or tracking cookies and no analytics services.",
      ],
    },
    {
      h: "Why",
      p: [
        "To run your account and show you prices and alerts (the service you asked for), and to keep the site secure (our legitimate interest).",
      ],
    },
    {
      h: "Who else sees it",
      p: [
        "We do not sell or share your data. Two companies process it for us: Contabo GmbH, which hosts our server, and Google (sign-in with Google, if you use it, and the Gemini service for the assistant).",
        "The site sends no emails.",
      ],
    },
    {
      h: "How long",
      p: [
        "As long as your account exists. When you delete it (Profile → Delete account), your account, favorites, settings and plan log are deleted at once; database backups that still contain them are overwritten within 7 days.",
      ],
    },
    {
      h: "Your rights",
      p: [
        `You can ask to see, correct, export or delete your data, or object to how we use it: write to ${CONTACT}. You can also complain to the Data State Inspectorate of Latvia (Datu valsts inspekcija, www.dvi.gov.lv).`,
      ],
    },
    {
      h: "Changes",
      p: ["When this policy changes, we update this page and its date."],
    },
  ] as Section[],
  terms: [
    {
      h: "The service",
      p: [
        "MarketPulse shows public prices of perfume from online shops (Notino, Makeup.lv, 220.lv and Douglas), read automatically every day. We are not connected with these shops and do not sell anything ourselves.",
        "Prices can be out of date or wrong. Always check the price in the shop before you buy.",
      ],
    },
    {
      h: "Your account",
      p: [
        "One account per person. Keep your password safe; you are responsible for what happens in your account. You can delete it at any time in your profile.",
      ],
    },
    {
      h: "Pro",
      p: [
        "Pro opens market analytics and data export. For now Pro is given by the administrator. When paid plans start, the price and terms will be shown before you pay. Pro ends when its term ends.",
      ],
    },
    {
      h: "Fair use",
      p: [
        "Do not read MarketPulse with bots or scripts, do not try to get around its security, and do not resell its data. We may switch off accounts that do.",
      ],
    },
    {
      h: "The AI assistant",
      p: ["The assistant's answers are written by a computer and can be wrong. Check important facts."],
    },
    {
      h: "Responsibility",
      p: [
        "The service is provided as it is. As far as the law allows, we are not responsible for losses from decisions based on prices shown here. We may change or stop the service.",
      ],
    },
    {
      h: "Law",
      p: [`These terms follow the law of the Republic of Latvia. Questions: ${CONTACT}.`],
    },
  ] as Section[],
};

const lv: typeof en = {
  privacyH: "Privātuma politika",
  termsH: "Lietošanas noteikumi",
  updated: "Atjaunināts",
  date: UPDATED,
  contact: "Kontakti",
  other: { privacy: "Lietošanas noteikumi", terms: "Privātuma politika" },
  privacy: [
    {
      h: "Kas mēs esam",
      p: [
        "MarketPulse (marketpulse1.me) salīdzina smaržu cenas Latvijas interneta veikalos. To uztur Ervins Ubinins, Rīga, Latvija, kurš ir atbildīgs par jūsu datiem.",
        `Jautājumi par jūsu datiem: ${CONTACT}.`,
      ],
    },
    {
      h: "Ko mēs glabājam",
      p: [
        "Jūsu kontu: e-pasta adresi, vārdu (ja to norādāt) un, ja iestatāt paroli, tās neatgriezenisku jaucējvērtību (nekad pašu paroli).",
        "Ja piesakāties ar Google: jūsu Google konta ID, e-pasta adresi un vārdu, kā tos nosūta Google. No jūsu Google konta mēs nesaņemam neko citu.",
        "Jūsu iestatījumus: veikalus un zīmolus, kuriem sekojat, izlasi un paziņojumu iestatījumus.",
        "Jūsu plānu: vai jums ir Pro, līdz kuram datumam, un tā izmaiņu žurnālu.",
        "MI asistentu: tas, ko tam rakstāt, tiek nosūtīts Google pakalpojumam Gemini, lai sagatavotu atbildi. Lūdzu, nerakstiet tur personas datus.",
        "Tehniskos ierakstus: serveris īsu laiku glabā žurnālus (IP adresi, laiku, pieprasīto adresi) drošībai un kļūdu labošanai.",
        "Jūsu pārlūkā mēs glabājam pieteikšanās atslēgu un valodu. Mēs neizmantojam reklāmas vai izsekošanas sīkdatnes un analītikas pakalpojumus.",
      ],
    },
    {
      h: "Kāpēc",
      p: [
        "Lai uzturētu jūsu kontu un rādītu cenas un paziņojumus (pakalpojums, ko pieprasījāt), un lai vietne būtu droša (mūsu leģitīmās intereses).",
      ],
    },
    {
      h: "Kas vēl tos redz",
      p: [
        "Mēs nepārdodam un nenododam jūsu datus. Mūsu uzdevumā tos apstrādā divi uzņēmumi: Contabo GmbH, kas uztur mūsu serveri, un Google (pieteikšanās ar Google, ja to izmantojat, un Gemini pakalpojums asistentam).",
        "Vietne nesūta e-pastus.",
      ],
    },
    {
      h: "Cik ilgi",
      p: [
        "Tik ilgi, kamēr pastāv jūsu konts. Kad to dzēšat (Profils → Dzēst kontu), konts, izlase, iestatījumi un plāna žurnāls tiek dzēsti uzreiz; datubāzes rezerves kopijas, kurās tie vēl ir, tiek pārrakstītas 7 dienu laikā.",
      ],
    },
    {
      h: "Jūsu tiesības",
      p: [
        `Varat lūgt savus datus apskatīt, labot, izgūt vai dzēst, kā arī iebilst pret to izmantošanu: rakstiet uz ${CONTACT}. Varat arī iesniegt sūdzību Datu valsts inspekcijā (www.dvi.gov.lv).`,
      ],
    },
    {
      h: "Izmaiņas",
      p: ["Kad šī politika mainās, mēs atjauninām šo lapu un tās datumu."],
    },
  ],
  terms: [
    {
      h: "Pakalpojums",
      p: [
        "MarketPulse rāda publiskas smaržu cenas no interneta veikaliem (Notino, Makeup.lv, 220.lv un Douglas), kas katru dienu tiek nolasītas automātiski. Mēs neesam saistīti ar šiem veikaliem un paši neko nepārdodam.",
        "Cenas var būt novecojušas vai kļūdainas. Pirms pirkuma vienmēr pārbaudiet cenu veikalā.",
      ],
    },
    {
      h: "Jūsu konts",
      p: [
        "Viens konts vienai personai. Glabājiet paroli drošībā; jūs atbildat par to, kas notiek jūsu kontā. Kontu varat dzēst jebkurā laikā savā profilā.",
      ],
    },
    {
      h: "Pro",
      p: [
        "Pro atver tirgus analītiku un datu eksportu. Pagaidām Pro piešķir administrators. Kad sāksies maksas plāni, cena un noteikumi tiks parādīti pirms maksājuma. Pro beidzas, kad beidzas tā termiņš.",
      ],
    },
    {
      h: "Godīga lietošana",
      p: [
        "Nelasiet MarketPulse ar robotiem vai skriptiem, nemēģiniet apiet tā drošību un nepārdodiet tā datus tālāk. Šādus kontus mēs varam atslēgt.",
      ],
    },
    {
      h: "MI asistents",
      p: ["Asistenta atbildes raksta dators, un tās var būt kļūdainas. Svarīgus faktus pārbaudiet."],
    },
    {
      h: "Atbildība",
      p: [
        "Pakalpojums tiek sniegts tāds, kāds tas ir. Ciktāl to atļauj likums, mēs neatbildam par zaudējumiem no lēmumiem, kas pieņemti, balstoties uz šeit redzamajām cenām. Mēs varam pakalpojumu mainīt vai pārtraukt.",
      ],
    },
    {
      h: "Likums",
      p: [`Šie noteikumi pakļaujas Latvijas Republikas likumiem. Jautājumi: ${CONTACT}.`],
    },
  ],
};

export default { en, lv };
