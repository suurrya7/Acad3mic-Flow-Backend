# Acad3mic-Flow AI Backend

This is the backend for the Acad3mic-Flow AI platform, built with FastAPI, Supabase, and a secure internal AI layer.

## 📚 Documentation
- **[API Contract (Endpoints & Payloads)](API_DOCUMENTATION.md)**: Refer to this for frontend integration.
- **Swagger UI**: Visit `/docs` (Development only).

## Prerequisites

1. Python 3.11+
2. Supabase Project
3. PayU Merchant Account
4. Google Gemini API Key

## Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Variables**:
   - Copy `.env.example` to `.env`.
   - Fill in all credentials.
   - For Production: Set `ENV=production` and `PROD_ORIGINS` to your frontend domain.

3. **Database Setup**:
   - Run the SQL script `schema.sql` in your Supabase SQL Editor.
   - **Important**: Create a public bucket named `assignments` in Supabase Storage.

4. **Run Application**:
   ```bash
   uvicorn app.main:app --reload
   ```

## Key Features

- **Auth**: Supabase Auth integration.
- **Chat**: Academic chat with **Long-Term Memory** via rolling summaries.
- **Assignments**: PDF/DOCX ingestion + **3-Pass Humanizer** for natural flow.
- **Payments**: PayU integration for word credits.
- **Safety**: Strict provider secrecy and monthly word balance resets.

## Security Note

The underlying AI model is strictly hidden from API responses. All outputs are labeled as "Acad3mic-Flow AI".
