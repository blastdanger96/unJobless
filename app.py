from flask import Flask, Request, jsonify, send_from_directory
import random
import os
import re
app = Flask(__name__, static_folder='.')

# ================================================================
#  QUESTION BANK
#  Each question carries:
#  - keywords: terms a strong answer should use
#  - concepts: higher level ideas that should appear
#  - common_mistakes: things weak answers typically do
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
    ],
 
    "Consultant": [
        {
            "q": "A client's revenue dropped 20% last quarter. How do you diagnose the problem?",
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
            "q": "How would you redesign a checkout flow with 70% cart abandonment?",
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
    ]
}
 


_recent: dict = {}

@app.route('/')
def index():
    return send_from_directory('.','index.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('.', filename)

@app.route('/question')
def get_question():
    role = request.args.get('role','').strip()

    if role not in QUESTIONS:
        return jsonify({'error': f'Unknown role: {role}'}), 400
    
    pool = QUESTIONS[role]
    last =_recent.get(role)
    available = [q for q in pool if q['q'] != last]
    chosen = random.choice(available)
    _recent[role] = chosen['q']

    return jsonify({'question': chosen['q'], 'role': role})

@app.route('/submit', methods=['POST'])
def submit():
    body = request.get_json()
    if not body:
        return jsonify({'error': 'No data received'}), 400
    
    role = body.get('role', '').strip()
    answer = body.get('answer','').strip()
    question = _recent.get(role,'')

    if role not in QUESTIONS:
        return jsonify({'error': 'Invalid role'}), 400
    if len(answer) < 20:
        return jsonify({'error': 'Answer too short'}), 400
    
    feedback, points, breakdown = grade(role, answer, question)

    return jsonify({
        'feedback': feedback,
        'points': points,
        'breakdown': breakdown,
        'max_points': 3
    })

def grade(role: str, answer: str, question: str) -> tuple:
    meta = next(
        (q for q in QUESTIONS.get(role,[]) if q['q'] == question),
        None
    )
    if not meta:
        return basic_grade(answer)
    
    answer_lower = answer.lower()
    words = answer_lower.split()
    words_count = len(words)
    ideal_length = meta.get('ideal_length', 80)

    length_score = 0
    if word_count>= ideal_length:
        length_score = 2

    elif words_count>= ideal_length *0.6:
        length_score = 1

    keywords = meta.get('keywords',[])
    keyowrd_hits = [k for k in keywords if k in answer_lower]
    keyword_score = 0
    if len(keywords) > 0:
        ratio = len(keyword_hits) / len(keywords)
        if ratio >= 0.5:
            keyword_score = 2
        elif ratio >= 0.25:
            keyword_score = 1
    
    concepts = meta.get('concepts',[])
    concept_hits = [c for c in concepts if c in answer_lower]
    concept_score= 0
    if leng(concepts) > 0:    
        ratio = len(concepts_hits)/len(concepts)
        if ratio >=0.4:
            concept_score = 2
        elif ratio >= 0.2:
            concept_score = 1

    structure_markers = [
        "first", "second", "third", "finally", "however",
        "for example", "such as", "because", "therefore",
        "on the other hand", "in contrast", "whereas",
        "for instance", "this means", "which means"
    ]
    structure_hits = sum(1 for m in structure_markers if m in answer_lower)
    structure_score = 2 if has_example else 0

    raw = (
        length_score * 0.20 +
        keyword_score *0.25 +
        concept_score * 0.30 +
        structure_score * 0.10 +
        example_score * 0.15
    )

    if raw >= 1.5:
        points = 3
    elif raw >= 1.0:
        points = 2
    elif raw >= 0.5:
        pointers = 1
    else:
        pointers = 0

    feedback = build_feedback(
        points, word_count, ideal_length,
        keyowrd_hits, keywords,
        concept_hits, concepts,
        has_example, structure_hits, meta
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
                   has_example, structure_hits, meta) -> str:

    lines = []

    if points == 3:
        lines.append(
            "Well done smartass, we get it ur smart ash"
        )
        if keyword_hits:
            line.append(f"Good job for writing key pointers, you correctly referenced : {',' .join(keyword_hits[:4])}."\
                        )
            
        if not has_example:
            lines.append(
                "aint no way, good job dawg its could be better icl"
            )    
        elif points == 2:
            lines.append(
                "yeah u could do sm better, put in sm effort for god's sake, its for ur own job"

            )
            missed_keywords = [k for k in keywords if k not in ' '.join(keyword_hits)][:3]
            if missed_keywords:
                lines.append(
                    f"u dumb ash m8 icl, so improve here or else ur cooked dawg: {','.join(missed_keywords)}."
                )
            if not has_example:
                lines.append("dont keep yappin bru its givin needy, give sm examples to make this answer more goated")
            if word_count < ideal_length * 0.7:
                lines.append(
                    "yap a lil more dawg or else the interviewer will kick u out as fast as u finished tht answer")
                
            elif points == 1:
                lines.append(
                    "ye study harder this aint js it bru"
                )
                if word_count<ideal_length * 0.5:
                    lines.append(
                        "yap a lil more dawg or else the interviewer will kick u out as fast as u finished tht answer"
                    )

                missed_concepts = [c for c in concepts if c not in '' .join(concept_hits)][:3]
                if missed_concepts:
                    lines.append(
                        f"u had many key ideas missin, tht aint finna gibbu a job unless u dont yap abt em: {','.join(missed_concepts)}."
                    )
                if not has_example:
                    lines.append("use examples bru or else they aint finna let u slide")
                

            else:
                lines.append(
                    "man ts is so wrong, go back and study fr gng or u finna be jobless ash"
                )
                lines.append(
                    "start with definition. explain how it words. give an example and dont fumble gng"
                )
                if keywords:
                    lines.append(
                        f"use terms like this lil bru: {','.join(keywords[:4])}."
                    )
                return " ".join(lines)
            
def build_breakdown(keyword_hits, keywords,
                    concept_hits, concepts,
                    has_example, word_count, ideal_length,
                    structure_hits) -> str:
    lines = []

    if len(keyword_hits) >= len(keywords) * 0.5:
        lines.append(f"+ used key technical terms like ({','. join(keywords_hits[:3])})")
    elif keywords_hits:
        lines.append(f"~ some technical terms which are present but emphasis on them 9{', '.join(keyword_hits[:2])}")
    else:
        lines.append(" - Missing key technical terminology")

    if len(concepts_hits) >= len(concepts) * 0.4:
        lines.append("A: gg gng ur pretty good")
    elif concepts_hits:
        lines.append(" ~ core concepts u need to yap on more")
    else:
        lines.append(f"- ye bru u gotta yap more than ({word_count} smth like {ideal_length}) or else u finna be cooked ash icl")   

    if has_example:
        lines.append("+ Include a example bru")
    else:
        lines.append("- touch grass and put sm real ex")
           
