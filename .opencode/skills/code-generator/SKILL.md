---
name: code-generator
description: Generates code for any specific objective assigned by the user. Does not implement directly - generates complete, production-ready code files that the user can review and apply.
version: "1.0.0"
---

# Code Generator Skill

Generates complete, production-ready code files for any specific objective assigned by the user. This skill **does not implement directly** - it generates complete, reviewed, production-ready code files that the user can review and apply.

## Capabilities

- Generates complete, production-ready code files (not snippets)
- Follows existing project conventions, patterns, and code style
- Respects existing project structure, frameworks, and dependencies
- Generates complete files (not snippets) with proper imports, types, and error handling
- Includes proper error handling, type hints, and documentation
- Follows existing project conventions (linting, formatting, testing patterns)
- Outputs complete file paths and contents ready for user review

## When to Use

- User asks "generate code for..." or "write code for..."
- User wants a new feature, component, endpoint, or module implemented
- User wants a bug fix implemented as a code change
- User wants refactoring done as generated code
- Any task where user wants code generated for review before applying

## Workflow

1. **Analyze the objective** - Understand what code needs to be generated
2. **Explore the codebase** - Find existing patterns, conventions, similar files
3. **Generate complete files** - Write complete, production-ready files with:
   - Proper imports and dependencies
   - Type hints (if Python/TypeScript)
   - Error handling
   - Documentation/comments matching project style
   - Tests if project has tests
4. **Output complete file paths and contents** - User reviews and applies

## Output Format

Always output as complete file operations the user can apply:

```
## Generated Files

### `path/to/file.py`
```python
# Complete file content here
```

### `path/to/test_file.py`
```python
# Complete test file content here
```
```

## Project Conventions (from this codebase)

- **Python/Flask** backend (`app.py`)
- **Vanilla JS/CSS/HTML** frontend (`index.html`, `questions.html`, `questions.js`, `script.js`, `questions.css`)
- **Flask** for backend API
- **Vanilla JS** (ES6 modules) for frontend
- **Vanilla CSS** with CSS custom properties
- **No TypeScript** - plain JavaScript
- **No build step** - vanilla JS/CSS served directly
- **Flask** for Python backend
- **Google Fonts** (Press Start 2P, VT323) via CDN
- **Terminal/pixel aesthetic** (VT323 + Press Start 2P fonts)
- **Dark theme** with CSS custom properties

## Python Conventions (from app.py)

- Flask routes with `@app.route`
- Type hints where practical
- JSON responses with `jsonify`
- Error handling with try/except
- Rule-based grading logic in `grade_answer()`
- Question bank in `QUESTIONS` dict
- Health endpoint at `/health`

## JavaScript Conventions (from script.js, questions.js)

- ES6 modules where possible
- `fetch` API for API calls
- DOM manipulation with `document.querySelector`/`querySelectorAll`
- Event listeners with `addEventListener`
- Async/await for async operations
- CSS custom properties for theming

## CSS Conventions (from questions.css)

- CSS custom properties for colors/fonts
- Mobile-first responsive design
- Terminal/pixel aesthetic (VT323, Press Start 2P)
- Dark theme with CSS variables
- Animations with dark mode support

## Python Dependencies (from requirements.txt)

- Flask
- gunicorn (for production)

## Output Requirements

When generating code, always output:

1. **Complete file paths** relative to project root
2. **Complete file contents** - no snippets, no "..." placeholders
3. **Follow existing patterns** exactly as found in codebase
4. **Include tests** if project has test patterns
5. **Note any new dependencies** needed in requirements.txt
6. **No explanations** - just the file outputs

## Example Output Format

```
## Generated Files

### `app.py`
```python
from flask import Flask, request, jsonify
from typing import Dict, List, Optional
import random

app = Flask(__name__)

QUESTIONS: Dict[str, List[Dict]] = {
    "Software Engineer": [
        {
            "id": "se-1",
            "question": "Explain the difference between a stack and a queue.",
            "keywords": ["LIFO", "FIFO", "stack", "queue", "push", "pop", "enqueue", "dequeue"],
            "concepts": ["data structures", "memory management", "access patterns"],
            "ideal_length": 150,
            "examples": ["browser history", "undo/redo", "printer queue", "task scheduling"]
        }
    ],
    # ... more questions
}

def grade_answer(role: str, answer: str, question: Dict) -> Dict:
    """Grade an answer using rule-based scoring."""
    # ... grading logic
    return {
        "feedback": "...",
        "points": 2,
        "max_points": 3,
        "breakdown": "..."
    }

@app.route("/question")
def get_question():
    role = request.args.get("role", "Software Engineer")
    questions = QUESTIONS.get(role, QUESTIONS["Software Engineer"])
    question = random.choice(questions)
    return jsonify({"question": question["question"], "id": question["id"]})

@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json()
    role = data.get("role")
    answer = data.get("answer")
    question_id = data.get("question_id")
    # ... grading logic
    return jsonify(result)

@app.route("/health")
def health():
    return jsonify({"status": "ok", "questions_count": sum(len(q) for q in QUESTIONS.values())})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
```

### `questions.js`
```javascript
// Complete file content
```

### `requirements.txt`
```
Flask==3.0.0
gunicorn==21.2.0
```
```

## Important Notes

- **DO NOT** implement directly - always generate files for user review
- **DO NOT** run commands to apply changes
- **DO** explore codebase first to understand patterns
- **DO** output complete, runnable files
- **DO** follow existing code style exactly
- **DO** include any new dependencies needed