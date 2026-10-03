# 🛣️ Road Cost AI — Smart Civil Cost Estimator

AI-powered road construction cost estimation tool built for **Maharashtra PWD** engineers. Upload site photos, get AI-driven pavement analysis, and generate complete Bill of Quantities (BOQ) with automated cost calculations.

![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)

## ✨ Features

- **📸 AI Site Photo Analysis** — Upload road photos for automatic pavement distress detection
- **📐 3D Pavement Cross-Section** — Interactive isometric CAD visualization of road layers
- **📊 Automated BOQ Generation** — Intelligent SSR item selection & quantity calculation
- **💰 Cost Estimation** — Subtotal, GST, and statutory markup calculations in Crores/Lakhs
- **💬 AI Chat Assistant** — Ask road engineering questions with live project context
- **📥 CSV Export** — Download detailed estimates for reporting

## 🚀 Live Demo

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://your-app-name.streamlit.app)

## 🛠️ Setup

### Local Development

```bash
pip install -r requirements.txt
streamlit run app.py
```

### Streamlit Cloud Deployment

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo
4. Set **Main file path**: `app.py`
5. Add your API key in **Secrets** (Settings → Secrets):
   ```toml
   OPENROUTER_API_KEY = "your-api-key-here"
   ```

## 📁 Project Structure

```
├── app.py                 # Main Streamlit UI
├── ai_module.py           # AI backend (OpenRouter)
├── estimate_service.py    # Estimation workflow coordinator
├── quantity_engine.py     # Deterministic quantity calculations
├── cost_engine.py         # Cost calculation engine
├── schemas.py             # Shared data structures
├── ssr_loader.py          # SSR Excel/CSV parser
├── ssr_selector.py        # Item candidate search & ranking
├── requirements.txt       # Python dependencies
├── .streamlit/
│   └── config.toml        # Streamlit theme configuration
└── tests/                 # Unit tests
```

## 📋 Tech Stack

- **Frontend**: Streamlit with custom CSS & SVG visualizations
- **AI**: OpenRouter API (free vision & text models)
- **Data**: Maharashtra PWD Schedule of Rates (SSR)
- **Engine**: Pure Python arithmetic (no AI in calculations)

## 👨‍💻 Author

**Kalash** — Built with ❤️ for Maharashtra PWD road infrastructure
