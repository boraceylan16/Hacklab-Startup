"""
RSS Feed Configuration
"""

RSS_FEEDS = [
    # ── Technology ───────────────────────────────────────────────────────────
    {"url": "https://feeds.feedburner.com/TechCrunch", "source": "TechCrunch",      "category": "technology"},
    {"url": "https://www.wired.com/feed/rss",          "source": "Wired",           "category": "technology"},
    {"url": "https://hnrss.org/frontpage",             "source": "HackerNews",      "category": "technology"},
    {"url": "https://www.theverge.com/rss/index.xml",  "source": "The Verge",       "category": "technology"},

    # ── AI / ML ──────────────────────────────────────────────────────────────
    {"url": "https://openai.com/blog/rss.xml",                            "source": "OpenAI Blog",     "category": "ai"},
    {"url": "https://bair.berkeley.edu/blog/feed.xml",                    "source": "BAIR Blog",       "category": "ai"},
    {"url": "https://newsletter.ruder.io/feed",                           "source": "NLP Newsletter",  "category": "ai"},

    # ── Business / Finance ───────────────────────────────────────────────────
    {"url": "https://feeds.bloomberg.com/markets/news.rss",               "source": "Bloomberg",       "category": "finance"},
    {"url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",             "source": "WSJ Markets",     "category": "finance"},
    {"url": "https://www.ft.com/?format=rss",                            "source": "FT",              "category": "finance"},

    # ── Science ──────────────────────────────────────────────────────────────
    {"url": "https://www.nature.com/nature.rss",       "source": "Nature",          "category": "science"},
    {"url": "https://rss.sciencemag.org/rss/current.xml","source": "Science Mag",   "category": "science"},

    # ── World News ───────────────────────────────────────────────────────────
    {"url": "https://feeds.bbci.co.uk/news/world/rss.xml","source": "BBC World",    "category": "world"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml","source":"NYT","category":"world"},
]

REQUEST_TIMEOUT   = 15
MAX_ARTICLES_FEED = 20
USER_AGENT        = "Mozilla/5.0 (compatible; NewsIntelBot/1.0)"
OUTPUT_DIR        = "output"
