# Acad3mic-Flow API Contract (v1.0 Frozen)

**Base URL**: `http://localhost:8000` (Dev) / `https://api.acad3mic-flow.com` (Prod)
**Auth**: Bearer Token (Supabase JWT) in header: `Authorization: Bearer <token>`

---

## 1. Authentication

**POST /auth/signup** (Developer Helper)
- **Auth**: None
- **Body**:
  ```json
  {
    "email": "user@example.com",
    "password": "yourpassword"
  }
  ```
- **Response**: User object.

**POST /auth/login** (Developer Helper)
- **Auth**: None
- **Body**:
  ```json
  {
    "email": "user@example.com",
    "password": "yourpassword"
  }
  ```
- **Response**:
  ```json
  {
    "access_token": "eyJh...",
    "token_type": "bearer",
    "user": { ... }
  }
  ```
- **Usage**: Use this `access_token` in the "Authorize" button in Swagger UI.

**GET /auth/me**
- **Auth**: Required
- **Response**:
  ```json
  {
    "id": "uuid",
    "email": "user@example.com",
    "profile": {
      "id": "uuid",
      "email": "user@example.com",
      "word_balance": 2000,
      "subscription_tier": "Free",
      "last_reset_date": "2023-10-01"
    }
  }
  ```

## 2. Usage & Credits
**GET /usage/words**
- **Auth**: Required
- **Response**:
  ```json
  {
    "word_balance": 1500,
    "subscription_tier": "Free"
  }
  ```

## 3. Chats (with Memory)
**GET /chats**
- **Auth**: Required
- **Response**: List of chats
  ```json
  [
    {
      "id": "uuid",
      "title": "History Essay Help",
      "created_at": "timestamp",
      "updated_at": "timestamp"
    }
  ]
  ```

**POST /chats**
- **Auth**: Required
- **Body**:
  ```json
  {
    "title": "New Chat Topic"
  }
  ```
- **Response**:
  ```json
  {
    "id": "uuid",
    "title": "New Chat Topic",
    "created_at": "timestamp",
    "updated_at": "timestamp"
  }
  ```

**GET /chats/{chat_id}**
- **Auth**: Required
- **Response**: Chat history
  ```json
  {
    "id": "uuid",
    "title": "History Essay Help",
    "messages": [
      {
        "id": "uuid",
        "role": "user",
        "content": "Hello",
        "created_at": "timestamp"
      },
      {
        "id": "uuid",
        "role": "assistant",
        "content": "Hi! I am Acad3mic-Flow AI.",
        "created_at": "timestamp"
      }
    ]
  }
  ```

**POST /chats/{chat_id}/messages**
- **Auth**: Required
- **Note**: 
  - Deducts words from balance. 
  - Updates long-term memory. 
  - **Auto-Title**: For new chats, the first message triggers an AI-generated title update in the background.
- **Body**:
  ```json
  {
    "content": "Can you explain the French Revolution?",
    "document_ids": ["uuid-optional"]
  }
  ```
- **Response** (Updates real-time):
  ```json
  {
    "id": "uuid",
    "role": "assistant",
    "content": "The French Revolution was...",
    "created_at": "timestamp"
  }
  ```

**POST /chats/{chat_id}/messages/stream**
- **Auth**: Required
- **Rate Limit**: 20 requests/minute per user.
- **Note**: Supports real-time streaming using Server-Sent Events (SSE). Can also detect assignment requests and stream academic content.
- **Body**: Same as standard message.
  ```json
  {
    "content": "Write an essay about...",
    "document_ids": ["uuid-optional"]
  }
  ```
- **Response**: Stream of SSE events (`text/event-stream`). Each event data is a JSON string.
  - **Event Types**:
    - `status`: Progress updates (e.g., "Analyzing request...", "Thinking...")
    - `content`: Chunks of the AI response text.
    - `complete`: Final JSON payload with full message details.
    - `error`: Error messages.
  - **Example Event**:
    ```
    data: {"type": "content", "content": "The French Revolution..."}
    ```
  - **Completion Event**:
    ```
    data: {"type": "complete", "message_id": "uuid", "final_content": "Full text...", "word_count": 150}
    ```

## 4. Documents
**POST /documents/upload**
- **Auth**: Required
- **Body**: `multipart/form-data`
  - `file`: (Binary PDF, DOCX, or TXT)
- **Response**:
  ```json
  {
    "id": "uuid",
    "filename": "lecture_notes.pdf",
    "created_at": "timestamp"
  }
  ```

**GET /documents**
- **Auth**: Required
- **Response**: List of uploaded docs

## 5. Assignments
**POST /assignments/submit**
- **Auth**: Required
- **Note**: Deducts words based on output length. Uses 3-pass Humanizer.
- **Body**:
  ```json
  {
    "topic": "Impact of AI on Education",
    "instructions": "Write a 1000 word argumentative essay.",
    "document_ids": ["uuid-1", "uuid-2"]
  }
  ```
- **Response**:
  ```json
  {
    "id": "uuid",
    "title": "Impact of AI on Education",
    "status": "completed",
    "output_text": "Title: Impact of AI...\n\nIntroduction...",
    "created_at": "timestamp"
  }
  ```
  *(Note: If processing takes time, response might be immediate with status 'processing' or wait until 'completed'. Current implementation waits.)*

**GET /assignments/{assignment_id}**
- **Auth**: Required
- **Response**: Full assignment details.

## 6. Payments (PayU)
**POST /payments/payu/create-order**
- **Auth**: Required
- **Body**:
  ```json
  {
    "amount": 699,
    "productinfo": "Basic Plan",
    "firstname": "Surya",
    "email": "surya@example.com"
  }
  ```
- **Response**:
  ```json
  {
    "txnid": "txn12345",
    "hash": "abcdef...",
    "amount": 699,
    "key": "merchant_key",
    "surl": "...",
    "furl": "..."
  }
  ```
- **Frontend Action**: Submit these fields as a FORM POST to PayU URL.

**POST /payments/payu/webhook**
- **Auth**: Public (called by PayU)
- **Body**: Form Data from PayU
- **Action**: Verifies hash, updates transaction to 'success', credits words.

## 7. Admin API
**Base Path**: `/admin`
**Auth**: Required (User must have `is_admin=true`)

### Dashboard
**GET /admin/dashboard/stats**
- **Response**: System statistics (users, revenue, active sessions).

### User Management
**GET /admin/users**
- **Params**: `page`, `per_page`, `search`, `tier`
- **Response**: Paginated list of users.

**GET /admin/users/{id}**
- **Response**: User profile + usage stats.

**PUT /admin/users/{id}**
- **Body**: `{"subscription_tier": "Premium", "word_balance": 50000}`
- **Response**: Updated user profile.

**POST /admin/users/{id}/credits**
- **Body**: `{"amount": 500, "reason": "bonus"}`
- **Response**: New balance.

### Humanizer Prompts
**GET /admin/prompts**
- **Response**: List of all prompt versions.

**POST /admin/prompts**
- **Body**: `{"prompt_text": "...", "notes": "v2"}`
- **Response**: Created prompt version.

**POST /admin/prompts/{id}/activate**
- **Response**: Sets prompt as active.

**POST /admin/prompts/test**
- **Body**: `{"prompt_text": "...", "sample_text": "..."}`
- **Response**: Humanized output.

### Transactions
**GET /admin/transactions**
- **Params**: `page`, `status`
- **Response**: List of payments.
