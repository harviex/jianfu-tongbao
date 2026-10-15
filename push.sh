#!/bin/bash
# Safe push script for jianfu-tongbao
# Usage: ./push.sh "commit message"

set -e

cd /home/c1/jianfu-tongbao

# 1. Check git status
echo "=== Git Status ==="
git status --short

# 2. Check for data/inbox/ in tracked files
if git ls-files --error-unmatch data/inbox/ >/dev/null 2>&1; then
    echo "ERROR: data/inbox/ is tracked! Run: git rm -r --cached data/inbox/"
    exit 1
fi

# 3. Check .gitignore
if ! grep -q "data/inbox/" .gitignore 2>/dev/null; then
    echo "WARNING: Adding data/inbox/ to .gitignore"
    echo "data/inbox/" >> .gitignore
    git add .gitignore
fi

# 4. Check .git size
GIT_SIZE=$(du -sm .git/ 2>/dev/null | awk '{print $1}')
echo ".git size: ${GIT_SIZE}MB"

if [ "$GIT_SIZE" -gt 500 ]; then
    echo "=== REPO TOO LARGE — Using shallow-clone method ==="
    
    # Save modified files
    FILES=$(git diff --name-only HEAD 2>/dev/null; git ls-files --others --exclude-standard 2>/dev/null)
    
    if [ -z "$FILES" ]; then
        echo "No files to push"
        exit 0
    fi
    
    echo "Files to push:"
    echo "$FILES"
    
    # Get token
    TOKEN=$(git remote get-url origin | sed 's|.*://harviex:||' | sed 's|@github.com.*||')
    
    # Clone shallow
    rm -rf /tmp/repo-clean
    git clone --depth 1 "https://***@github.com/harviex/jianfu-tongbao.git" /tmp/repo-clean
    
    # Copy modified files
    echo "$FILES" | while read f; do
        if [ -f "$f" ]; then
            cp "$f" "/tmp/repo-clean/$f"
        fi
    done
    
    # Commit and push
    cd /tmp/repo-clean
    git add -A
    git commit -m "${1:-fix: update files}"
    git push origin main
    
    echo "=== Push complete ==="
    echo "NOTE: Local repo still has bloated .git"
    echo "To fix: rm -rf .git && git clone --depth 1 https://TOKEN@github.com/harviex/jianfu-tongbao.git ."
else
    # Small repo — use Contents API for single file, or git push for multiple
    NUM_FILES=$(git diff --name-only HEAD 2>/dev/null | wc -l)
    
    if [ "$NUM_FILES" -eq 1 ] && [ "$(git diff --name-only HEAD | head -1)" = "clues.html" ]; then
        echo "=== Single file (clues.html) — Using GitHub Contents API ==="
        
        TOKEN=$(git remote get-url origin | sed 's|.*://harviex:||' | sed 's|@github.com.*||')
        FILE="clues.html"
        SHA=$(curl -s "https://api.github.com/repos/harviex/jianfu-tongbao/contents/$FILE" \
          -H "Authorization: token $TOKEN" | python3 -c "import sys,json;print(json.load(sys.stdin)['sha'])")
        
        curl -s -X PUT "https://api.github.com/repos/harviex/jianfu-tongbao/contents/$FILE" \
          -H "Authorization: token $TOKEN" \
          -H "Content-Type: application/json" \
          -d "{\"message\":\"${1:-fix: update}\",\"content\":\"$(base64 -w0 $FILE)\",\"sha\":\"$SHA\"}" \
          | python3 -c "import sys,json;d=json.load(sys.stdin);print('Pushed:',d.get('content',{}).get('sha','')[:12])"
    else
        echo "=== Multiple files — Using git push ==="
        git add -A
        git commit -m "${1:-fix: update files}"
        git push origin main
    fi
fi
