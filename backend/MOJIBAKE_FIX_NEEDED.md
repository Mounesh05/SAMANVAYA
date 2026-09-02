# Mojibake Encoding Fix Required

## Issue
Three files contain corrupted unicode characters (mojibake) from improper UTF-8 encoding.

This is a **cosmetic issue only** - characters are inside strings/comments, not in code logic. The application runs correctly, but the display text is corrupted.

## Files Affected

### 1. backend/main.py
**Line 33:**
```python
"""Application lifespan Ã¢â‚¬â€ startup and shutdown events."""
```
**Should be:**
```python
"""Application lifespan — startup and shutdown events."""
```

**Line 167:**
```python
"message": "Samanvaya API v1.0 Ã¢â‚¬â€ AI-powered engineering intelligence platform",
```
**Should be:**
```python
"message": "Samanvaya API v1.0 — AI-powered engineering intelligence platform",
```

### 2. backend/domain/services/webhook_event_processor.py
**Lines 460-462:**
```python
state_labels = {
    "approved": "âœ… approved",
    "changes_requested": "ðŸ"„ requested changes on",
    "commented": "ðŸ'¬ commented on",
}
```
**Should be:**
```python
state_labels = {
    "approved": "✅ approved",
    "changes_requested": "📄 requested changes on",
    "commented": "💬 commented on",
}
```

### 3. backend/domain/services/enhanced_notification_service.py
**Line 157:**
```python
"title": f"ðŸ"Š Your {frequency.value} digest ({len(notifications)} updates)",
```
**Should be:**
```python
"title": f"📊 Your {frequency.value} digest ({len(notifications)} updates)",
```

**Line 193:**
```python
lines.append(f"\nðŸš¨ URGENT ({len(by_priority['urgent'])}):")
```
**Should be:**
```python
lines.append(f"\n🚨 URGENT ({len(by_priority['urgent'])}):")
```

**Lines 195, 201, 207:**
```python
lines.append(f"  â€¢ {notif['rendered']['title']}")
```
**Should be:**
```python
lines.append(f"  • {notif['rendered']['title']}")
```

**Line 199:**
```python
lines.append(f"\nðŸ"´ HIGH PRIORITY ({len(by_priority['high'])}):")
```
**Should be:**
```python
lines.append(f"\n🔴 HIGH PRIORITY ({len(by_priority['high'])}):")
```

**Line 205:**
```python
lines.append(f"\nðŸ"‹ UPDATES ({len(by_priority['normal'])}):")
```
**Should be:**
```python
lines.append(f"\n📋 UPDATES ({len(by_priority['normal'])}):")
```

## Root Cause
Files were saved with incorrect encoding (likely Windows-1252 or similar) instead of UTF-8, causing multi-byte unicode characters (em-dash —, emojis 🚨📄💬 etc.) to be corrupted.

## Fix Instructions

### Manual Fix (Recommended)
1. Open each file in VS Code
2. Click on encoding in bottom-right status bar (currently shows "UTF-8")
3. Select "Save with Encoding"
4. Choose "UTF-8" (not "UTF-8 with BOM")
5. Manually replace the corrupted strings with correct characters using find-and-replace:
   - `Ã¢â‚¬â€` → `—` (em-dash)
   - `âœ…` → `✅`
   - `ðŸ"„` → `📄`
   - `ðŸ'¬` → `💬`
   - `ðŸ"Š` → `📊`
   - `ðŸš¨` → `🚨`
   - `ðŸ"´` → `🔴`
   - `ðŸ"‹` → `📋`
   - `â€¢` → `•` (bullet point)

### Automated Fix (if available)
```bash
# Install iconv if not available (Linux/Mac)
# Then run:
iconv -f UTF-8 -t UTF-8 -c backend/main.py -o backend/main.py.fixed
iconv -f UTF-8 -t UTF-8 -c backend/domain/services/webhook_event_processor.py -o backend/domain/services/webhook_event_processor.py.fixed
iconv -f UTF-8 -t UTF-8 -c backend/domain/services/enhanced_notification_service.py -o backend/domain/services/enhanced_notification_service.py.fixed

# On Windows with PowerShell:
# Use VS Code's "Save with Encoding" feature instead
```

## Impact
- **Severity:** Low (cosmetic only)
- **User-facing:** Yes (API response messages and notifications will show garbled text)
- **Functional:** No (application logic unaffected)
- **Production:** Should be fixed before deployment for professional appearance

## Status
- ✅ Issue documented
- ❌ Not fixed (string replacement in automation tool failed due to encoding issues)
- 🔧 Manual fix required by developer with proper text editor
