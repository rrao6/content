# How to Restart the Dashboard After Fix

## 🔄 Quick Restart

```bash
cd /Users/fchen/Code/content/red-zone-dashboard
pkill -f "python3.*dashboard.py" 2>/dev/null || true
python3 dashboard.py
```

## 📋 Step-by-Step Instructions

### 1. Stop Any Running Dashboard Instances

```bash
# Find the process
ps aux | grep "dashboard.py"

# Kill it (if running)
pkill -f "python3.*dashboard.py"
```

### 2. Navigate to Dashboard Directory

```bash
cd /Users/fchen/Code/content/red-zone-dashboard
```

### 3. Start the Dashboard

```bash
python3 dashboard.py
```

You should see output like:
```
 * Serving Flask app 'dashboard'
 * Debug mode: on
WARNING: This is a development server. Do not use it in a production deployment.
 * Running on http://127.0.0.1:5000
```

### 4. Verify the Fix

**Open your browser to:** http://localhost:5000

**Test these URLs:**
1. Main dashboard: http://localhost:5000/
2. Run 16 results: http://localhost:5000/results?run_id=16
3. A specific poster: http://localhost:5000/poster/100000031

**What to check:**
- ✅ Original poster images should now display (not just placeholders)
- ✅ Composite images should still work
- ✅ Toggle between original/composite views should work
- ✅ No 404 errors in browser console

---

## 🎯 Quick Test

Open the results page and look for these specific posters (they should all show images now):

- **Glory** (ID: 100003413)
- **Rocky** (ID: 100000031)
- **Moonlight** (ID: 100000045)

If you see the actual movie posters (not placeholders), the fix is working! ✅

---

## 🐛 Troubleshooting

### Issue: Still seeing placeholders

**Solution:** Hard refresh your browser to clear cache
- **Chrome/Firefox:** `Ctrl+Shift+R` (Windows) or `Cmd+Shift+R` (Mac)
- **Safari:** `Cmd+Option+R`

### Issue: Dashboard won't start

**Check if port 5000 is in use:**
```bash
lsof -i :5000
```

**Kill the process if needed:**
```bash
kill -9 <PID>
```

### Issue: Import errors

**Make sure you're in the right directory:**
```bash
pwd
# Should show: /Users/fchen/Code/content/red-zone-dashboard
```

**Verify parent directory is accessible:**
```bash
ls ../*.py
# Should list files like ../main.py, ../analysis.py, etc.
```

---

## 📞 Need Help?

Check these documentation files:
- `IMAGE_PROXY_FIX.md` - Details about the fix
- `QUICK_START.md` - Dashboard usage guide
- `README.md` - Full dashboard documentation

