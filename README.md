## 1. Návrh dátového modelu pre e-commerce platformu

### 1) Dátový model vo forme ER diagramu
![ER Diagram](images/ER%20diagram.png)

V tabuľke `Orders` sa nenachádza stĺpec `order_items`, pretože jednotlivé položky objednávky sú uložené v samostatnej tabuľke `OrderItems`. Jedna objednávka môže obsahovať viacero produktov, preto je tento vzťah modelovaný ako väzba 1:N medzi tabuľkami `Orders` a `OrderItems`
### 2) Dimenzie a faktové tabuľky pre analytické potreby
![Star schema](images/Star%20schema.png)

Pridal som aj tabuľku DimCustomer, pretože podľa môjho názoru je v e-commerce užitočná na analytické účely. Umožňuje analyzovať predaje podľa zákazníkov, rozlišovať nových a existujúcich zákazníkov alebo sledovať predaje podľa dátumu registrácie

| Data Warehouse | Source OLTP | Transformation |
|---|---|---|
| `dim_time` | `orders.order_date` | Extrahovať unikátne dátumy objednávok a odvodiť `date_id`, `date`, `day`, `month`, `quarter`, `year` |
| `dim_product` | `products` + `categories` | Skopírovať atribúty produktu a denormalizovať hierarchiu kategórií do produktovej dimenzie |
| `dim_customer` | `customers` | Skopírovať atribúty zákazníka a spojiť `first_name` + `last_name` do poľa `customer_name` |
| `dim_region` | adresné polia z `customers` | Extrahovať unikátne kombinácie `country`, `region`, `city`, `postal_code` a vygenerovať `region_id` |
| `fact_sales` | `orders` + `order_items` + `customers` | Vytvoriť jeden faktový riadok pre každú položku objednávky, dohľadať kľúče dimenzií a vypočítať `total_amount = quantity * unit_price` |

### 3) Primárne a cudzie kľúče

| Table | Primary Key | Foreign Key |
|---|---|---|
| `categories` | `category_id` | `parent_category_id → categories.category_id` |
| `products` | `product_id` | `category_id → categories.category_id` |
| `customers` | `customer_id` | - |
| `orders` | `order_id` | `customer_id → customers.customer_id` |
| `order_items` | `order_item_id` | `order_id → orders.order_id`, `product_id → products.product_id` |
| `transactions` | `transaction_id` | `order_id → orders.order_id` |

### 4) SQL schéma
Schéma sa nachádza v súbore `SQL schema.txt` - PostgreSQL


<br>

### Ako by ste riešili historické zmeny (napr. zmena ceny produktu, adresa zákazníka)?


Pri cene produktu je najdôležitejšie zachovať cenu platnú v momente nákupu. Preto je cena položky uložená v tabuľke `order_items` ako `unit_price`. Ak sa aktuálna cena produktu v tabuľke `products` zmení, historické objednávky zostanú nezmenené. Ak by bolo potrebné sledovať aj históriu cenníkových cien, doplnil by som samostatnú tabuľku `product_price_history` so stĺpcami `product_id, price, valid_from, valid_to` a `is_current`

Pri adrese zákazníka by som neprepisoval historické údaje bez zachovania pôvodnej hodnoty. Základná tabuľka `customers` by obsahovala aktuálne údaje zákazníka a zmeny adresy by som ukladal do samostatnej tabuľky `customer_address_history`. Táto tabuľka by obsahovala `customer_id, adresné polia, valid_from, valid_to` a `is_current`, aby bolo možné určiť, ktorá adresa bola platná v čase konkrétnej objednávky

V analytickej vrstve by som pri meniacich sa dimenziách použil Slowly Changing Dimension (SCD) Type 2. Pri zmene atribútu by sa nevykonal update pôvodného záznamu, ale vytvorila by sa nová verzia záznamu s novým obdobím platnosti

<br>

---
## 2. Analytická úloha

Výstupy analytickej úlohy sú dostupné tu:

* Prístup do Keboola projektu bol zdieľaný cez e-mailovú pozvánku
* [Tableau dashboard](https://dub01.online.tableau.com/t/maximkuznetsov0000-64ea51bb38/views/GymBeamCaseStudy-AnalyticsDashboard/Top20CitiesbyAOVTable?:origin=card_share_link&:embed=n)

Pred samotnou prácou v Keboole som si najprv spravil jednoduchú EDA analýzu v súbore [`eda_sales_data.ipynb`](eda_sales_data.ipynb). Cieľom bolo pochopiť štruktúru vstupných tabuliek, skontrolovať počty riadkov, základné dátové typy a možné problémy v dátach, napríklad chýbajúce hodnoty

Následne som obe vstupné tabuľky `sales_order` a `sales_order_item` nahral do Kebooly. Ako prvý krok som vytvoril transformáciu [`01_prepare_order_items_enriched`](https://connection.us-east4.gcp.keboola.com/admin/projects/6042/transformations-v2/keboola.python-transformation-v2/01kwhg9p9y8dmkdhe2btzvbs54), ktorá tieto dve tabuľky spojí na úrovni položiek objednávky. V tejto transformácii sa zároveň čistia dátové typy, normalizuje sa PSČ, vytvárajú sa pomocné dátumové stĺpce a počítajú sa základné metriky ako `revenue_eur`, `cost_eur`, `margin_eur` a `margin_pct`.

### 2.1. Doplnenie názvu mesta k objednávke

V poskytnutých dátach sa nachádzalo iba PSČ, ale nie názov mesta. Na doplnenie mesta som použil externý GeoNames postal code dataset. Dataset som rozdelil podľa krajín do troch súborov pre CZ, SK a HU, ktoré sa nachádzajú v priečinku [`Postal Codes`](Postal%20Codes/).

Pri práci s PSČ som narazil na problém granularity. Jedno PSČ môže byť v referenčných dátach priradené k viacerým miestam alebo častiam miest. Preto som pripravil skript [`build_postal_code_reference_normalized.py`](build_postal_code_reference_normalized.py), ktorý vytvorí normalizovanú referenčnú tabuľku [`postal_code_reference_normalized.csv`](Postal%20Codes/postal_code_reference_normalized.csv). Táto tabuľka obsahuje reprezentatívny názov mesta, pôvodný názov mesta, informáciu o spôsobe normalizácie a úroveň dôveryhodnosti normalizácie.

Na základe tejto referenčnej tabuľky som v Keboole vytvoril transformáciu [`02_enrich_orders_with_city`](https://connection.us-east4.gcp.keboola.com/admin/projects/6042/transformations-v2/keboola.python-transformation-v2/01kwhyc9wdwfng51z71k9t4z9s). Táto transformácia doplní k položkám objednávok mesto, región, okres, zemepisnú šírku a dĺžku. Zároveň označuje prípady, kde PSČ nebolo možné spárovať alebo bolo nevalidné.

Ďalším krokom bola transformácia [`03_city_order_metrics`](https://connection.us-east4.gcp.keboola.com/admin/projects/6042/transformations-v2/keboola.python-transformation-v2/01kwhzttvkdwe5zm8f0xz0p09k). Tá agreguje dáta na úroveň mesta a počíta metriky ako počet objednávok, počet položiek objednávok, tržby a AOV. Výstup tejto transformácie používam vo vizualizácii TOP 20 miest podľa AOV a zároveň aj na mape, kde je zobrazený počet vytvorených objednávok podľa miest.

### 2.2. Výpočet priemernej mesačnej marže produktu

Pre výpočet priemernej mesačnej marže produktu som vytvoril transformáciu [`04_product_monthly_margin`](https://connection.us-east4.gcp.keboola.com/admin/projects/6042/transformations-v2/keboola.python-transformation-v2/01kwkq5jt4t74e1w70t9wkf58p). Vstupom je obohatená tabuľka `order_items_enriched`, kde sú už vypočítané tržby, náklady a marža na úrovni položky objednávky.

Transformácia agreguje dáta podľa `product_id` a mesiaca. Pre každý produkt a mesiac počíta počet objednávok, predané množstvo, tržby, náklady, celkovú maržu, percentuálnu maržu a priemernú maržu na jednu predanú jednotku. Výstupná tabuľka `product_monthly_margin` sa následne používa v Tableau na vizualizáciu vývoja priemernej mesačnej marže v čase s možnosťou filtrovať konkrétny produkt.

### 2.3. Pricing stratégia

V tejto časti som najprv narazil na dôležité obmedzenie dát. V poskytnutých tabuľkách sa nachádza iba `product_id`, ale nie názov produktu, kategória, značka ani veľkosť balenia. Preto nie je možné presne určiť, ktoré produkty patria do food sortimentu. Z tohto dôvodu som pre účely analýzy identifikoval TOP 5 produktov podľa tržieb zo všetkých dostupných `product_id` a následne som ich priradil k pravdepodobným food / sports nutrition segmentom podľa cenovej hladiny.

Ako metriku pre "dopad na tržby" som zvolil celkové tržby produktu:

`dopad na tržby = SUM(revenue_eur)`

Túto metriku som zvolil preto, že priamo ukazuje, koľko tržieb daný produkt v sledovanom období priniesol. TOP produkty som vypočítal v Keboole v transformácii `05_top_revenue_products` na základe tabuľky `order_items_enriched`.

#### TOP 5 produktov podľa tržieb

| Rank | product_id | Revenue (EUR) | Revenue share | Median price (EUR) | Avg. cost (EUR) | Margin % | Assumed segment |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | `0f89562a368bb1e822b7b3075fa7e18c` | 17 555.03 | 1.56% | 35.04 | 24.43 | 32.35% | whey protein / premium protein |
| 2 | `2f039d8c907a9c41754a2d11cc799ac1` | 14 114.89 | 1.25% | 20.63 | 12.51 | 40.39% | protein bars / protein snack |
| 3 | `95bd8e77c045c2d6cec27fb8a9c0c8b4` | 13 097.75 | 1.16% | 9.40 | 3.94 | 61.92% | peanut butter / nut spread |
| 4 | `dc3710567650e9d59a621c71e4483778` | 10 550.90 | 0.93% | 35.08 | 24.70 | 31.86% | isolate protein / premium protein |
| 5 | `c7864360e1c1a27bdc4e28294dc3082f` | 10 138.70 | 0.90% | 22.70 | 8.20 | 61.54% | vegan protein / functional food |

#### Konkurenčný benchmark

Keďže nepoznám presný názov produktu za jednotlivými `product_id`, produkty nižšie používam ako porovnateľné benchmark produkty, nie ako presnú zhodu. Ceny konkurencie som porovnával hlavne cez jednotkovú cenu, napríklad EUR/kg. Pri proteínových tyčinkách je porovnanie menej presné, pretože sa líši veľkosť balenia a gramáž jednej tyčinky.

| product_id | Assumed GymBeam product | Dataset median price | GymBeam current price | Myprotein SK comparable | Myprotein price | Nutrend SK comparable | Nutrend price | Confidence |
|---|---|---:|---:|---|---:|---|---:|---|
| `0f89562a368bb1e822b7b3075fa7e18c` | True Whey - GymBeam 1000g | 35.04 | 31.95 | Impact Whey Protein Milkshake | 57.46 EUR/kg | 100% Whey Protein | 48.75 EUR/kg | Medium/High |
| `dc3710567650e9d59a621c71e4483778` | Pure IsoWhey - GymBeam 1000g | 35.08 | 37.95 | Impact Whey Izolát | 96.66 EUR/kg | Iso Whey Prozero | 64.00 EUR/kg | Medium/High |
| `c7864360e1c1a27bdc4e28294dc3082f` | Ultimate Vegan Protein - GymBeam 1000g | 22.70 | 24.95 | Vegánska proteínová zmes 1000g | 41.99 | Delicious Vegan Protein | 51.11 EUR/kg | Medium |
| `2f039d8c907a9c41754a2d11cc799ac1` | Proteínová tyčinka Excelent 18 x 85g | 20.63 | 27.30 | 6-vrstvová proteínová tyčinka 12 x 60g | 45.99 | Excelent Protein Bar 18 x 85g | 37.80 | Low/Medium |
| `95bd8e77c045c2d6cec27fb8a9c0c8b4` | Arašidové maslo - GymBeam 1000g | 9.40 | 5.95 | Prírodné arašidové maslo 1000g | 16.99 | Denuts Cream arašidové maslo | 12.00 EUR/kg | Low/Medium |

#### Pricing pravidlo

Ako základ pre aktuálnu internú cenu som použil `median_price_eur` z datasetu, pretože ide o historickú predajnú cenu za rok 2024 a medián je menej citlivý na extrémne promo ceny. Ceny z webov konkurencie používam iba ako externý trhový benchmark. Rozdiel medzi cenou v datasete a cenou na webe môže byť spôsobený tým, že dáta sú z roku 2024, aktuálne webové ceny sa menia, prebiehajú akcie alebo ide iba o porovnateľný produkt.

Pri odporúčaní ceny som použil jednoduché pravidlo:

`margin_floor_price = avg_cost_eur / (1 - minimum_margin)`

Kde `minimum_margin = 30%`. Cena by nemala klesnúť pod túto hranicu, aby bola chránená minimálna marža. Zároveň som neprenášal celé cenové rozdiely voči konkurencii naraz, pretože pri anonymných produktoch bez presného produktového katalógu by to bolo príliš agresívne. Pri väčších rozdieloch voči trhu preto odporúčam postupnú zmenu ceny.

#### Odporúčanie cien

| product_id | Current price (dataset median) | Recommended price | Change % | Expected impact |
|---|---:|---:|---:|---|
| `0f89562a368bb1e822b7b3075fa7e18c` | 35.04 | 35.99 | +2.7% | Mierne zvýšenie ceny. Produkt je stále lacnejší ako porovnateľní konkurenti a marža zostáva nad minimálnou hranicou. |
| `2f039d8c907a9c41754a2d11cc799ac1` | 20.63 | 22.69 | +10.0% | Postupné zvýšenie ceny. Segment protein snackov má vyššie ceny u konkurencie, ale confidence matchu je nižšia, preto by som cenu zvyšoval opatrne. |
| `95bd8e77c045c2d6cec27fb8a9c0c8b4` | 9.40 | 9.40 | 0.0% | Cenu by som zatiaľ nemenil. Produkt má vysokú maržu, ale porovnanie s arašidovým maslom má nižšiu istotu a aktuálna cena GymBeam produktu je výrazne nižšia. |
| `dc3710567650e9d59a621c71e4483778` | 35.08 | 37.95 | +8.2% | Zvýšenie ceny smerom k aktuálnej cene porovnateľného GymBeam premium proteínu. Produkt zostáva výrazne lacnejší ako konkurencia a marža sa zlepší. |
| `c7864360e1c1a27bdc4e28294dc3082f` | 22.70 | 24.95 | +9.9% | Zvýšenie na úroveň aktuálneho porovnateľného GymBeam vegan proteínu. Benchmark konkurencie naznačuje priestor na vyššiu cenu. |

#### Ako by som tento prístup škáloval

Pre škálovanie na celý food sortiment by bolo potrebné doplniť produktový katalóg s mapovaním `product_id`, názvu produktu, kategórie, značky, veľkosti balenia a jednotky porovnania. Pravidelne by som zbieral aj ceny konkurencie, ideálne denne alebo niekoľkokrát týždenne pri produktoch s vysokým obratom. Pri každom produkte by som počítal aktuálnu cenu, náklad, maržu, cenovú pozíciu voči konkurencii a elasticitu dopytu, ak by bola dostupná. Najväčším úzkym miestom by bola kvalita párovania produktov s konkurenciou, pretože produkty sa môžu líšiť balením, zložením alebo promo mechanikou. Zaviedol by som preto confidence score pre každý match a produkty s nízkou istotou by vyžadovali manuálnu kontrolu. Ako guardrails by som nastavil minimálnu maržu, maximálnu jednorazovú zmenu ceny a pravidlo, že cena sa nemení automaticky pri nízkej kvalite benchmarku. Pri strategických alebo veľmi predávaných produktoch by odporúčania pred nasadením kontroloval category manager.


---

## 3. Výkonnostný problém v SQL transformácii



### Čo je príčinou spomalenia

* **Full Table Scan:** SQL dopyt pravdepodobne pri každom spustení prechádza kompletne celú databázu od nuly (všetky historické objednávky z tabuliek `sales_order` a `sales_order_item`)
* **Chýbajúce indexy:** Ak stĺpce, cez ktoré spájame tabuľky (napr. `order_id` v `JOIN`-e) alebo cez ktoré filtrujeme dáta, nemajú vytvorené indexy, databáza musí mechanicky prehľadávať milióny riadkov jeden po druhom
* **Problém s pamäťou:** Keďže robíme náročné operácie ako `GROUP BY` alebo `ORDER BY` nad čoraz väčším datasetom, dáta sa už nezmestia do operačnej pamäte. Databáza si ich preto začala odkladať na pomalý pevný disk, čo proces extrémne spomaľuje



### Ako by som to reálne vyriešil

#### 1. Zmena logiky na inkrementálne načítanie
Toto je najdôležitejší krok. Prekopal by som transformáciu tak, aby sme zakaždým nepočítali celú históriu 

Pomocou technického stĺpca (napr. `updated_at`) by sme z produkčnej databázy ťahali iba nové objednávky alebo tie, ktoré sa za posledných 24 hodín zmenili (napr. zmena stavu objednávky). Do DWH nové riadky vložíme, zmenené aktualizujeme. Výrazne tým odľahčíme disk aj procesor

#### 2. Optimalizácia kódu a indexácia
Pred úpravou kódu by som analyzoval exekučný plán pomocou nástroja **EXPLAIN ANALYZE**. Ten presne ukáže, na ktorom kroku databáza najviac "visí" a kde presne dochádza k neefektívnemu úplnému skenovaniu tabuliek. 

Následne by som nechal pridať chýbajúce indexy na spojovacie kľúče (napr. `order_id`). Samotný SQL kód by som tiež prečistil – vyhodil zbytočné vnorené poddopyty, nahradil ich prehľadnejšími CTE štruktúrami 

#### 3. Škálovanie infraštruktúry (Horizontálne a Vertikálne)
* **Vertikálne škálovanie:** Ak Keboola pod kapotou využíva napríklad Snowflake, môžeme na čas behu tejto transformácie automaticky navýšiť výkon výpočtového skladu.
* **Horizontálne škálovanie:** Pri obrovskom raste dát by som navrhol prechod na MPP architektúru (Massively Parallel Processing). Dáta sa vtedy rozdistribuujú na viacero serverov (uzlov) a dopyt nad tabuľkami objednávok beží na viacerých strojoch paralelne a naraz. 
</br></br>*Tento krok je však racionálne implementovať iba v prípade, že firma disponuje potrebnými finančnými a technickými zdrojmi na správu takéhoto klastra, keďže prevádzka distribuovaných systémov výrazne zvyšuje náklady na infraštruktúru.*
