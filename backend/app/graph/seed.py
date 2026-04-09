from app.graph.company_queries import seed_companies

SEED_COMPANIES = [
    {"name": "Google", "industry": "Tech"},
    {"name": "Meta", "industry": "Tech"},
    {"name": "Amazon", "industry": "Tech"},
    {"name": "Apple", "industry": "Tech"},
    {"name": "Microsoft", "industry": "Tech"},
    {"name": "Netflix", "industry": "Tech"},
    {"name": "Stripe", "industry": "Fintech"},
    {"name": "Airbnb", "industry": "Travel Tech"},
    {"name": "Uber", "industry": "Mobility Tech"},
    {"name": "Spotify", "industry": "Media Tech"},
]


async def run_seed():
    await seed_companies(SEED_COMPANIES)
