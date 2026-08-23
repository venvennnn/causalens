from __future__ import annotations

from datetime import datetime, timedelta

from app.models.schemas import Article, CausalEdge, Entity, Event
from app.services.evidence import annotate_cross_border, calculate_evidence_score
from app.sources.adapters import article_id_for

NOW = datetime(2026, 8, 23, 8, 30, 0)


def _body(paragraphs: list[str]) -> str:
    text = "\n\n".join(paragraphs)
    if len(text) < 250:
        text += " Regional officials and corporate filings independently corroborate the timeline, capital figures and stated commercial rationale described above."
    return text


def _article(
    url: str,
    title: str,
    source: str,
    country: str,
    published: datetime,
    body: list[str],
    *,
    author: str | None = None,
    category: list[str] | None = None,
    summary: str | None = None,
) -> Article:
    text = _body(body)
    return Article(
        id=article_id_for(url),
        title=title,
        url=url,
        source=source,
        country=country,
        language="en",
        published_at=published,
        author=author,
        category=category or ["Business"],
        summary=summary or body[0][:240],
        body=text,
        image_url=None,
        ingested_at=NOW,
        raw={"provider": "seed", "demo": True},
    )


def seed_articles() -> list[Article]:
    return [
        _article(
            "https://www.channelnewsasia.com/business/singapore-data-centre-power-land-constraints-ai-2026",
            "Singapore data centre pipeline tightens as power and land constraints bite",
            "CNA",
            "Singapore",
            NOW - timedelta(days=6),
            [
                "Singapore's remaining data-centre capacity is being rationed as grid connection queues lengthen and suitable industrial land becomes scarce, according to industry filings and energy-market officials.",
                "Operators say new AI training and inference loads require power densities that existing parks were not designed for. Several postponed commissioning dates have been disclosed to customers in the financial district and in the western industrial belt.",
                "Policy agencies have signalled that incremental capacity will favour high-efficiency facilities, pushing some hyperscale demand into neighbouring Johor while keeping core financial workloads onshore.",
            ],
            author="Reuters",
            category=["Business", "Technology"],
        ),
        _article(
            "https://theedgemalaysia.com/node/815901",
            "Johor-Singapore SEZ draws fresh AI data centre capital as Singapore capacity tightens",
            "The Edge Malaysia",
            "Malaysia",
            NOW - timedelta(days=5),
            [
                "Malaysia's Johor-Singapore Special Economic Zone is attracting a new wave of AI data-centre commitments as developers cite cheaper land, available power and proximity to Singapore's financial and cloud customers.",
                "State investment officials said multiple hyperscale and enterprise campuses have entered advanced site selection around Sedenak and the Iskandar corridor, with grid reinforcement now treated as a binding constraint on timelines.",
                "Bankers tracking the corridor say cross-border fibre and subsea extensions are being scoped alongside the campuses, linking Johor capacity to Singapore interconnection points.",
            ],
            author="The Edge Staff",
            category=["Corporate", "Technology", "Economy"],
        ),
        _article(
            "https://theedgemalaysia.com/node/815507",
            "Alibaba plans US$10.2 billion share placement to fund AI expansion",
            "The Edge Malaysia",
            "Malaysia",
            NOW - timedelta(hours=18),
            [
                "Alibaba Group is planning a share placement of about US$10.2 billion to fund accelerated artificial-intelligence development, including cloud infrastructure and model training capacity, people familiar with the matter said.",
                "The company has been increasing capital expenditure on AI after demand for cloud computing and proprietary models outpaced earlier capacity plans. Part of the incremental compute is expected to support customers across Asia, including Singapore and other Southeast Asian markets.",
                "Regional investors are watching whether the fundraising tightens competition for GPUs and wholesale data-centre space in Malaysia and Singapore, where Alibaba Cloud already operates or has announced facilities.",
            ],
            author="Bloomberg/The Edge",
            category=["Corporate", "Technology", "World"],
        ),
        _article(
            "https://www.channelnewsasia.com/business/alibaba-cloud-southeast-asia-expansion-ai",
            "Alibaba Cloud flags further Southeast Asia capacity after AI fundraising",
            "CNA",
            "Singapore",
            NOW - timedelta(hours=14),
            [
                "Alibaba Cloud said additional capital from a planned share placement would be used to expand AI-ready capacity for Asia-Pacific customers, with Southeast Asia among the growth markets cited by executives.",
                "The company already serves enterprise and public-sector clients from Singapore and has been evaluating additional availability in Malaysia as Singapore power allocations remain tight.",
                "Channel checks with colocation brokers indicate wholesale inquiries linked to Chinese hyperscalers have increased in Johor and in Singapore's remaining reserved capacity tranches.",
            ],
            category=["Business", "Technology"],
        ),
        _article(
            "https://theedgemalaysia.com/node/815880",
            "YTL and NVIDIA-linked AI supercomputer project advances in Malaysia",
            "The Edge Malaysia",
            "Malaysia",
            NOW - timedelta(days=4),
            [
                "YTL Power's NVIDIA-linked AI supercomputing initiative in Malaysia is moving from announcement to procurement, with local contractors shortlisted for power, cooling and campus works.",
                "The project is being positioned as a regional training cluster that can serve Singapore-based model developers who cannot secure sufficient onshore megawatts.",
                "Analysts say the supercomputer and adjacent commercial data halls will compete for the same high-voltage supply that Johor's new AI campuses also require.",
            ],
            category=["Corporate", "Technology"],
        ),
        _article(
            "https://www.channelnewsasia.com/business/microsoft-sea-data-centre-investment-ai",
            "Microsoft deepens Southeast Asia cloud investment as AI demand accelerates",
            "CNA",
            "Singapore",
            NOW - timedelta(days=3),
            [
                "Microsoft is expanding cloud and AI infrastructure serving Southeast Asia, citing enterprise demand for Copilot workloads and sovereign-ready hosting options in Singapore.",
                "People familiar with the company's regional capacity plan said overflow and disaster-recovery capacity continues to be mapped into southern Malaysia because Singapore sites cannot absorb every incremental megawatt.",
                "The investment is part of a broader hyperscaler capex cycle that is also lifting demand for networking gear, liquid cooling and specialised construction labour across the corridor.",
            ],
            category=["Business", "Technology"],
        ),
        _article(
            "https://vir.com.vn/electronics-fdi-vietnam-semiconductor-packaging-ai-159401.html",
            "Vietnam electronics FDI climbs as AI hardware demand filters into packaging and assembly",
            "Vietnam Investment Review",
            "Vietnam",
            NOW - timedelta(days=2),
            [
                "Foreign direct investment into Vietnam's electronics and semiconductor-related assembly has accelerated this quarter as global AI hardware demand filters into packaging, testing and component supply.",
                "Industrial park operators in Bac Ninh, Hai Phong and Ho Chi Minh City reported new inquiries from contract manufacturers serving data-centre and consumer AI devices.",
                "Trade officials said the inflows are part of a China-plus-one shift that is also lifting supporting industries such as precision plastics, chemicals and logistics.",
            ],
            category=["Investment", "Manufacturing"],
        ),
        _article(
            "https://vir.com.vn/foxconn-suppliers-expand-vietnam-production-ai-servers-159266.html",
            "Contract manufacturers expand Vietnam output for AI servers and networking gear",
            "Vietnam Investment Review",
            "Vietnam",
            NOW - timedelta(days=1, hours=6),
            [
                "Several large electronics manufacturers are adding production lines in Vietnam dedicated to AI servers, switches and power equipment, according to provincial investment boards.",
                "The expansions follow multi-year customer forecasts from cloud providers and networking vendors that have lengthened order books into 2027.",
                "Exporters said the new capacity will increase outbound shipments through Hai Phong and Cai Mep, with some high-value modules still finishing in Malaysia or Singapore before reaching end customers.",
            ],
            category=["Manufacturing", "Exports"],
        ),
        _article(
            "https://www.channelnewsasia.com/business/gpu-supply-tightness-asia-data-centres",
            "GPU lead times still stretching Asia data-centre commissioning calendars",
            "CNA",
            "Singapore",
            NOW - timedelta(days=2, hours=4),
            [
                "Accelerator supply remains a binding constraint for new AI halls in Asia, with procurement leads for high-end GPUs still measured in multiple quarters, according to systems integrators in Singapore.",
                "Even where power and land are available, operators are staggering hall openings to match chip deliveries rather than building dark capacity.",
                "The tightness is affecting both Singapore campuses and overflow sites in Johor, delaying some contracted go-live dates into late 2026 and 2027.",
            ],
            category=["Technology", "Supply Chain"],
        ),
        _article(
            "https://theedgemalaysia.com/node/815940",
            "Tenaga and state utilities plan grid upgrades for Johor data-centre load",
            "The Edge Malaysia",
            "Malaysia",
            NOW - timedelta(days=1),
            [
                "Malaysia's utilities are advancing grid reinforcement plans to serve concentrated data-centre demand in Johor, including new substations and high-voltage corridors into Iskandar.",
                "Officials warned that without the upgrades, several announced AI campuses would slip. Power planners are also modelling tariff and fuel-mix effects if the load materialises faster than generation additions.",
                "Local energy prices in industrial tariffs are already under watch as a potential cost inflator for operators comparing Johor against Singapore and Indonesia.",
            ],
            category=["Energy", "Infrastructure"],
        ),
        _article(
            "https://www.channelnewsasia.com/business/singapore-data-centre-reits-ai-demand",
            "Singapore data-centre landlords reprice assets as AI wholesale demand firms",
            "CNA",
            "Singapore",
            NOW - timedelta(hours=20),
            [
                "Listed data-centre landlords and REITs in Singapore are marking firmer rents and longer contracted tenors as AI wholesale demand collides with constrained new supply.",
                "Brokers said remaining powered shells are being bid by cloud and financial-services tenants who prefer onshore latency even as overflow capacity is built in Johor.",
                "Equity analysts covering the sector raised occupancy and rental growth assumptions after a cluster of hyperscale capacity announcements across the Causeway.",
            ],
            category=["Markets", "Property"],
        ),
        _article(
            "https://www.channelnewsasia.com/business/indonesia-data-centre-incentives-ai-corridor",
            "Indonesia weighs data-centre incentives as Batam-Singapore compute corridor takes shape",
            "CNA",
            "Singapore",
            NOW - timedelta(hours=10),
            [
                "Indonesian officials are weighing fiscal and power incentives for data centres as investors look at Batam and nearby islands as a third node in a Singapore-Johor compute corridor.",
                "Subsea and terrestrial fibre projects already connect the three jurisdictions. Developers argue that Indonesia can absorb later-phase AI inference and disaster-recovery loads if permitting and electricity contracts clear.",
                "The discussion follows a string of Malaysia campus announcements that have made land-and-power scarcity in Singapore more visible to regional capital.",
            ],
            category=["Business", "Regional"],
        ),
        _article(
            "https://vir.com.vn/vietnam-ai-software-parks-hanoi-hcmc-expansion-159410.html",
            "Hanoi and HCMC AI software parks expand as hardware FDI deepens",
            "Vietnam Investment Review",
            "Vietnam",
            NOW - timedelta(hours=30),
            [
                "Municipal authorities in Hanoi and Ho Chi Minh City are expanding AI software parks and talent programmes alongside the hardware manufacturing boom.",
                "Universities and industrial parks are pairing semiconductor packaging investments with applied AI curricula aimed at keeping higher-value design and operations work in-country.",
                "Recruiters report rising cross-border movement of engineers between Vietnam, Singapore and Malaysia as regional AI operations scale.",
            ],
            category=["Technology", "Investment"],
        ),
        _article(
            "https://theedgemalaysia.com/node/815970",
            "Malaysia semiconductor packaging houses see AI-related utilisation rebound",
            "The Edge Malaysia",
            "Malaysia",
            NOW - timedelta(hours=22),
            [
                "Malaysian outsourced semiconductor assembly and test houses reported higher utilisation tied to AI networking, power-management and edge devices, extending a recovery that began in late 2025.",
                "Management commentary linked the rebound both to Vietnam and China-plus-one board builds and to data-centre hardware demand originating from Singapore and Johor campuses.",
                "Several firms are evaluating additional advanced packaging tools, which would deepen Malaysia's role in the regional AI hardware chain.",
            ],
            category=["Corporate", "Technology"],
        ),
        _article(
            "https://www.channelnewsasia.com/business/imda-mas-ai-infrastructure-guidelines-singapore",
            "Singapore agencies tighten AI infrastructure guidance for onshore compute",
            "CNA",
            "Singapore",
            NOW - timedelta(days=3, hours=2),
            [
                "Singapore's IMDA and financial regulators issued updated guidance on AI infrastructure, energy efficiency and operational resilience for onshore compute used by financial institutions.",
                "The rules do not freeze new capacity but they raise the bar for efficiency and concentration risk, reinforcing the split between latency-sensitive onshore workloads and regional overflow.",
                "Banks and cloud providers said the guidance was a response to grid constraints and to the rapid rise of model-hosting inside the city-state.",
            ],
            category=["Regulation", "Technology"],
        ),
        _article(
            "https://theedgemalaysia.com/node/815990",
            "Johor industrial power watch: data-centre load lifts tariff debate",
            "The Edge Malaysia",
            "Malaysia",
            NOW - timedelta(hours=8),
            [
                "A sharper debate has opened in Johor over whether concentrated data-centre load will pressure industrial power prices and water resources even as it supports investment headlines.",
                "Business groups want transparent connection queues and cost-reflective tariffs so manufacturing is not crowded out by AI campuses.",
                "The discussion is a direct response to utility upgrade plans and to the pipeline of Johor-Singapore SEZ data-centre projects disclosed this month.",
            ],
            category=["Energy", "Economy"],
        ),
    ]


def _entity(name: str, type_: str, country: str | None = None) -> Entity:
    return Entity(id=article_id_for(name + type_), name=name, type=type_, country=country)


def seed_events(articles: list[Article]) -> list[Event]:
    by_url = {article.url: article.id for article in articles}

    def ids(*urls: str) -> list[str]:
        return [by_url[url] for url in urls if url in by_url]

    return [
        Event(
            id="evt_hyperscaler_capex",
            title="Global hyperscaler AI capex cycle accelerates",
            summary="Cloud and internet platforms are raising AI infrastructure spending, tightening competition for GPUs, power and regional data-centre capacity.",
            event_date=NOW - timedelta(days=7),
            countries=["United States", "China", "Singapore"],
            companies=["Microsoft", "Alibaba", "NVIDIA"],
            industries=["Cloud", "AI", "Data centers"],
            entities=[
                _entity("Microsoft", "COMPANY", "United States"),
                _entity("Alibaba", "COMPANY", "China"),
                _entity("NVIDIA", "COMPANY", "United States"),
            ],
            source_article_ids=ids(
                "https://www.channelnewsasia.com/business/microsoft-sea-data-centre-investment-ai",
                "https://theedgemalaysia.com/node/815507",
            ),
            confidence=0.9,
            event_type="INVESTMENT",
        ),
        Event(
            id="evt_sg_power_land",
            title="Singapore rations new data-centre capacity on power and land limits",
            summary="Grid queues and scarce industrial land are delaying AI halls in Singapore and pushing overflow demand across the Causeway.",
            event_date=NOW - timedelta(days=6),
            countries=["Singapore"],
            companies=[],
            industries=["Data centers", "Energy", "Cloud"],
            entities=[_entity("Singapore", "COUNTRY", "Singapore")],
            source_article_ids=ids(
                "https://www.channelnewsasia.com/business/singapore-data-centre-power-land-constraints-ai-2026",
                "https://www.channelnewsasia.com/business/imda-mas-ai-infrastructure-guidelines-singapore",
            ),
            confidence=0.93,
            event_type="SUPPLY_DISRUPTION",
        ),
        Event(
            id="evt_johor_sez_dc",
            title="Johor-Singapore SEZ AI data-centre cluster accelerates",
            summary="Developers are committing AI campuses in Johor to serve Singapore customers who cannot secure onshore megawatts.",
            event_date=NOW - timedelta(days=5),
            countries=["Malaysia", "Singapore"],
            companies=["YTL Power"],
            industries=["Data centers", "Infrastructure", "Cloud"],
            entities=[
                _entity("Johor", "CITY", "Malaysia"),
                _entity("YTL Power", "COMPANY", "Malaysia"),
            ],
            source_article_ids=ids(
                "https://theedgemalaysia.com/node/815901",
                "https://www.channelnewsasia.com/business/singapore-data-centre-power-land-constraints-ai-2026",
            ),
            confidence=0.91,
            event_type="EXPANSION",
        ),
        Event(
            id="evt_ytl_nvidia",
            title="YTL-NVIDIA AI supercomputer moves into procurement",
            summary="Malaysia's NVIDIA-linked supercomputing campus is entering construction and equipment procurement as a regional training hub.",
            event_date=NOW - timedelta(days=4),
            countries=["Malaysia"],
            companies=["YTL Power", "NVIDIA"],
            industries=["AI", "Data centers", "Energy"],
            entities=[
                _entity("YTL Power", "COMPANY", "Malaysia"),
                _entity("NVIDIA", "COMPANY", "United States"),
            ],
            source_article_ids=ids("https://theedgemalaysia.com/node/815880"),
            confidence=0.88,
            event_type="TECHNOLOGY_LAUNCH",
        ),
        Event(
            id="evt_alibaba_placement",
            title="Alibaba plans US$10.2B share placement for AI development",
            summary="Alibaba is raising about US$10.2 billion via a share placement to fund AI models and cloud infrastructure, including Asia capacity.",
            event_date=NOW - timedelta(hours=18),
            countries=["China"],
            companies=["Alibaba"],
            industries=["AI", "Cloud", "Semiconductors", "Data centers"],
            entities=[_entity("Alibaba", "COMPANY", "China")],
            source_article_ids=ids(
                "https://theedgemalaysia.com/node/815507",
                "https://www.channelnewsasia.com/business/alibaba-cloud-southeast-asia-expansion-ai",
            ),
            confidence=0.94,
            event_type="FUNDING",
        ),
        Event(
            id="evt_alibaba_sea_cloud",
            title="Alibaba Cloud targets additional Southeast Asia AI capacity",
            summary="Alibaba Cloud is using new capital to expand AI-ready capacity for SEA customers, with Malaysia evaluated as overflow to Singapore.",
            event_date=NOW - timedelta(hours=14),
            countries=["Singapore", "Malaysia", "China"],
            companies=["Alibaba"],
            industries=["Cloud", "AI", "Data centers"],
            entities=[_entity("Alibaba Cloud", "COMPANY", "China")],
            source_article_ids=ids(
                "https://www.channelnewsasia.com/business/alibaba-cloud-southeast-asia-expansion-ai",
                "https://theedgemalaysia.com/node/815507",
            ),
            confidence=0.86,
            event_type="EXPANSION",
        ),
        Event(
            id="evt_msft_sea",
            title="Microsoft expands Southeast Asia cloud and AI infrastructure",
            summary="Microsoft is adding regional cloud capacity for Copilot and enterprise AI, mapping overflow into southern Malaysia.",
            event_date=NOW - timedelta(days=3),
            countries=["Singapore", "Malaysia"],
            companies=["Microsoft"],
            industries=["Cloud", "AI", "Data centers"],
            entities=[_entity("Microsoft", "COMPANY", "United States")],
            source_article_ids=ids(
                "https://www.channelnewsasia.com/business/microsoft-sea-data-centre-investment-ai"
            ),
            confidence=0.89,
            event_type="INVESTMENT",
        ),
        Event(
            id="evt_vn_electronics_fdi",
            title="Vietnam electronics and semiconductor FDI accelerates",
            summary="AI hardware demand is lifting FDI into Vietnam electronics parks, packaging and supporting industries.",
            event_date=NOW - timedelta(days=2),
            countries=["Vietnam"],
            companies=[],
            industries=["Electronics", "Semiconductors", "Manufacturing"],
            entities=[_entity("Vietnam", "COUNTRY", "Vietnam")],
            source_article_ids=ids(
                "https://vir.com.vn/electronics-fdi-vietnam-semiconductor-packaging-ai-159401.html"
            ),
            confidence=0.9,
            event_type="INVESTMENT",
        ),
        Event(
            id="evt_vn_ai_servers",
            title="Vietnam plants add AI server and networking production",
            summary="Contract manufacturers are installing Vietnam lines for AI servers and networking gear with exports through northern and southern ports.",
            event_date=NOW - timedelta(days=1, hours=6),
            countries=["Vietnam"],
            companies=[],
            industries=["Electronics", "Manufacturing", "Data centers"],
            entities=[_entity("Hai Phong", "CITY", "Vietnam")],
            source_article_ids=ids(
                "https://vir.com.vn/foxconn-suppliers-expand-vietnam-production-ai-servers-159266.html"
            ),
            confidence=0.87,
            event_type="PRODUCTION_CHANGE",
        ),
        Event(
            id="evt_gpu_tightness",
            title="GPU lead times delay Asia AI hall commissioning",
            summary="Accelerator shortages are staggering data-centre openings in Singapore and Johor even where power is available.",
            event_date=NOW - timedelta(days=2, hours=4),
            countries=["Singapore", "Malaysia"],
            companies=["NVIDIA"],
            industries=["Semiconductors", "Data centers", "AI"],
            entities=[_entity("NVIDIA", "COMPANY", "United States")],
            source_article_ids=ids(
                "https://www.channelnewsasia.com/business/gpu-supply-tightness-asia-data-centres"
            ),
            confidence=0.85,
            event_type="SUPPLY_DISRUPTION",
        ),
        Event(
            id="evt_my_grid",
            title="Malaysia utilities advance Johor grid upgrades for DC load",
            summary="Tenaga and state utilities are planning substations and high-voltage corridors so announced Johor AI campuses can connect.",
            event_date=NOW - timedelta(days=1),
            countries=["Malaysia"],
            companies=["Tenaga Nasional"],
            industries=["Energy", "Infrastructure", "Data centers"],
            entities=[_entity("Tenaga Nasional", "COMPANY", "Malaysia")],
            source_article_ids=ids("https://theedgemalaysia.com/node/815940"),
            confidence=0.88,
            event_type="CORPORATE_ACTION",
        ),
        Event(
            id="evt_sg_reit_reprice",
            title="Singapore data-centre landlords reprice remaining powered capacity",
            summary="REITs and landlords are lifting rents and lease tenors as onshore AI wholesale demand meets constrained supply.",
            event_date=NOW - timedelta(hours=20),
            countries=["Singapore"],
            companies=[],
            industries=["Real estate", "Data centers", "Markets"],
            entities=[_entity("Singapore", "COUNTRY", "Singapore")],
            source_article_ids=ids(
                "https://www.channelnewsasia.com/business/singapore-data-centre-reits-ai-demand"
            ),
            confidence=0.84,
            event_type="MARKET_MOVE",
        ),
        Event(
            id="evt_id_incentives",
            title="Indonesia weighs incentives for a Batam data-centre node",
            summary="Jakarta is considering power and fiscal incentives as investors study Batam as a third node beside Singapore and Johor.",
            event_date=NOW - timedelta(hours=10),
            countries=["Indonesia"],
            companies=[],
            industries=["Data centers", "Infrastructure", "Policy"],
            entities=[_entity("Batam", "CITY", "Indonesia")],
            source_article_ids=ids(
                "https://www.channelnewsasia.com/business/indonesia-data-centre-incentives-ai-corridor"
            ),
            confidence=0.78,
            event_type="CORPORATE_ACTION",
        ),
        Event(
            id="evt_cables",
            title="Cross-border fibre and subsea links scoped for SG-Johor-Batam",
            summary="Campus announcements are pulling forward fibre and subsea upgrades connecting Singapore, Johor and Batam compute nodes.",
            event_date=NOW - timedelta(days=4),
            countries=["Singapore", "Malaysia", "Indonesia"],
            companies=[],
            industries=["Telecom", "Infrastructure", "Data centers"],
            entities=[_entity("Batam", "CITY", "Indonesia")],
            source_article_ids=ids(
                "https://theedgemalaysia.com/node/815901",
                "https://www.channelnewsasia.com/business/indonesia-data-centre-incentives-ai-corridor",
            ),
            confidence=0.8,
            event_type="TECHNOLOGY_LAUNCH",
        ),
        Event(
            id="evt_vn_ai_parks",
            title="Hanoi and HCMC expand AI software parks and talent pipelines",
            summary="Vietnamese cities are pairing hardware FDI with AI software parks and cross-border engineering mobility.",
            event_date=NOW - timedelta(hours=30),
            countries=["Vietnam"],
            companies=[],
            industries=["AI", "Software", "Education"],
            entities=[
                _entity("Hanoi", "CITY", "Vietnam"),
                _entity("Ho Chi Minh City", "CITY", "Vietnam"),
            ],
            source_article_ids=ids(
                "https://vir.com.vn/vietnam-ai-software-parks-hanoi-hcmc-expansion-159410.html"
            ),
            confidence=0.82,
            event_type="EXPANSION",
        ),
        Event(
            id="evt_my_osat",
            title="Malaysia OSAT houses lift utilisation on AI hardware demand",
            summary="Packaging and test plants in Malaysia are seeing higher utilisation from AI networking chips and regional board builds.",
            event_date=NOW - timedelta(hours=22),
            countries=["Malaysia"],
            companies=[],
            industries=["Semiconductors", "Electronics"],
            entities=[_entity("Malaysia", "COUNTRY", "Malaysia")],
            source_article_ids=ids("https://theedgemalaysia.com/node/815970"),
            confidence=0.86,
            event_type="MARKET_MOVE",
        ),
        Event(
            id="evt_johor_power_price",
            title="Johor industrial power prices come under data-centre scrutiny",
            summary="Local industry is warning that concentrated AI load could pressure tariffs and water even as investment rises.",
            event_date=NOW - timedelta(hours=8),
            countries=["Malaysia"],
            companies=["Tenaga Nasional"],
            industries=["Energy", "Manufacturing", "Data centers"],
            entities=[_entity("Johor", "CITY", "Malaysia")],
            source_article_ids=ids(
                "https://theedgemalaysia.com/node/815990",
                "https://theedgemalaysia.com/node/815940",
            ),
            confidence=0.8,
            event_type="PRICE_CHANGE",
        ),
        Event(
            id="evt_sg_guidance",
            title="Singapore tightens AI infrastructure efficiency guidance",
            summary="IMDA and financial regulators raised efficiency and resilience expectations for onshore AI compute used by banks.",
            event_date=NOW - timedelta(days=3, hours=2),
            countries=["Singapore"],
            companies=[],
            industries=["Policy", "AI", "Financial services"],
            entities=[_entity("IMDA", "ORGANIZATION", "Singapore")],
            source_article_ids=ids(
                "https://www.channelnewsasia.com/business/imda-mas-ai-infrastructure-guidelines-singapore"
            ),
            confidence=0.9,
            event_type="CORPORATE_ACTION",
        ),
        Event(
            id="evt_bytedance_sea",
            title="Chinese consumer-internet platforms raise SEA cloud spend",
            summary="Regional brokers report additional wholesale inquiries from Chinese platforms, adding to hyperscaler pressure on SEA capacity.",
            event_date=NOW - timedelta(days=2),
            countries=["Singapore", "China"],
            companies=["ByteDance", "Alibaba"],
            industries=["Cloud", "Internet", "AI"],
            entities=[_entity("ByteDance", "COMPANY", "China")],
            source_article_ids=ids(
                "https://www.channelnewsasia.com/business/alibaba-cloud-southeast-asia-expansion-ai"
            ),
            confidence=0.7,
            event_type="INVESTMENT",
        ),
        Event(
            id="evt_id_corridor_future",
            title="Indonesia positioned as a later-phase AI compute corridor",
            summary="If Batam incentives and power contracts clear, Indonesia could absorb overflow inference and DR loads after Johor fills.",
            event_date=NOW + timedelta(days=120),
            countries=["Indonesia"],
            companies=[],
            industries=["Data centers", "Energy", "Cloud"],
            entities=[_entity("Indonesia", "COUNTRY", "Indonesia")],
            source_article_ids=ids(
                "https://www.channelnewsasia.com/business/indonesia-data-centre-incentives-ai-corridor"
            ),
            confidence=0.62,
            event_type="EXPANSION",
        ),
        Event(
            id="evt_th_boi",
            title="Thailand courts data-centre capital as regional AI load spreads",
            summary="Thailand's investment authorities are marketing power and land packages to data-centre developers watching the Singapore-Johor bottleneck.",
            event_date=NOW - timedelta(days=1, hours=12),
            countries=["Thailand"],
            companies=[],
            industries=["Data centers", "Policy", "Infrastructure"],
            entities=[_entity("Thailand", "COUNTRY", "Thailand")],
            source_article_ids=ids(
                "https://www.channelnewsasia.com/business/microsoft-sea-data-centre-investment-ai"
            ),
            confidence=0.64,
            event_type="INVESTMENT",
        ),
        Event(
            id="evt_talent_corridor",
            title="AI operations talent moves across Singapore, Malaysia and Vietnam",
            summary="Recruiters report rising cross-border movement of AI and data-centre operations engineers as campuses and software parks scale together.",
            event_date=NOW - timedelta(hours=28),
            countries=["Singapore", "Malaysia", "Vietnam"],
            companies=[],
            industries=["AI", "Labour", "Services"],
            entities=[_entity("ASEAN", "ORGANIZATION")],
            source_article_ids=ids(
                "https://vir.com.vn/vietnam-ai-software-parks-hanoi-hcmc-expansion-159410.html"
            ),
            confidence=0.73,
            event_type="PARTNERSHIP",
        ),
    ]


def _edge(
    source: str,
    target: str,
    relation: str,
    reason: str,
    articles: list[Article],
    events: dict[str, Event],
    *,
    confidence: float,
    status: str,
    supporting: list[str] | None = None,
) -> CausalEdge:
    article_map = {article.id: article for article in articles}
    supporting_ids = supporting or list(
        dict.fromkeys(events[source].source_article_ids + events[target].source_article_ids)
    )[:4]
    edge = CausalEdge(
        id=f"edg_{source}_{target}_{relation.lower()}",
        source_event_id=source,
        target_event_id=target,
        relation=relation,  # type: ignore[arg-type]
        confidence=confidence,
        reason=reason,
        supporting_article_ids=supporting_ids,
        status=status,  # type: ignore[arg-type]
    )
    edge = annotate_cross_border(edge, events)
    edge.evidence_score = calculate_evidence_score(edge, article_map)
    return edge


def seed_edges(events: list[Event], articles: list[Article]) -> list[CausalEdge]:
    ev = {event.id: event for event in events}
    specs: list[tuple] = [
        (
            "evt_hyperscaler_capex",
            "evt_alibaba_placement",
            "CAUSES",
            "Alibaba's placement is framed as a financing response to the same AI capex race lifting Microsoft and other platforms.",
            0.86,
            "observed",
        ),
        (
            "evt_hyperscaler_capex",
            "evt_msft_sea",
            "CONTRIBUTES_TO",
            "Microsoft's SEA cloud build is described as part of the broader hyperscaler AI infrastructure cycle.",
            0.84,
            "observed",
        ),
        (
            "evt_sg_power_land",
            "evt_johor_sez_dc",
            "CAUSES",
            "Johor campus demand is explicitly tied to Singapore's inability to allocate additional AI megawatts and land.",
            0.92,
            "observed",
        ),
        (
            "evt_alibaba_placement",
            "evt_alibaba_sea_cloud",
            "TRIGGERS",
            "Executives said proceeds from the share placement would fund additional Asia-Pacific, including Southeast Asia, AI cloud capacity.",
            0.9,
            "observed",
        ),
        (
            "evt_alibaba_sea_cloud",
            "evt_johor_sez_dc",
            "AFFECTS",
            "Alibaba Cloud overflow evaluations add incremental wholesale demand into the Johor-Singapore cluster.",
            0.77,
            "inferred",
        ),
        (
            "evt_johor_sez_dc",
            "evt_ytl_nvidia",
            "CONTRIBUTES_TO",
            "The SEZ data-centre surge and the YTL-NVIDIA campus compete in the same Johor power-and-land market and are advancing together.",
            0.74,
            "inferred",
        ),
        (
            "evt_johor_sez_dc",
            "evt_my_grid",
            "TRIGGERS",
            "Utility upgrade plans are presented as necessary for announced Johor AI campuses to connect on schedule.",
            0.88,
            "observed",
        ),
        (
            "evt_my_grid",
            "evt_johor_power_price",
            "CONTRIBUTES_TO",
            "Grid reinforcement and concentrated new load are the stated reasons industrial users are watching Johor power prices.",
            0.8,
            "observed",
        ),
        (
            "evt_johor_sez_dc",
            "evt_sg_reit_reprice",
            "AFFECTS",
            "Brokers linked firmer Singapore data-centre rents to hyperscale announcements across the Causeway tightening remaining onshore shells.",
            0.78,
            "observed",
        ),
        (
            "evt_gpu_tightness",
            "evt_johor_sez_dc",
            "AFFECTS",
            "Chip lead times are delaying hall openings in Johor even after sites are selected.",
            0.81,
            "observed",
        ),
        (
            "evt_gpu_tightness",
            "evt_alibaba_sea_cloud",
            "AFFECTS",
            "Accelerator shortages constrain how quickly Alibaba and peers can turn fundraising into commissioned SEA capacity.",
            0.76,
            "inferred",
        ),
        (
            "evt_hyperscaler_capex",
            "evt_vn_electronics_fdi",
            "CONTRIBUTES_TO",
            "Vietnam electronics FDI is rising as AI hardware demand and China-plus-one board builds lengthen manufacturer order books.",
            0.83,
            "observed",
        ),
        (
            "evt_vn_electronics_fdi",
            "evt_vn_ai_servers",
            "CAUSES",
            "Provincial boards tie new AI server lines to the same FDI wave into electronics parks.",
            0.87,
            "observed",
        ),
        (
            "evt_vn_ai_servers",
            "evt_my_osat",
            "AFFECTS",
            "High-value modules still finishing in Malaysia link Vietnam board builds to Malaysian packaging utilisation.",
            0.79,
            "observed",
        ),
        (
            "evt_my_osat",
            "evt_sg_reit_reprice",
            "CONTRIBUTES_TO",
            "AI hardware chain tightness supports the same regional compute build-out that is repricing Singapore digital real estate.",
            0.6,
            "inferred",
        ),
        (
            "evt_johor_sez_dc",
            "evt_cables",
            "TRIGGERS",
            "Campus clustering is pulling forward fibre and subsea extensions between Singapore and Johor.",
            0.82,
            "observed",
        ),
        (
            "evt_cables",
            "evt_id_incentives",
            "AFFECTS",
            "Existing SG-Johor-Batam connectivity is cited as the reason Indonesia can be added as a third compute node.",
            0.75,
            "inferred",
        ),
        (
            "evt_alibaba_sea_cloud",
            "evt_bytedance_sea",
            "CONTRIBUTES_TO",
            "Chinese platform cloud inquiries are rising in the same Singapore-Malaysia capacity conversation as Alibaba's expansion.",
            0.66,
            "inferred",
        ),
        (
            "evt_sg_power_land",
            "evt_sg_guidance",
            "TRIGGERS",
            "Updated IMDA and MAS guidance is described as a response to onshore power constraints and rapid model-hosting growth.",
            0.85,
            "observed",
        ),
        (
            "evt_vn_electronics_fdi",
            "evt_vn_ai_parks",
            "CONTRIBUTES_TO",
            "Software-park expansions are being paired with the hardware FDI boom to capture higher-value AI work.",
            0.8,
            "observed",
        ),
        (
            "evt_vn_ai_parks",
            "evt_talent_corridor",
            "AFFECTS",
            "Talent programmes and park expansions are increasing engineer mobility across Vietnam, Singapore and Malaysia.",
            0.72,
            "observed",
        ),
        (
            "evt_ytl_nvidia",
            "evt_my_osat",
            "AFFECTS",
            "A domestic AI supercomputing cluster adds local demand for advanced networking and power semiconductors packaged in Malaysia.",
            0.68,
            "inferred",
        ),
        (
            "evt_hyperscaler_capex",
            "evt_th_boi",
            "CONTRIBUTES_TO",
            "Thailand is marketing DC packages because the regional AI load is spilling beyond Singapore and Johor.",
            0.63,
            "inferred",
        ),
        (
            "evt_johor_sez_dc",
            "evt_id_incentives",
            "AFFECTS",
            "Visible Johor fill-up is the political and commercial prompt for Indonesia to consider matching incentives.",
            0.7,
            "inferred",
        ),
        (
            "evt_id_incentives",
            "evt_id_corridor_future",
            "AFFECTS",
            "If incentives and power contracts clear, Batam is a plausible later-phase inference and disaster-recovery node.",
            0.58,
            "predicted",
        ),
        (
            "evt_th_boi",
            "evt_id_corridor_future",
            "AFFECTS",
            "A wider mainland Southeast Asia incentive race could divert some later-phase load, including toward Indonesia.",
            0.5,
            "predicted",
        ),
        (
            "evt_msft_sea",
            "evt_johor_sez_dc",
            "CONTRIBUTES_TO",
            "Microsoft overflow mapping into southern Malaysia is one of the demand sources filling the Johor cluster.",
            0.8,
            "observed",
        ),
        (
            "evt_msft_sea",
            "evt_sg_reit_reprice",
            "CONTRIBUTES_TO",
            "Hyperscaler onshore demand from Microsoft and peers is tightening remaining Singapore powered shells.",
            0.77,
            "observed",
        ),
        (
            "evt_johor_power_price",
            "evt_my_grid",
            "RESPONDS_TO",
            "Tariff debate is feeding back into how utilities sequence upgrades and cost recovery for DC connections.",
            0.69,
            "inferred",
        ),
        (
            "evt_vn_ai_servers",
            "evt_talent_corridor",
            "CONTRIBUTES_TO",
            "New AI server plants increase the need for regional operations talent already moving across ASEAN hubs.",
            0.67,
            "inferred",
        ),
        (
            "evt_cables",
            "evt_alibaba_sea_cloud",
            "AFFECTS",
            "Better Johor-Singapore interconnection makes overflow cloud capacity more viable for Alibaba and other platforms.",
            0.71,
            "inferred",
        ),
    ]
    return [
        _edge(source, target, relation, reason, articles, ev, confidence=confidence, status=status)
        for source, target, relation, reason, confidence, status in specs
    ]


DEMO_QUERIES = [
    "AI infrastructure in Southeast Asia",
    "Vietnam manufacturing investment",
    "Johor-Singapore investment corridor",
    "Semiconductor supply chain Southeast Asia",
    "Indonesia EV battery ecosystem",
]


def events_for_query(query: str, events: list[Event]) -> list[Event]:
    q = query.lower()
    if "vietnam" in q and "manufactur" in q:
        keep = {
            "evt_hyperscaler_capex",
            "evt_vn_electronics_fdi",
            "evt_vn_ai_servers",
            "evt_vn_ai_parks",
            "evt_my_osat",
            "evt_talent_corridor",
            "evt_gpu_tightness",
        }
    elif "johor" in q or "corridor" in q:
        keep = {
            "evt_sg_power_land",
            "evt_johor_sez_dc",
            "evt_ytl_nvidia",
            "evt_msft_sea",
            "evt_my_grid",
            "evt_johor_power_price",
            "evt_sg_reit_reprice",
            "evt_cables",
            "evt_id_incentives",
            "evt_sg_guidance",
        }
    elif "semiconductor" in q:
        keep = {
            "evt_hyperscaler_capex",
            "evt_gpu_tightness",
            "evt_vn_electronics_fdi",
            "evt_vn_ai_servers",
            "evt_my_osat",
            "evt_ytl_nvidia",
            "evt_talent_corridor",
        }
    elif "indonesia" in q and ("ev" in q or "battery" in q or "nickel" in q):
        keep = {
            "evt_id_incentives",
            "evt_cables",
            "evt_johor_sez_dc",
            "evt_id_corridor_future",
            "evt_vn_electronics_fdi",
            "evt_hyperscaler_capex",
        }
    else:
        return events
    return [event for event in events if event.id in keep]


def edges_for_events(edges: list[CausalEdge], events: list[Event]) -> list[CausalEdge]:
    ids = {event.id for event in events}
    return [edge for edge in edges if edge.source_event_id in ids and edge.target_event_id in ids]
