"""Kategori sözlüğü. Kodlar content_categories.code ile birebir.

Her girdi: (regex, ağırlık 1-3). Regex normalize edilmiş metne uygulanır.
Türkçe ekler için kök + \\w* kullanılır; yanlış pozitif riski olan kökler
negatif lookahead ile daraltılır (sikke, siklet, götür ...).
"""

W = r"\b"

LEXICON: dict[str, list[tuple[str, int]]] = {
    "hakaret": [
        (r"\bamk\b|\baq\b|\bamq\b|\bamına\w*|\bamcık\w*", 3),
        (r"\bsik(?!ke|let|lon|ıntı)\w*", 3),
        (r"\borospu\w*|\bpiç\w*|\bkahpe\w*|\bpezevenk\w*|\byavşak\w*|\bşerefsiz\w*|\bgavat\w*", 3),
        (r"\bgöt(?!ür)\w*", 2),
        (r"\boç\b|\bmk\b", 2),
        (r"\bgerizekalı\w*|\bsalak\w*|\baptal\w*|\bmal herif|\bdangalak\w*|\bhıyar herif", 1),
        (r"\bfuck\w*|\bmotherfuck\w*|\bbitch\w*|\basshole\w*|\bcunt\w*|\bwhore\w*|\bslut\w*", 3),
        (r"\bshit\w*|\bidiot\w*|\bstupid\b|\bdumbass\b", 1),
    ],
    "nefret_soylemi": [
        (r"\bibne\w*|\bnonoş\w*|\bfaggot\w*|\bdyke\b|\btranny\b", 3),
        (r"\bnigg\w*|\bzenci\w*", 3),
        (r"\bpis (suriyeli|arap|kürt|ermeni|yahudi|rum|çingene|göçmen)\w*", 3),
        (r"\b(ermeni|yahudi|kürt|suriyeli) (dölü|tohumu|köpeği|soyu)\w*", 3),
        (r"\bçingene\w*|\bgevur\w*", 1),
        (r"\bretard\w*|\bözürlü\w*|\bspastik\w*", 2),
    ],
    "islamofobik": [
        (r"\bmüslüman terörist\w*|\bislamcı terör\w*|\bislam terör\w*", 3),
        (r"\byobaz\w*|\bsarıklı\w*|\bcihatçı\w*|\bharam zebani\w*", 2),
        (r"\bmuzzie\w*|\braghead\w*|\bsandnigg\w*", 3),
    ],
    "mustehcenlik": [
        (r"\bporn\w*|\bporno\w*|\bxxx\b|\bnsfw\b|\bonlyfans\w*|\bhentai\b|\bnudes?\b", 3),
        (r"\bsikiş\w*|\bsevişme\w*|\bescort\w*|\bfahişe\w*|\bmasaj salonu", 3),
        (r"\b(18|\+18|18\+)\s?(yaş üstü|only|\+)?\b(?=.*(video|içerik|content))", 2),
        (r"\bsexy\b|\bseksi\w*|\bsex\w*|\bseks\w*|\bhorny\b|\bazgın\w*|\bçıplak\w*", 2),
        (r"\bsugar (daddy|baby|mommy)\b|\bstrip\w*\b|\bthong\w*|\blingerie\b|\biç çamaşır\w*", 2),
        (r"\bhot (girls?|pics?)\b|\btumblr girls?\b|\bbikini\w*", 1),
    ],
    "siddet": [
        (r"\böldür(eceğim|ürüm|cem|ün|meli)\w*|\bgeberti\w*|\bkafanı (kır|kopar|patlat)\w*", 3),
        (r"\bkill (you|him|her|them|yourself)\b|\bshoot (you|up)\b|\bmurder\w*", 3),
        (r"\bbıçak\w*|\bsilah\w*|\btabanca\w*|\bkurşun\w*|\bmermi\w*|\bpompalı\w*", 2),
        (r"\bdövüş\w*|\bkavga\w*|\bdayak\w*|\bkatliam\w*|\bvahşet\w*|\bişkence\w*", 2),
        (r"\bgun\b|\bguns\b|\bknife\b|\bfight\w*|\bblood\w*|\bgore\b", 1),
    ],
    # DB'de ayrı kategori yok; en yüksek önceliğe sahip olduğu için ayrı kod,
    # panelde/DB'de 'siddet' altına + critical severity ile eşlenebilir
    "kendine_zarar": [
        (r"\bintihar\w*|\bkendimi (öldür|asa|kes)\w*|\bölmek istiyorum|\byaşamak istemiyorum", 3),
        (r"\bsuicid\w*|\bkill myself\b|\bself ?harm\w*|\bcutting myself\b|\bwant to die\b|\bkms\b", 3),
        (r"\bjilet\w*|\bbilek kes\w*", 2),
    ],
    "kumar": [
        (r"\bcasino\w*|\bkumar\w*|\bslot\w*|\brulet\w*|\bpoker\w*|\bblackjack\b|\bjackpot\w*", 3),
        (r"\bfree ?spin\w*|\bbedava spin\w*|\bçevrim(siz|li)\w*", 3),
    ],
    "bahis": [
        (r"\bbahis\w*|\biddaa\w*|\bbetting\b|\bbet\b|\bbahsi\w*", 3),
        (r"\b\w*bet\d+\w*|\b(1x|ix|jojo|mat|bets|super|tipo|holi|grand|mar|onwin|youwin)bet\w*", 3),
        (r"\bdeneme bonusu\w*|\byatırımsız bonus\w*|\bgüncel giriş\w*|\bkupon\w*|\boran(lar)?ı? yüksek", 2),
    ],
    "uyusturucu": [
        (r"\buyuşturucu\w*|\besrar\w*|\bkokain\w*|\beroin\w*|\bbonzai\w*|\bmetamfetamin\w*|\bhap atmak", 3),
        (r"\bweed\b|\bmarijuana\b|\bcannabis\b|\bganja\b|\bcocaine\b|\bheroin\b|\bmdma\b|\becstasy\b|\blsd\b|\bxanax\b|\bkush\b", 3),
        (r"\bot içmek|\bjoint\b|\bstoned\b|\bhigh af\b|\b420\b", 2),
    ],
    "bagimlilik": [
        (r"\balkol\w*|\brakı\w*|\bvotka\w*|\bviski\w*|\bsarhoş\w*|\bbira(lar|yı|ya|da|cı|cılar)?\b", 2),
        (r"\bvodka\b|\bwhiskey\b|\btequila\b|\bdrunk\b|\bbeer\b|\bcocktail\w*|\bshots?\b|🍸|🍺|🍻|🥃", 1),
        (r"\bsigara\w*|\bvape\w*|\belektronik sigara|\bnargile\w*|\bpuff\b|\bjuul\b", 2),
    ],
    # DB: oyun (default_action=warn) — tek başına risk değil, süre/yoğunluk sinyali
    "oyun": [
        (r"\b\w+ (saat|gece) aralıksız oyna\w*|\bsabaha kadar oyna\w*|\boyun bağımlı\w*", 3),
        (r"\boyna(yın|mak|dığım|dığıma|r)?\b|\boyunu?\b|\bherkes bunu oynuyor|\bkrallığını kur", 1),
        (r"\bdownload (now|free)\b|\bplay (now|free)\b|\bminecraft\b|\befootball\b|\bfortnite\b|\broblox\b|\bpubg\b|\bbrawl stars\b", 1),
    ],
    # DB: diger — beden algısı / estetik reklamı, tehlikeli trend/challenge
    "diger": [
        (r"\bliposuction\b|\bliposuction\w*|\bbotoks\w*|\bdolgu\w*|\bburun estetiği|\bestetik\w*|\bzayıflama\w*|\bkilo ver\w*", 2),
        (r"\bdying for a trend\b|\bchallenge\b|\bblackout\b|\bbayılma (oyunu|akımı)|\btehlikeli akım\w*", 2),
        (r"\bkonum\w* (paylaş|aç)\w*|\bdm('?den)? yaz\w*|\bgizli hesap\w*", 1),
    ],
}

# Kategori → varsayılan önem çarpanı (veli için öncelik)
CATEGORY_PRIORITY = {
    "kendine_zarar": 3.0,
    "siddet": 1.5,
    "uyusturucu": 1.5,
    "mustehcenlik": 1.3,
    "nefret_soylemi": 1.3,
    "islamofobik": 1.3,
    "hakaret": 1.0,
    "bahis": 1.2,
    "kumar": 1.2,
    "bagimlilik": 0.8,
    "oyun": 0.6,
    "diger": 0.9,
}

CATEGORY_LABEL = {
    "hakaret": "Hakaret",
    "nefret_soylemi": "Nefret Söylemi",
    "islamofobik": "İslamofobik",
    "mustehcenlik": "Müstehcenlik",
    "siddet": "Şiddet",
    "kendine_zarar": "Kendine Zarar",
    "kumar": "Kumar",
    "bahis": "Bahis",
    "uyusturucu": "Uyuşturucu",
    "bagimlilik": "Bağımlılık (alkol/tütün)",
    "oyun": "Oyun",
    "diger": "Diğer (estetik / tehlikeli trend)",
}

# DB content_categories.code eşlemesi (kendine_zarar DB'de yok → siddet + critical)
DB_CODE = {k: k for k in CATEGORY_LABEL} | {"kendine_zarar": "siddet"}
