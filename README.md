# JARVIS API MVP

A first, deliberately small Windows desktop-assistant backend. It uses Groq for language-model responses and has one allowlisted local action: opening Notepad. It does **not** yet include a GUI, microphone, webcam, memory, web search, or arbitrary shell/PowerShell execution.

## 1. Requirements

- Windows 10/11, 64-bit
- Python 3.11 recommended for the broader project roadmap
- A Groq API key and internet access for AI responses

Check installed Python versions in PowerShell:

```powershell
py -0p
```

## 2. Create an environment

Open PowerShell in this folder:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If Python 3.11 is not installed, install it or use a Python version supported by the chosen libraries. Do not mix this project's dependencies into another project's virtual environment.

If PowerShell blocks activation, use this for the current terminal session only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 3. Configure the API key

```powershell
Copy-Item .env.example .env
notepad .env
```

Replace `GROQ_API_KEY=replace_me` with your key. Keep `.env` private and never commit it to Git. `GROQ_MODEL` must be a model ID currently available to your Groq account; model availability and pricing may change.

## 4. Run the backend

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs` in your browser.

- `GET /health` confirms the backend is alive and whether the key setting is present (it never returns the key).
- `POST /chat` accepts `{"message":"Say hello"}`.
- Try `{"message":"Open Notepad"}` to test the single approved desktop action on Windows.

Keep the server bound to `127.0.0.1` during development. Do not expose it directly to a public network.

## 5. Run unit tests

In another PowerShell terminal with the virtual environment active:

```powershell
pytest -q
```

These tests validate the action registry without opening real applications. The live Groq API has not been tested as part of this scaffold; it requires your own key and a model your account can access.

## Safety limits

- No arbitrary shell, PowerShell or Python execution.
- Only the `open_notepad` tool is registered.
- The tool accepts no arguments and only runs on Windows.
- The API key stays in the backend `.env` file.
- Do not add file deletion, message sending, installation or shutdown actions without explicit validation and confirmation.
