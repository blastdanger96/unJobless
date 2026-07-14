### unJobless - AI Interview Practice

unJobless is a light Flask-based AI grader for the most asked interview questions, made specifically to provide a All-in-One plateform for cringe Gen-z job seekers who want to actively learn and improve to score a decent job, in such a shitty job market.

### Quick Start
1. You can directly use the hosted website link from Vercel:- https://unjobless.vercel.app/index.html
![alt text](<Screenshot 2026-07-14 at 4.28.06 PM.png>)

![alt text](<Screenshot 2026-07-14 at 4.28.27 PM.png>)

![alt text](<Screenshot 2026-07-14 at 4.28.59 PM.png>)


2. You can download the required code and dependencies yourself and run it localhost (MAKE SURE TO REMOVE COMMENTS FROM PYTHON app.py CODE)
```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python app.py

# Open the said running local server given in the terminal
```

## Project Structure

```
unJobless/
├── app.py                # Flask backend: auth, sessions, grading,
├── ai_teacher.py          #OpenAI grading (hybrid with rule fallback)
├── cost_tracker.py        # OpenAI API cost tracking & circuit breaker
├── questions.json         # Question bank (4 roles, ~75 questions)
├── requirements.txt       # Python deps: flask, openai, python-dotenv, PyJWT
├── index.html             # Landing page 
├── style.css              # index.html styles
├── script.js              # index.js rules and logic
├── questions.html         # Interview page 
├── questions.js           # Interview rules and logic 
├── questions.css          # Interview page styles 
└── README.md
```



### DISCLAIMER

I have used AI for:-
1. When I started to code for unJobless, I was very much familiar with python but the course I had learnt it using didn't teach me anything about github, so I had to take AI's help as I was completely blank in the beginning to commit my code and learn how things work.

2. Solving bugs in the code I was oblivious to and unable to crack many times, this includes entire page failures and function not being able to get called properly and utilized, to basic spelling errors and excessive relience on tutorial turning the code complicated.

3. For a new language (I was completely new to json so I had to ask AI to give me the structure to write the questions in them for the question bank I made, used in rule based learning in python)

I have specifically used Nemotron 3 Ultra 550B A55B model, NVIDA's latest model which gives you free tokens on opencode for this help and for committing I have also used VS-Code's own baked Copilot and it's been really useful. Taught me alot of stuff i'd be struggling for in minutes and I am super grateful.

Also please don't judge my commit comments, I was new to github and didn't know you gotta be serious with them, I have understood my mistake and will try to fix them, so I am also open for feedback!

## Dependencies

requirements.txt (4 packages)
- Package Version 
- flask latest  (Web framework)
- openai  >=1.0.0 OpenAI API client (AI grading)
- python-dotenv >1.0.0  Load .env config
- PyJWT latest  (JWT token auth)


## License

MIT - Built for Hack Club