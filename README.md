# unJobless - AI Interview Practice

A Flask-based interview practice platform with rule-based AI grading. Practice for Software Engineer, Consultant, Data Analyst, and UI Designer roles.

## Features

- **4 Interview Roles**: Software Engineer, Consultant, Data Analyst, UI/UX Designer
- **Rule-based AI Grading**: No external API calls - grades locally using keyword matching, concept detection, and structure analysis
- **Real-time Feedback**: Live Interview Flow**: Questions served from a curated bank, instant grading with detailed breakdowns
- **Word Count Tracking**: Live word counter with visual feedback at 50+ words
- **Terminal/Pixel Aesthetic**: VT323 + Press Start 2P fonts, dark theme, glitchy cursor

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python app.py

# Open http://localhost:8000
```

## Project Structure

```
Project_dp/
├── app.py              # Flask backend with question bank & grader
├── index.html          # Main page - role selection + interview
├── questions.html      # Standalone interview page (role via URL)
├── questions.js        # Interview logic for questions.html
├── questions.css       # Shared styles for interview pages
├── script.js           # Interview logic for index.html
├── requirements.txt    # Python dependencies
└── README.md
```

## Usage

### Main Flow (index.html)
1. Open `http://localhost:8000`
2. Click a role button
3. Answer the question (minimum 25 chars)
4. Click "Submit Answer"
5. View AI feedback with score breakdown
6. Click "Next Question" for another

### Direct Role Link (questions.html)
Append role to URL: `http://localhost:8000/questions.html?role=Software%20Engineer`

Valid roles: `Software Engineer`, `Consultant`, `Data Analyst`, `UI Designer`

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Serves index.html |
| `/questions.html` | GET | Serves questions.html |
| `/question?role=X` | GET | Returns random question for role |
| `/submit` | POST | Grades answer, returns feedback + score |
| `/health` | GET | Health check + stats |

### `/submit` Request
```json
{
  "role": "Software Engineer",
  "answer": "Your answer here..."
}
```

### `/submit` Response
```json
{
  "feedback": "Detailed feedback text...",
  "points": 2,
  "max_points": 3,
  "breakdown": "Score breakdown with markers..."
}
```

## Grading Logic (Rule-based, No AI)

The grader evaluates answers against question metadata:
- **Keywords** - Required technical terms
- **Concepts** - Higher-level ideas that should appear
- **Examples** - Detection of concrete examples ("for example", "e.g.", specific case studies)
- **Structure** - Transition words (first, second, finally, however, etc.)
- **Length** - Compared to `ideal_length` per question

Scores: 0-3 points per question. Breakdown shows `+` strengths, `~` partial, `-` weaknesses.

## Development

```bash
# Run with auto-reload
python app.py

# Health check
curl http://localhost:8000/health
```

## Dependencies

- Flask (Python)
- Google Fonts: Press Start 2P, VT323 (loaded via CDN)

## License

MIT - Built for Hack Club