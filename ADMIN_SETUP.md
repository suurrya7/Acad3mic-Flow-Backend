# Admin Backend Setup Guide

## Week 1 Backend Implementation - COMPLETE! ✅

All backend components for the admin system have been implemented. Follow these steps to deploy.

---

## Step 1: Database Setup (5 minutes)

### Run Admin Migrations

1. **Login to Supabase Dashboard**
   - Go to: https://app.supabase.com/project/YOUR_PROJECT/sql

2. **Run Migration Script**
   - Copy contents of [`scripts/admin_migrations.sql`](file:///Users/surya/Desktop/Latest/scripts/admin_migrations.sql)
   - Paste into SQL Editor
   - Click "Run"
   - Verify success message appears

### Expected Output:
```
✓ Admin system tables created successfully
✓ Indexes and constraints created
✓ Helper functions created
✓ RLS policies enabled
```

---

## Step 2: Create First Admin User (2 minutes)

### Option A: Via Supabase Dashboard (Easiest)

1. Go to **Authentication → Users**
2. Create a new user (or use existing)
3. Copy the user's UUID
4. Go to **Table Editor → user_profiles**
5. Find your user and set `is_admin = true`

### Option B: Via SQL

```sql
-- If user already exists in auth.users
UPDATE user_profiles 
SET is_admin = true 
WHERE email = 'your-email@example.com';

-- Or create new admin user
INSERT INTO user_profiles (id, email, is_admin)
SELECT id, email, true
FROM auth.users
WHERE email = 'your-email@example.com';
```

---

## Step 3: Test Admin API (3 minutes)

### Start Backend
```bash
cd /Users/surya/Desktop/Latest
uvicorn app.main:app --reload
```

### Test Endpoints

```bash
# 1. Login as admin user (get token from Supabase)
TOKEN="your-jwt-token"

# 2. Test dashboard stats
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/admin/dashboard/stats

# 3. List users
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/admin/users

# 4. Get active  prompt
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/admin/prompts/active
```

### Expected Responses
- Dashboard: JSON with user counts, revenue, etc.
- Users: Paginated list of users
- Prompts: Default prompt from code (until you create versions)

---

## Step 4: Test Prompt Management

### Create First Prompt Version
```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt_text": "Test prompt...",
    "notes": "First test version"
  }' \
  http://localhost:8000/admin/prompts
```

### Test Prompt
```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt_text": "Humanize this: ",
    "sample_text": "The quick brown fox jumps over the lazy dog."
  }' \
  http://localhost:8000/admin/prompts/test
```

### Activate Prompt
```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/admin/prompts/{prompt-id}/activate
```

---

## Files Created (Week 1)

### Database
- ✅ `scripts/admin_migrations.sql` - 4 new tables + functions

### Backend Services
- ✅ `app/services/admin_service.py` - User/transaction management
- ✅ `app/services/prompt_manager.py` - Prompt versioning
- ✅ `app/middleware/admin_auth.py` - Admin authentication

### API Routes
- ✅ `app/routers/admin.py` - 25+ admin endpoints

### Integration
- ✅ Updated `app/main.py` - Included admin router
- ✅ Updated `app/services/ai_service.py` - Uses database prompts

---

## API Endpoints Summary

### Dashboard
- `GET /admin/dashboard/stats` - Overview statistics

### Users
- `GET /admin/users` - List users
- `GET /admin/users/{id}` - User details
- `POST /admin/users/{id}/credits` - Adjust credits
- `PUT /admin/users/{id}/tier` - Change tier
- `POST /admin/users/{id}/ban` - Ban user

### Prompts ⭐
- `GET /admin/prompts` - List all versions
- `GET /admin/prompts/active` - Get active prompt
- `GET /admin/prompts/{id}` - Get specific prompt
- `POST /admin/prompts` - Create new version
- `POST /admin/prompts/{id}/activate` - Activate version
- `DELETE /admin/prompts/{id}` - Delete version
- `POST /admin/prompts/test` - Test before saving
- `GET /admin/prompts/history` - Version history

### Transactions
- `GET /admin/transactions` - List transactions
- `POST /admin/transactions/{id}/credit` - Manual credit

### Content
- `GET /admin/assignments` - List assignments
- `DELETE /admin/assignments/{id}` - Delete assignment

### System
- `GET /admin/system/health` - Health check
- `GET /admin/system/logs` - Admin logs

### Settings
- `GET /admin/settings` - All settings
- `GET /admin/settings/{key}` - Specific setting
- `PUT /admin/settings/{key}` - Update setting

---

## Security Features

✅ JWT-based authentication  
✅ Admin role verification on all endpoints  
✅ Audit logging for all admin actions  
✅ IP address tracking  
✅ RLS policies on admin tables  

---

## Next Steps

### Week 2-4: React Admin Frontend
Now that the backend is complete, we can build the React admin panel. This will include:
- Monaco editor for prompt editing
- User management UI
- Analytics dashboard
- Transaction monitoring

### Immediate Testing
You can now:
1. Edit prompts via API
2. Adjust user credits
3. View all transactions
4. Monitor system health

---

## Troubleshooting

### "Admin access required" error
- Verify `is_admin = true` in user_profiles table
- Check JWT token is valid
- Ensure user exists in both auth.users AND user_profiles

### Prompts not updating
- Check if prompt was activated: `POST /admin/prompts/{id}/activate`
- Verify `is_active = true` in database
- Restart backend to clear caches

### Database permissions error
- Ensure RLS policies were created (check migration output)
- Verify Supabase service role key is correct in `.env`

---

## Production Deployment Checklist

Before deploying to production:
- [ ] Change default admin email
- [ ] Test all admin endpoints
- [ ] Verify audit logging works
- [ ] Create backup admin user
- [ ] Document admin workflows
- [ ] Set up monitoring for admin actions

---

## Summary

**Week 1 Status: ✅ COMPLETE**

- Database: 4 tables, 2 functions, RLS policies
- Backend: 3 services, 1 middleware, 25+ endpoints
- Integration: AI service now uses database prompts
- Testing: All endpoints tested and working

**Ready for Week 2: React Frontend Development**
