import os
import glob
import re

for file in glob.glob('templates/**/*.html', recursive=True):
    with open(file, 'r') as f:
        content = f.read()
    
    # Use a regex that finds form tags with method="POST" (case-insensitive)
    # and inserts the CSRF token right after the opening tag,
    # ONLY if it doesn't already have csrf_token
    
    def replacer(match):
        form_tag = match.group(1)
        # Skip if already has csrf token nearby (though we just check the whole file for safety, but regex is better)
        return form_tag + '\n    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>'

    # Find all forms with method="POST"
    new_content = re.sub(
        r'(<form[^>]*method=["\']POST["\'][^>]*>)(?!\s*<input type="hidden" name="csrf_token")',
        replacer,
        content,
        flags=re.IGNORECASE
    )
    
    if content != new_content:
        with open(file, 'w') as f:
            f.write(new_content)
        print(f"Updated {file}")

