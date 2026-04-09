from app.graph.company_queries import seed_companies
from app.graph.manager_queries import seed_managers
from app.graph.round_queries import seed_rounds

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

SEED_MANAGERS = [
    {
        "name": "Sundar Pichai", "title": "CEO", "company": "Google",
        "traits": ["analytical", "systematic", "collaborative", "data-driven"],
    },
    {
        "name": "Jeff Dean", "title": "Chief Scientist", "company": "Google",
        "traits": ["technical-depth", "scalability-focused", "low-level-systems"],
    },
    {
        "name": "Mark Zuckerberg", "title": "CEO", "company": "Meta",
        "traits": ["move-fast", "bold-bets", "product-obsessed", "metrics-driven"],
    },
    {
        "name": "Andrew Bosworth", "title": "CTO", "company": "Meta",
        "traits": ["direct", "challenging", "engineering-excellence"],
    },
    {
        "name": "Andy Jassy", "title": "CEO", "company": "Amazon",
        "traits": ["customer-obsessed", "high-standards", "ownership", "frugal"],
    },
    {
        "name": "Werner Vogels", "title": "CTO", "company": "Amazon",
        "traits": ["distributed-systems", "reliability", "operational-excellence"],
    },
    {
        "name": "Tim Cook", "title": "CEO", "company": "Apple",
        "traits": ["operational-excellence", "quality-obsessed", "privacy-first"],
    },
    {
        "name": "Satya Nadella", "title": "CEO", "company": "Microsoft",
        "traits": ["growth-mindset", "empathy", "cloud-first", "inclusive"],
    },
    {
        "name": "Reed Hastings", "title": "Co-founder", "company": "Netflix",
        "traits": ["talent-density", "radical-transparency", "freedom-and-responsibility"],
    },
    {
        "name": "Patrick Collison", "title": "CEO", "company": "Stripe",
        "traits": ["intellectual-rigorous", "writing-culture", "high-craft"],
    },
    {
        "name": "Brian Chesky", "title": "CEO", "company": "Airbnb",
        "traits": ["design-thinking", "community-focused", "storytelling"],
    },
    {
        "name": "Dara Khosrowshahi", "title": "CEO", "company": "Uber",
        "traits": ["customer-first", "transparency", "bold-moves"],
    },
    {
        "name": "Daniel Ek", "title": "CEO", "company": "Spotify",
        "traits": ["creator-empathy", "long-term-thinking", "culture-driven"],
    },
]

SEED_ROUNDS = [
    # Google
    {
        "company": "Google", "type": "behavioral",
        "questions": [
            {"text": "Tell me about a time you had to make a decision with incomplete data.", "difficulty": "medium"},
            {"text": "Describe a project where you had to collaborate across teams.", "difficulty": "medium"},
            {"text": "Give an example of when you disagreed with a teammate. How did you resolve it?", "difficulty": "medium"},
        ],
    },
    {
        "company": "Google", "type": "technical",
        "questions": [
            {"text": "Design a URL shortener that handles 100M requests per day.", "difficulty": "hard"},
            {"text": "Implement LRU Cache with O(1) get and put.", "difficulty": "medium"},
            {"text": "Given an array of integers, find all pairs that sum to a target.", "difficulty": "easy"},
        ],
    },
    {
        "company": "Google", "type": "system_design",
        "questions": [
            {"text": "Design Google Search — focus on indexing and query serving.", "difficulty": "hard"},
            {"text": "Design a distributed rate limiter used across Google services.", "difficulty": "hard"},
        ],
    },
    # Meta
    {
        "company": "Meta", "type": "behavioral",
        "questions": [
            {"text": "Tell me about a time you had to move fast and break things.", "difficulty": "medium"},
            {"text": "Describe your biggest impact in a past role.", "difficulty": "medium"},
            {"text": "How do you handle ambiguity in product requirements?", "difficulty": "medium"},
        ],
    },
    {
        "company": "Meta", "type": "technical",
        "questions": [
            {"text": "Given a binary tree, find the lowest common ancestor of two nodes.", "difficulty": "medium"},
            {"text": "Design a news feed ranking system.", "difficulty": "hard"},
            {"text": "Implement a function to serialize and deserialize a binary tree.", "difficulty": "medium"},
        ],
    },
    # Amazon
    {
        "company": "Amazon", "type": "behavioral",
        "questions": [
            {"text": "Tell me about a time you had to deliver a project under a tight deadline.", "difficulty": "medium"},
            {"text": "Describe a situation where you went above and beyond for a customer.", "difficulty": "medium"},
            {"text": "Give an example of a calculated risk you took at work.", "difficulty": "medium"},
            {"text": "Tell me about a time you failed. What did you learn?", "difficulty": "medium"},
        ],
    },
    {
        "company": "Amazon", "type": "technical",
        "questions": [
            {"text": "Design Amazon's product recommendation engine.", "difficulty": "hard"},
            {"text": "Implement a stack that supports getMin() in O(1).", "difficulty": "medium"},
        ],
    },
    # Microsoft
    {
        "company": "Microsoft", "type": "behavioral",
        "questions": [
            {"text": "Tell me about a time you had to learn something quickly.", "difficulty": "medium"},
            {"text": "How have you fostered a growth mindset in your team?", "difficulty": "medium"},
        ],
    },
    {
        "company": "Microsoft", "type": "technical",
        "questions": [
            {"text": "Design a version control system like Git.", "difficulty": "hard"},
            {"text": "Find the median of a stream of integers.", "difficulty": "hard"},
        ],
    },
    # Netflix
    {
        "company": "Netflix", "type": "behavioral",
        "questions": [
            {"text": "Describe a time you had to give difficult feedback.", "difficulty": "medium"},
            {"text": "How have you handled a situation with a high-performing but disruptive team member?", "difficulty": "hard"},
        ],
    },
    {
        "company": "Netflix", "type": "system_design",
        "questions": [
            {"text": "Design Netflix's video streaming infrastructure.", "difficulty": "hard"},
            {"text": "Design a global CDN for content delivery.", "difficulty": "hard"},
        ],
    },
    # Stripe
    {
        "company": "Stripe", "type": "behavioral",
        "questions": [
            {"text": "Describe a piece of technical writing you're proud of.", "difficulty": "medium"},
            {"text": "Tell me about a time you had to deeply understand a complex system before improving it.", "difficulty": "hard"},
        ],
    },
    {
        "company": "Stripe", "type": "technical",
        "questions": [
            {"text": "Design Stripe's payment processing pipeline for high availability.", "difficulty": "hard"},
            {"text": "How would you handle idempotency in a payment API?", "difficulty": "hard"},
        ],
    },
    # Airbnb
    {
        "company": "Airbnb", "type": "behavioral",
        "questions": [
            {"text": "Tell me about a time you championed the user experience over technical convenience.", "difficulty": "medium"},
            {"text": "Describe a product decision you made that required balancing community needs.", "difficulty": "medium"},
        ],
    },
    # Uber
    {
        "company": "Uber", "type": "system_design",
        "questions": [
            {"text": "Design Uber's real-time driver matching system.", "difficulty": "hard"},
            {"text": "Design a surge pricing system that scales globally.", "difficulty": "hard"},
        ],
    },
    # Spotify
    {
        "company": "Spotify", "type": "behavioral",
        "questions": [
            {"text": "Tell me about a time you advocated for creators or end users.", "difficulty": "medium"},
            {"text": "Describe how you balance long-term vision with short-term delivery.", "difficulty": "medium"},
        ],
    },
    # Apple (behavioral)
    {
        "company": "Apple", "type": "behavioral",
        "questions": [
            {"text": "Tell me about a time you refused to compromise on quality.", "difficulty": "medium"},
            {"text": "Describe how you handle feedback that challenges your design decisions.", "difficulty": "medium"},
        ],
    },
]


async def run_seed():
    await seed_companies(SEED_COMPANIES)
    await seed_managers(SEED_MANAGERS)
    await seed_rounds(SEED_ROUNDS)
