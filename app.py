from flask import Flask, request, jsonify, send_from_directory
import random

app = Flask(__name__, static_folder='.')

# ================================================================
#  QUESTION BANK
#  Each question carries:
#  - keywords: terms a strong answer should use
#  - concepts: higher level ideas that should appear
#  - common_mistakes: things weak answers typically do (optional)
#  - ideal_length: rough word count of a strong answer
# ================================================================
QUESTIONS = {
    "Software Engineer": [
        {
            "q": "Explain the difference between a stack and a queue. When would you use each?",
            "keywords": ["lifo", "fifo", "push", "pop", "enqueue", "dequeue"],
            "concepts": ["last in first out", "first in first out", "undo", "history", "print queue", "bfs", "dfs", "recursion"],
            "common_mistakes": ["only defining one", "no real example", "confusing the order"],
            "ideal_length": 80
        },
        {
            "q": "What is Big O notation? Walk me through O(n), O(log n), and O(n²) with examples.",
            "keywords": ["time complexity", "space complexity", "algorithm", "loop", "binary search", "nested"],
            "concepts": ["worst case", "linear", "logarithmic", "quadratic", "scales", "performance"],
            "common_mistakes": ["no examples", "only defining without explaining", "missing the practical implication"],
            "ideal_length": 100
        },
        {
            "q": "Walk me through how you would design a URL shortener like bit.ly.",
            "keywords": ["hash", "database", "redirect", "collision", "base62", "cache"],
            "concepts": ["unique id", "mapping", "lookup", "short code", "long url", "302 redirect", "scale"],
            "common_mistakes": ["skipping the database design", "no collision handling", "no scale discussion"],
            "ideal_length": 120
        },
        {
            "q": "What is the difference between SQL and NoSQL? When would you choose one over the other?",
            "keywords": ["relational", "schema", "acid", "scalability", "document", "joins", "table"],
            "concepts": ["structured data", "flexible schema", "consistency", "horizontal scaling", "use case"],
            "common_mistakes": ["saying one is always better", "no concrete examples", "ignoring trade-offs"],
            "ideal_length": 100
        },
        {
            "q": "Explain what recursion is. What are its risks and how do you mitigate them?",
            "keywords": ["base case", "call stack", "overflow", "memoization", "fibonacci"],
            "concepts": ["function calls itself", "termination condition", "infinite loop risk", "memory", "dynamic programming"],
            "common_mistakes": ["no base case mention", "no stack overflow risk", "no mitigation strategy"],
            "ideal_length": 90
        },
        {
            "q": "How does a hash table work? What happens during a collision?",
            "keywords": ["hash function", "bucket", "chaining", "open addressing", "load factor"],
            "concepts": ["key to index", "array", "constant time", "worst case", "linked list", "probing"],
            "common_mistakes": ["skipping collision handling", "no complexity analysis", "vague on implementation"],
            "ideal_length": 90
        },
        {
            "q": "What is REST and how does it differ from GraphQL?",
            "keywords": ["endpoint", "http", "over-fetching", "under-fetching", "schema", "query", "mutation"],
            "concepts": ["multiple endpoints", "single endpoint", "flexible queries", "typed", "bandwidth", "versioning"],
            "common_mistakes": ["only defining REST", "no trade-off comparison", "no concrete example"],
            "ideal_length": 100
        },
        {
            "q": "What is the difference between a process and a thread?",
            "keywords": ["memory", "concurrency", "shared", "isolation", "context switch", "os"],
            "concepts": ["separate memory space", "lightweight", "communication", "crash isolation", "gil"],
            "common_mistakes": ["no memory distinction", "no use case", "no trade-off"],
            "ideal_length": 90
        },
        {"q": "Explain polymorphism and how it's different from inheritance.", "keywords": ["method overriding", "interface", "dynamic dispatch", "subtype"], "concepts": ["behavior variation", "code reuse", "abstraction"], "ideal_length": 90},
        {"q": "What is a design pattern? Name 3 and explain when to use each.", "keywords": ["singleton", "factory", "observer", "template", "strategy"], "concepts": ["reusable solution", "structure", "communication"], "ideal_length": 100},
        {"q": "Describe the difference between imperative and declarative programming.", "keywords": ["how vs what", "state mutations", "functional", "sql"], "concepts": ["programming paradigm", "abstraction level"], "ideal_length": 80},
        {"q": "What is a distributed system? What are the main challenges?", "keywords": ["network partition", "consistency", "fault tolerance", "consensus"], "concepts": ["scalability", "cap theorem", "eventual consistency"], "ideal_length": 110},
        {"q": "Explain ACID properties in databases.", "keywords": ["atomicity", "consistency", "isolation", "durability", "transaction"], "concepts": ["data integrity", "reliability"], "ideal_length": 90},
        {"q": "What is caching? What are cache invalidation strategies?", "keywords": ["ttl", "lru", "write-through", "write-back", "memory"], "concepts": ["performance", "data freshness"], "ideal_length": 95},
        {"q": "How would you debug a memory leak in production?", "keywords": ["heap dump", "profiler", "garbage collector", "reference"], "concepts": ["performance degradation", "root cause"], "ideal_length": 100},
        {"q": "Explain the difference between composition and inheritance.", "keywords": ["has-a", "is-a", "flexibility", "coupling"], "concepts": ["oop design", "code organization"], "ideal_length": 85},
        {"q": "What is containerization and how does Docker work?", "keywords": ["image", "container", "namespace", "layer", "registry"], "concepts": ["deployment", "isolation", "reproducibility"], "ideal_length": 100},
        {"q": "Describe a microservices architecture. What are its benefits and drawbacks?", "keywords": ["service", "scalability", "complexity", "communication", "distributed"], "concepts": ["architecture", "trade-offs"], "ideal_length": 120},
        {"q": "What is CI/CD and why is it important?", "keywords": ["pipeline", "testing", "deployment", "automation", "feedback"], "concepts": ["development velocity", "quality"], "ideal_length": 90},
        {"q": "Explain the difference between stateless and stateful services.", "keywords": ["session", "scaling", "horizontal", "session store"], "concepts": ["architecture", "reliability"], "ideal_length": 85},
        {"q": "What is sharding in databases? When would you use it?", "keywords": ["partition", "key", "horizontal scaling", "distributed"], "concepts": ["scalability", "data distribution"], "ideal_length": 95},
        {"q": "Describe the Observer pattern and where it's used.", "keywords": ["event", "listener", "publish-subscribe", "coupling"], "concepts": ["design pattern", "decoupling"], "ideal_length": 85},
        {"q": "What is the difference between OAuth and JWT?", "keywords": ["authentication", "authorization", "token", "stateless", "delegation"], "concepts": ["security", "identity"], "ideal_length": 95},
        {"q": "Explain what a CDN is and why companies use it.", "keywords": ["edge", "cache", "latency", "bandwidth", "distribution"], "concepts": ["performance", "global scale"], "ideal_length": 85},
        {"q": "What is load balancing? Describe different strategies.", "keywords": ["round-robin", "weighted", "least connections", "sticky"], "concepts": ["scalability", "reliability"], "ideal_length": 100},
        {"q": "Describe the MVC architecture pattern.", "keywords": ["model", "view", "controller", "separation", "concern"], "concepts": ["organization", "testability"], "ideal_length": 85},
        {"q": "What is an API and what makes a good REST API?", "keywords": ["endpoint", "resource", "status code", "versioning", "documentation"], "concepts": ["interface", "usability"], "ideal_length": 100},
        {"q": "Explain what a message queue is and when to use it.", "keywords": ["async", "producer", "consumer", "decoupling", "reliability"], "concepts": ["architecture", "scalability"], "ideal_length": 95},
    ],

    "Consultant": [
        {
            "q": "A client's revenue dropped 20 percent last quarter. How do you diagnose the problem?",
            "keywords": ["revenue", "volume", "price", "market", "competition", "internal", "external", "segment"],
            "concepts": ["structure the problem", "price times volume", "internal vs external", "hypothesis", "data"],
            "common_mistakes": ["jumping to solutions", "no framework", "only one cause explored"],
            "ideal_length": 120
        },
        {
            "q": "How would you estimate the number of petrol stations in the UAE?",
            "keywords": ["population", "cars", "frequency", "capacity", "assumption"],
            "concepts": ["top down", "bottom up", "sanity check", "decompose", "per day", "litres"],
            "common_mistakes": ["no clear assumptions", "no structure", "no sanity check at end"],
            "ideal_length": 100
        },
        {
            "q": "A retail bank wants to enter the UAE wealth management market. Should they?",
            "keywords": ["market size", "competition", "capabilities", "regulation", "risk", "synergies"],
            "concepts": ["market attractiveness", "competitive advantage", "fit", "recommendation", "pros cons"],
            "common_mistakes": ["no clear recommendation", "ignoring competition", "no capability assessment"],
            "ideal_length": 120
        },
        {
            "q": "How would you prioritize a backlog of 50 features for a product team?",
            "keywords": ["impact", "effort", "roi", "stakeholder", "moscow", "ice", "rice"],
            "concepts": ["framework", "value", "cost", "dependency", "align", "quick wins"],
            "common_mistakes": ["no framework mentioned", "ignoring stakeholders", "no effort assessment"],
            "ideal_length": 100
        },
        {
            "q": "A manufacturing company's costs increased 15% year-over-year. Where do you look?",
            "keywords": ["cogs", "fixed", "variable", "supplier", "labour", "volume", "efficiency"],
            "concepts": ["break down cost", "benchmark", "internal vs external", "root cause", "unit cost"],
            "common_mistakes": ["no cost breakdown", "jumping to one cause", "no benchmarking mentioned"],
            "ideal_length": 100
        },
        {
            "q": "Walk me through a go-to-market strategy for a new SaaS product.",
            "keywords": ["icp", "channel", "pricing", "positioning", "cac", "ltv", "pilot"],
            "concepts": ["target customer", "value proposition", "sales motion", "metrics", "iteration"],
            "common_mistakes": ["skipping the customer definition", "no pricing model", "no success metrics"],
            "ideal_length": 120
        },
        {"q": "A company's market share declined from 30% to 22 percent in 2 years. What's your analysis?", "keywords": ["competition", "pricing", "product", "market", "customer satisfaction"], "concepts": ["market analysis", "strategy"], "ideal_length": 120},
        {"q": "How would you enter a new geographic market?", "keywords": ["research", "adaptation", "localization", "partners", "risks"], "concepts": ["expansion strategy", "entry mode"], "ideal_length": 110},
        {"q": "A SaaS company is considering a price increase. How would you decide?", "keywords": ["elasticity", "churn", "arr", "customer", "value"], "concepts": ["pricing strategy", "financial impact"], "ideal_length": 100},
        {"q": "What is operational excellence and how do you measure it?", "keywords": ["efficiency", "cost", "quality", "cycle time", "waste"], "concepts": ["operations", "kpi"], "ideal_length": 100},
        {"q": "How would you turn around a declining business unit?", "keywords": ["diagnosis", "action plan", "stakeholder", "timeline", "metrics"], "concepts": ["turnaround strategy", "change management"], "ideal_length": 120},
        {"q": "A retail company wants to move to e-commerce. What's your approach?", "keywords": ["digital", "channel", "operations", "customer", "investment"], "concepts": ["transformation", "business model"], "ideal_length": 115},
        {"q": "Estimate the TAM (Total Addressable Market) for an AI chatbot startup.", "keywords": ["market size", "segments", "bottom-up", "top-down", "assumptions"], "concepts": ["market analysis", "sizing"], "ideal_length": 100},
        {"q": "How would you improve customer retention for a telecom company?", "keywords": ["churn", "loyalty", "engagement", "value", "service"], "concepts": ["retention strategy", "customer lifetime value"], "ideal_length": 100},
        {"q": "A manufacturing company wants to automate its factory. How do you approach it?", "keywords": ["roi", "capital", "labor", "risk", "timeline"], "concepts": ["investment decision", "change management"], "ideal_length": 110},
        {"q": "What does a good business strategy look like?", "keywords": ["vision", "goals", "competitive advantage", "execution", "measurement"], "concepts": ["strategy framework"], "ideal_length": 100},
        {"q": "How would you analyze competitor pricing?", "keywords": ["value", "positioning", "market", "segment", "elasticity"], "concepts": ["competitive analysis", "pricing strategy"], "ideal_length": 95},
        {"q": "Describe how you'd measure the success of a digital transformation.", "keywords": ["kpi", "adoption", "efficiency", "revenue", "timeline"], "concepts": ["metrics", "outcomes"], "ideal_length": 100},
        {"q": "A company has high employee turnover. What's your diagnostic?", "keywords": ["engagement", "compensation", "culture", "growth", "management"], "concepts": ["hr strategy", "root cause"], "ideal_length": 100},
        {"q": "How would you develop a go-to-market strategy for a B2B product?", "keywords": ["icp", "channel", "sales", "marketing", "pricing"], "concepts": ["gtm strategy", "execution"], "ideal_length": 110},
        {"q": "What is blue ocean strategy? Give an example.", "keywords": ["uncontested market", "value innovation", "differentiation", "cost"], "concepts": ["strategy framework", "competition"], "ideal_length": 95},
    ],

    "Data Analyst": [
        {
            "q": "What is the difference between INNER JOIN, LEFT JOIN, and FULL OUTER JOIN?",
            "keywords": ["matching rows", "null", "all rows", "intersection", "foreign key", "table"],
            "concepts": ["only matched", "keep left", "keep all", "missing values", "when to use each"],
            "common_mistakes": ["only defining one type", "no use case", "no null handling mention"],
            "ideal_length": 90
        },
        {
            "q": "You run an A/B test. p < 0.05 but the effect size is tiny. Do you ship?",
            "keywords": ["statistical significance", "practical significance", "effect size", "sample size", "cost"],
            "concepts": ["business impact", "confidence", "cost to ship", "context matters", "lift"],
            "common_mistakes": ["just saying yes because p < 0.05", "ignoring business context", "no nuance"],
            "ideal_length": 90
        },
        {
            "q": "Explain the difference between correlation and causation with an example.",
            "keywords": ["confounding", "experiment", "rct", "observational", "spurious"],
            "concepts": ["does not imply", "third variable", "randomized", "controlled", "real example"],
            "common_mistakes": ["no example", "no confounding mention", "no path to causation"],
            "ideal_length": 90
        },
        {
            "q": "How would you detect and handle outliers in a dataset?",
            "keywords": ["iqr", "z-score", "boxplot", "domain knowledge", "cap", "remove"],
            "concepts": ["detection method", "investigate why", "business context", "impact on model"],
            "common_mistakes": ["only removing outliers", "no detection method", "ignoring domain context"],
            "ideal_length": 90
        },
        {
            "q": "You have 30% missing values in a key column. What do you do?",
            "keywords": ["mcar", "mar", "mnar", "imputation", "drop", "flag", "mean", "median"],
            "concepts": ["why missing", "mechanism", "strategy", "risk", "model impact"],
            "common_mistakes": ["just dropping rows", "no mechanism analysis", "no risk discussion"],
            "ideal_length": 100
        },
        {
            "q": "Walk me through how you would build a dashboard for a sales team.",
            "keywords": ["kpi", "audience", "granularity", "refresh", "filter", "tool", "stakeholder"],
            "concepts": ["understand user", "choose metrics", "data source", "design", "iterate"],
            "common_mistakes": ["jumping to tools", "no stakeholder mention", "no iteration"],
            "ideal_length": 100
        },
        {
            "q": "Explain what a p-value is in plain English. What are common misconceptions?",
            "keywords": ["null hypothesis", "probability", "threshold", "false positive"],
            "concepts": ["not probability of hypothesis", "not proof", "threshold arbitrary", "type 1 error"],
            "common_mistakes": ["saying it proves the hypothesis", "no misconception", "too technical"],
            "ideal_length": 90
        },
    ],

    "UI Designer": [
        {
            "q": "Walk me through your end-to-end design process for a new feature.",
            "keywords": ["research", "wireframe", "prototype", "iterate", "handoff", "test", "feedback"],
            "concepts": ["discovery", "ideation", "low fidelity", "high fidelity", "user testing", "dev"],
            "common_mistakes": ["skipping research", "no testing step", "no handoff mention"],
            "ideal_length": 120
        },
        {
            "q": "How do you design for accessibility? Give three concrete examples.",
            "keywords": ["wcag", "contrast", "alt text", "keyboard", "screen reader", "focus"],
            "concepts": ["colour contrast ratio", "tab navigation", "semantic html", "aria labels", "inclusive"],
            "common_mistakes": ["less than 3 examples", "vague examples", "no WCAG mention"],
            "ideal_length": 100
        },
        {
            "q": "How would you redesign a checkout flow with 70 percent cart abandonment?",
            "keywords": ["friction", "steps", "trust", "guest checkout", "autofill", "error", "progress"],
            "concepts": ["reduce steps", "clear errors", "trust signals", "test", "metric", "heuristic"],
            "common_mistakes": ["no diagnosis before solution", "no success metric", "generic suggestions"],
            "ideal_length": 120
        },
        {
            "q": "What is a design system and what are its benefits and trade-offs?",
            "keywords": ["component", "token", "consistency", "scalability", "maintenance", "adoption"],
            "concepts": ["shared language", "speed", "brand", "rigidity", "cost to build", "governance"],
            "common_mistakes": ["only benefits no trade-offs", "no concrete examples", "too vague"],
            "ideal_length": 100
        },
        {
            "q": "When should you use a modal dialog and when should you avoid it?",
            "keywords": ["interrupt", "focus", "context", "dismiss", "confirmation", "accessibility"],
            "concepts": ["blocking interaction", "critical action", "mobile", "cognitive load", "alternatives"],
            "common_mistakes": ["no when to avoid", "no accessibility mention", "no alternatives"],
            "ideal_length": 90
        },
        {
            "q": "What is the difference between UX and UI? Why does the distinction matter?",
            "keywords": ["research", "flow", "information architecture", "visual", "interaction", "usability"],
            "concepts": ["experience vs interface", "user journey", "aesthetics", "function", "overlap"],
            "common_mistakes": ["too brief", "no concrete example", "saying they are the same"],
            "ideal_length": 90
        },
        {"q": "How would you redesign a legacy interface for mobile?", "keywords": ["responsive", "touch", "navigation", "hierarchy", "testing"], "concepts": ["mobile design", "user research"], "ideal_length": 100},
        {"q": "Explain the importance of typography in UI design.", "keywords": ["hierarchy", "readability", "contrast", "weight", "spacing"], "concepts": ["visual design", "ux"], "ideal_length": 85},
        {"q": "How would you design an onboarding flow for a complex product?", "keywords": ["tutorial", "progressive disclosure", "context", "feedback"], "concepts": ["user education", "first impression"], "ideal_length": 100},
        {"q": "Describe your approach to designing for users with disabilities.", "keywords": ["wcag", "contrast", "keyboard", "screen reader", "testing"], "concepts": ["inclusive design", "accessibility"], "ideal_length": 95},
        {"q": "How do you decide between modal and non-modal dialogs?", "keywords": ["focus", "urgency", "context", "interruption"], "concepts": ["interaction design", "user flow"], "ideal_length": 85},
        {"q": "How would you improve a navigation system with 50+ pages?", "keywords": ["information architecture", "hierarchy", "search", "breadcrumb"], "concepts": ["ia", "wayfinding"], "ideal_length": 100},
        {"q": "Describe your process for validating a design with users.", "keywords": ["testing", "prototype", "feedback", "iteration", "insights"], "concepts": ["user research", "validation"], "ideal_length": 95},
        {"q": "How do you handle conflicting feedback from stakeholders?", "keywords": ["data", "user research", "compromise", "reasoning"], "concepts": ["design thinking", "stakeholder management"], "ideal_length": 90},
        {"q": "What is the role of color in UI design?", "keywords": ["psychology", "contrast", "meaning", "consistency", "brand"], "concepts": ["visual design", "emotion"], "ideal_length": 85},
        {"q": "How would you design an error state for a form?", "keywords": ["clarity", "recovery", "guidance", "location", "tone"], "concepts": ["ux writing", "error handling"], "ideal_length": 85},
        {"q": "Explain the concept of mental models in design.", "keywords": ["user expectation", "conceptual", "learning", "intuitive"], "concepts": ["psychology", "usability"], "ideal_length": 90},
        {"q": "How do you balance aesthetics and functionality?", "keywords": ["visual design", "usability", "brand", "performance"], "concepts": ["design discipline", "trade-offs"], "ideal_length": 85},
        {"q": "What is dark mode design and what are its challenges?", "keywords": ["contrast", "readability", "battery", "preference", "consistency"], "concepts": ["design variant", "user preference"], "ideal_length": 90},
    ]
}

# Phrases that genuinely indicate an example was given.
# ("like" alone is excluded on purpose -- too common a filler word
# and triggers false positives, e.g. "I would like to use a hash map")
EXAMPLE_MARKERS = [
    "for example", "for instance", "such as", "e.g.", "like when",
    "in particular", "in my experience", "i once", "i worked on",
    "a case where", "imagine", "consider a", "say a company", "say a user"
]

STRUCTURE_MARKERS = [
    "first", "second", "third", "finally", "however",
    "for example", "such as", "because", "therefore",
    "on the other hand", "in contrast", "whereas",
    "for instance", "this means", "which means"
]

# tracks the last question shown per role, so we don't immediately repeat it
_recent: dict = {}
# tracks per-user score history: {user_id: {"points": [...], "by_role": {role: [...]}}}
_user_scores: dict = {}


@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('.', filename)


@app.route('/question')
def get_question():
    role = request.args.get('role', '').strip()

    if role not in QUESTIONS:
        return jsonify({'error': f'Unknown role: {role}'}), 400

    pool = QUESTIONS[role]
    last = _recent.get(role)
    available = [q for q in pool if q['q'] != last] or pool
    chosen = random.choice(available)
    _recent[role] = chosen['q']

    return jsonify({'question': chosen['q'], 'role': role})


@app.route('/submit', methods=['POST'])
def submit():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({'error': 'No data received'}), 400

    role = body.get('role', '').strip()
    answer = body.get('answer', '').strip()
    user_id = body.get('user_id', 'anonymous').strip() or 'anonymous'
    question = _recent.get(role, '')

    if role not in QUESTIONS:
        return jsonify({'error': 'Invalid role'}), 400
    if len(answer) < 20:
        return jsonify({'error': 'Answer too short'}), 400

    feedback, points, breakdown = grade(role, answer, question)

    user_record = _user_scores.setdefault(user_id, {'points': [], 'by_role': {}})
    user_record['points'].append(points)
    user_record['by_role'].setdefault(role, []).append(points)

    return jsonify({
        'feedback': feedback,
        'points': points,
        'breakdown': breakdown,
        'max_points': 3
    })


@app.route('/status')
def get_status():
    user_id = request.args.get('user', 'anonymous')
    score_data = _user_scores.get(user_id)

    if not score_data or not score_data['points']:
        return jsonify({'score': 0, 'answered': 0, 'average': 0, 'by_role': {}})

    total = sum(score_data['points'])
    answered = len(score_data['points'])
    avg = total / answered

    return jsonify({
        'score': total,
        'answered': answered,
        'average': round(avg, 2),
        'by_role': score_data['by_role']
    })


def grade(role: str, answer: str, question: str) -> tuple:
    meta = next(
        (q for q in QUESTIONS.get(role, []) if q['q'] == question),
        None
    )
    if not meta:
        return basic_grade(answer)

    answer_lower = answer.lower()
    words = answer_lower.split()
    word_count = len(words)
    ideal_length = meta.get('ideal_length', 80)

    # --- length score (0-2) ---
    length_score = 0
    if word_count >= ideal_length:
        length_score = 2
    elif word_count >= ideal_length * 0.6:
        length_score = 1

    # --- keyword score (0-2) ---
    keywords = meta.get('keywords', [])
    keyword_hits = [k for k in keywords if k.lower() in answer_lower]
    keyword_score = 0
    if keywords:
        ratio = len(keyword_hits) / len(keywords)
        if ratio >= 0.5:
            keyword_score = 2
        elif ratio >= 0.2:
            keyword_score = 1

    # --- concept score (0-2) ---
    concepts = meta.get('concepts', [])
    concept_hits = [c for c in concepts if c.lower() in answer_lower]
    concept_score = 0
    if concepts:
        ratio = len(concept_hits) / len(concepts)
        if ratio >= 0.4:
            concept_score = 2
        elif ratio >= 0.2:
            concept_score = 1

    # --- structure score (0-2) ---
    structure_hits = sum(1 for m in STRUCTURE_MARKERS if m in answer_lower)
    structure_score = 2 if structure_hits >= 2 else (1 if structure_hits == 1 else 0)

    # --- example score (0-2) ---
    has_example = any(m in answer_lower for m in EXAMPLE_MARKERS)
    example_score = 2 if has_example else 0

    raw = (
        length_score * 0.2 +
        keyword_score * 0.3 +
        concept_score * 0.3 +
        structure_score * 0.1 +
        example_score * 0.1
    )

    if raw >= 1.5:
        points = 3
    elif raw >= 1.0:
        points = 2
    elif raw >= 0.5:
        points = 1
    else:
        points = 0

    feedback = build_feedback(
        points, word_count, ideal_length,
        keyword_hits, keywords,
        concept_hits, concepts,
        has_example
    )

    breakdown = build_breakdown(
        keyword_hits, keywords,
        concept_hits, concepts,
        has_example, word_count, ideal_length,
        structure_hits
    )

    return feedback, points, breakdown


def build_feedback(points, word_count, ideal_length,
                    keyword_hits, keywords,
                    concept_hits, concepts,
                    has_example) -> str:

    lines = []

    if points == 3:
        lines.append("Well done smartass, you sound like you know your shi and you got the examples to back it up, gg gng")
        if keyword_hits:
            lines.append(f"Good job for using key terms like: {', '.join(keyword_hits)}.")
        if not has_example:
            lines.append("aint no way dawg, gj but it could be better icl, missing an example")

    elif points == 2:
        lines.append("yeah u could do sm better, put in sm effort for god's sake, its for ur own job")
        missed_keywords = [k for k in keywords if k not in keyword_hits][:3]
        if missed_keywords:
            lines.append(f"u missed sm key terms icl, so improve here or else ur cooked dawg: {', '.join(missed_keywords)}.")
        if not has_example:
            lines.append("dont keep yappin bru its givin needy, give sm examples to make this answer more goated")
        if word_count < ideal_length * 0.7:
            lines.append("yap a lil more dawg or else the interviewer will kick u out as fast as u finished tht answer")

    elif points == 1:
        lines.append("ye study harder this aint js it bru")
        if word_count < ideal_length * 0.5:
            lines.append("yap a lil more dawg or else the interviewer will kick u out as fast as u finished tht answer")
        missed_concepts = [c for c in concepts if c not in concept_hits][:3]
        if missed_concepts:
            lines.append(f"u had many key ideas missin, tht aint finna gibbu a job unless u yap abt em: {', '.join(missed_concepts)}.")
        if not has_example:
            lines.append("use examples bru or else they aint finna let u slide")

    else:
        lines.append("man ts is so wrong, go back and study fr gng or u finna be jobless ash")
        lines.append("start with the definition. explain how it works. give an example and dont fumble gng")
        if keywords:
            lines.append(f"use terms like this lil bru: {', '.join(keywords[:4])}.")

    return " ".join(lines)


def build_breakdown(keyword_hits, keywords,
                     concept_hits, concepts,
                     has_example, word_count, ideal_length,
                     structure_hits) -> str:
    lines = []

    if keywords and len(keyword_hits) >= len(keywords) * 0.5:
        lines.append(f"+ used key technical terms like ({', '.join(keyword_hits[:3])})")
    elif keyword_hits:
        lines.append(f"~ some technical terms present but need more emphasis ({', '.join(keyword_hits[:2])})")
    else:
        lines.append("- missing key technical terminology")

    if concepts and len(concept_hits) >= len(concepts) * 0.4:
        lines.append("+ gg gng ur pretty good on the core concepts")
    elif concept_hits:
        lines.append("~ core concepts touched on but u need to yap on more")
    else:
        lines.append(f"- ye bru u gotta yap more ({word_count} vs ~{ideal_length} ideal) or else u finna be cooked ash icl")

    if has_example:
        lines.append("+ included an example, good job dawg")
    elif word_count < ideal_length * 0.6:
        lines.append("- answer is too short AND missing an example, add one to make it convincing")
    else:
        lines.append("- touch grass and put in a real example")

    if structure_hits >= 2:
        lines.append("+ g00d structure markers (first, second, finally) to organize your answer, bru finally bothered lockin in on ts")
    else:
        lines.append("- yea bru u need to start lockin in on structure, ts aint tuff icl")

    return '\n'.join(lines)


def basic_grade(answer: str) -> tuple:
    """Fallback grading if no question metadata is found. Checks length and presence of an example."""
    has_example = any(m in answer.lower() for m in EXAMPLE_MARKERS)
    words = len(answer.split())

    if words < 30:
        feedback = "u are absolutely jobless fam try to yap more and give examples or else u finna be homeless ash"
        points = 0
        breakdown = "- answer is too short, add more detail and examples"
    elif words < 80:
        feedback = "bro u gotta yap more to get a job, add more detail and examples or else u finna be homeless ash"
        points = 1
        breakdown = "~ decent attempt but light on detail, add more substance"
    elif words < 150:
        feedback = "ye no ts fr gng, on ur way to landin on a hot bag, keep cookin"
        points = 2
        breakdown = "+ decent shi ngl\n~ could use more specificity to really seal it"
    else:
        feedback = "ma goat man u finally locked in on ts and u sound like u know ur shi, gg gng"
        points = 3
        breakdown = "+ thorough answer with good depth, gg gng"

    if not has_example:
        breakdown += "\n- no example detected, always back up your answer with one"

    return feedback, points, breakdown


@app.route('/health')
def health():
    return jsonify({
        'status': 'running',
        'ai_enabled': False,
        'grader': 'rule-based (no external ai calls)',
        'roles': list(QUESTIONS.keys()),
        'total_questions': sum(len(v) for v in QUESTIONS.values())
    })


if __name__ == '__main__':
    print("\n" + "=" * 52)
    print(" unJ0bless Backend")
    print("=" * 52)
    print(" URL    -> http://localhost:8000")
    print(" Health -> http://localhost:8000/health")
    print(" Grader -> http://localhost:8000/submit (im sigma enough to not use AI gng)")
    print(f" Roles  -> {', '.join(QUESTIONS.keys())}")
    print(f" Total Questions -> {sum(len(v) for v in QUESTIONS.values())}")
    print("=" * 52 + "\n")
    app.run(debug=True, port=8000)