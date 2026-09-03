#!/usr/bin/env python3
"""Fix mojibake encoding in Python files."""

def fix_file(filepath):
    """Fix a single file's mojibake issues."""
    # Read the file
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    
    original_length = len(content)
    
    # Define replacements using unicode escapes to avoid corruption
    replacements = {
        # Decorative comments (box drawing characters)
        '# \u00c3\u00a2\u00e2\u0080\u009a\u00c2\u00ac\u00c3\u00a2\u00e2\u0080\u009a\u00c2\u00ac Root endpoint \u00c3\u00a2\u00e2\u0080\u009a\u00c2\u00ac\u00c3\u00a2\u00e2\u0080\u009a\u00c2\u00ac': '# \u2500\u2500 Root endpoint \u2500\u2500',
        '# \u00c3\u00a2\u00e2\u0080\u009a\u00c2\u00ac\u00c3\u00a2\u00e2\u0080\u009a\u00c2\u00ac Health check \u00c3\u00a2\u00e2\u0080\u009a\u00c2\u00ac\u00c3\u00a2\u00e2\u0080\u009a\u00c2\u00ac': '# \u2500\u2500 Health check \u2500\u2500',
        '# \u00c3\u00a2\u00e2\u0080\u009a\u00c2\u00ac\u00c3\u00a2\u00e2\u0080\u009a\u00c2\u00ac Register API Routers \u00c3\u00a2\u00e2\u0080\u009a\u00c2\u00ac\u00c3\u00a2\u00e2\u0080\u009a\u00c2\u00ac': '# \u2500\u2500 Register API Routers \u2500\u2500',
        '# \u00c3\u00a2\u00e2\u0080\u009a\u00c2\u00ac\u00c3\u00a2\u00e2\u0080\u009a\u00c2\u00ac New Features \u00c3\u00a2\u00e2\u0080\u009a\u00c2\u00ac\u00c3\u00a2\u00e2\u0080\u009a\u00c2\u00ac': '# \u2500\u2500 New Features \u2500\u2500',
        # Emojis (checkmark, file, speech, chart, siren, red circle, clipboard)
        '\u00c3\u00a2\u00c5\u201c\u00c5\u00a0': '\u2705',  # checkmark
        '\u00c3\u00b0\u00c5\u0178\u00e2\u0080\u0098\u00c4': '\U0001f4c4',  # file
        '\u00c3\u00b0\u00c5\u0178\u00e2\u20ac\u2122\u00c2\u00ac': '\U0001f4ac',  # speech
        '\u00c3\u00b0\u00c5\u0178\u00e2\u0080\u0098\u00c5\u00a0': '\U0001f4ca',  # chart
        '\u00c3\u00b0\u00c5\u0178\u00c5\u00a1\u00c2\u00a8': '\U0001f6a8',  # siren
        '\u00c3\u00b0\u00c5\u0178\u00e2\u0080\u0098\u00c2\u00b4': '\U0001f534',  # red circle
        '\u00c3\u00b0\u00c5\u0178\u00e2\u0080\u0098\u00c5\u00be': '\U0001f4cb',  # clipboard
        # Bullet point
        '\u00c3\u00a2\u00e2\u0082\u00ac\u00c2\u00a2': '\u2022',
    }
    
    changes = 0
    # Apply replacements
    for old, new in replacements.items():
        count = content.count(old)
        if count > 0:
            content = content.replace(old, new)
            changes += count
            print(f"  \u2705 Replaced {count}x: {old[:15]}... \u2192 {new}")
    
    if changes > 0:
        # Write back
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"\u2705 Fixed {changes} instances in: {filepath}")
    else:
        print(f"\u2139 No changes needed: {filepath}")
    
    return changes


if __name__ == '__main__':
    import os
    
    files = [
        r'm:\Samanvaya\backend\main.py',
        r'm:\Samanvaya\backend\domain\services\webhook_event_processor.py',
        r'm:\Samanvaya\backend\domain\services\enhanced_notification_service.py',
    ]
    
    total_changes = 0
    for filepath in files:
        print(f"\n\U0001f4c4 Processing: {os.path.basename(filepath)}")
        if os.path.exists(filepath):
            try:
                changes = fix_file(filepath)
                total_changes += changes
            except Exception as e:
                print(f"  \u274c Error: {e}")
        else:
            print(f"  \u274c File not found")
    
    print(f"\n\u2705 Complete! Fixed {total_changes} corrupted characters across {len(files)} files.")
