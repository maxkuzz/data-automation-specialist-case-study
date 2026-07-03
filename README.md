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


---

## 3. Výkonnostný problém v SQL transformácii

Podľa priloženého grafu je jasné, že s rastúcim objemom dát naráža súčasné riešenie na svoje limity. Zatiaľ čo na začiatku dopyt zbehol za hodinu, po pár dňoch to trvá skoro tri hodiny. Ak by sme to neriešili, čoskoro by transformácia nestihla dobehnúť do ranného reportingu

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
