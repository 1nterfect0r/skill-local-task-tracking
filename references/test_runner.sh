#!/usr/bin/env bash
set -u
ROOT=/tmp/tt-root
baseDir=/home/hanneskuhl/.openclaw/skills/task-tracking
LOG_DIR=/home/hanneskuhl/.openclaw/workspace/tmp
STAMP=$(date -u +"%Y-%m-%dT%H%M%SZ")
LOG="$LOG_DIR/tt-test-$STAMP.log"
mkdir -p "$LOG_DIR"
rm -rf "$ROOT"
export TASK_TRACKING_ROOT="$ROOT"

pass=0
fail=0
log(){ echo "$1" | tee -a "$LOG"; }
run_ok(){ desc="$1"; shift; out=$("$@" 2>&1); code=$?; if [ $code -eq 0 ]; then log "PASS: $desc"; pass=$((pass+1)); else log "FAIL: $desc (exit $code) out=$out"; fail=$((fail+1)); fi; }
run_fail(){ desc="$1"; exp="$2"; shift 2; out=$("$@" 2>&1); code=$?; if [ $code -eq $exp ]; then log "PASS: $desc (exit $code)"; pass=$((pass+1)); else log "FAIL: $desc (exit $code, expected $exp) out=$out"; fail=$((fail+1)); fi; }
run_ok_cmd(){ desc="$1"; cmd="$2"; out=$(bash -lc "$cmd" 2>&1); code=$?; if [ $code -eq 0 ]; then log "PASS: $desc"; pass=$((pass+1)); else log "FAIL: $desc (exit $code) out=$out"; fail=$((fail+1)); fi; }
run_fail_cmd(){ desc="$1"; exp="$2"; cmd="$3"; out=$(bash -lc "$cmd" 2>&1); code=$?; if [ $code -eq $exp ]; then log "PASS: $desc (exit $code)"; pass=$((pass+1)); else log "FAIL: $desc (exit $code, expected $exp) out=$out"; fail=$((fail+1)); fi; }

log "== Core flow =="
run_ok "init-project" python3 "${baseDir}/scripts/task_tracking.py" init-project acme-s4 --statuses backlog,open,done
run_ok "add default backlog" python3 "${baseDir}/scripts/task_tracking.py" add acme-s4 --task-id fix_posting_logic
run_ok "add open with meta" python3 "${baseDir}/scripts/task_tracking.py" add acme-s4 --task-id adjust_tax_codes --status open --tags "sap,fi" --assignee hannes --priority P2 --body "Initial body"
run_fail "add duplicate task_id" 4 python3 "${baseDir}/scripts/task_tracking.py" add acme-s4 --task-id fix_posting_logic
run_ok "list default" python3 "${baseDir}/scripts/task_tracking.py" list acme-s4 --limit 100 --sort updated_at --desc
run_ok "show meta" python3 "${baseDir}/scripts/task_tracking.py" show acme-s4 adjust_tax_codes
run_ok_cmd "set-body" "python3 ${baseDir}/scripts/task_tracking.py set-body acme-s4 adjust_tax_codes --text $'L1\\nL2\\nL3\\nL4'"
run_ok "show body limits" python3 "${baseDir}/scripts/task_tracking.py" show acme-s4 adjust_tax_codes --body --max-body-lines 2 --max-body-chars 5
run_ok "move open->done" python3 "${baseDir}/scripts/task_tracking.py" move acme-s4 adjust_tax_codes done
run_ok "meta-update valid" python3 "${baseDir}/scripts/task_tracking.py" meta-update acme-s4 fix_posting_logic --patch-json '{"set":{"priority":"P1","assignee":"Hannes"},"unset":["due_date"]}'
run_ok "set-body text" python3 "${baseDir}/scripts/task_tracking.py" set-body acme-s4 fix_posting_logic --text "Hello"
run_ok "integrity-check clean" python3 "${baseDir}/scripts/task_tracking.py" integrity-check acme-s4

log "== Regression checks for fixes =="
run_fail "meta-update invalid patch set=[]" 2 python3 "${baseDir}/scripts/task_tracking.py" meta-update acme-s4 fix_posting_logic --patch-json '{"set":[],"unset":[]}'
run_fail "list limit >1000" 2 python3 "${baseDir}/scripts/task_tracking.py" list acme-s4 --limit 1001
run_fail "list fields title forbidden" 2 python3 "${baseDir}/scripts/task_tracking.py" list acme-s4 --fields title --limit 10

# corrupt due_date and verify list does not crash
python3 - <<'PY'
import json, os
path=os.path.join("/tmp/tt-root","acme-s4","backlog","index.json")
with open(path,"r",encoding="utf-8") as f: data=json.load(f)
data["fix_posting_logic"]["due_date"]="not-a-date"
with open(path,"w",encoding="utf-8") as f: json.dump(data,f)
PY
out=$(python3 "${baseDir}/scripts/task_tracking.py" list acme-s4 --sort due_date --asc --limit 10 2>&1); code=$?
if [ $code -ne 0 ]; then log "FAIL: list due_date invalid (exit $code) out=$out"; fail=$((fail+1));
else
  tmp=/tmp/tt-out.json
  echo "$out" > $tmp
  python3 - <<'PY'
import json
with open("/tmp/tt-out.json","r",encoding="utf-8") as f: obj=json.load(f)
if obj.get("ok") is True:
    raise SystemExit(0)
raise SystemExit(1)
PY
  if [ $? -eq 0 ]; then log "PASS: list due_date invalid treated as missing"; pass=$((pass+1)); else log "FAIL: list due_date invalid returned not ok"; fail=$((fail+1)); fi
fi

log "== Edge cases 18.x =="
run_fail "18.1 meta-update tags=null" 2 python3 "${baseDir}/scripts/task_tracking.py" meta-update acme-s4 fix_posting_logic --patch-json '{"set":{"tags":null},"unset":[]}'
run_fail "18.2 meta-update assignee non-string" 2 python3 "${baseDir}/scripts/task_tracking.py" meta-update acme-s4 fix_posting_logic --patch-json '{"set":{"assignee":123},"unset":[]}'
run_fail "18.3 meta-update due_date null" 2 python3 "${baseDir}/scripts/task_tracking.py" meta-update acme-s4 fix_posting_logic --patch-json '{"set":{"due_date":null},"unset":[]}'
run_fail "18.4 meta-update unset non-string" 2 python3 "${baseDir}/scripts/task_tracking.py" meta-update acme-s4 fix_posting_logic --patch-json '{"set":{},"unset":["due_date",123]}'
run_fail "18.5 meta-update priority null" 2 python3 "${baseDir}/scripts/task_tracking.py" meta-update acme-s4 fix_posting_logic --patch-json '{"set":{"priority":null},"unset":[]}'
run_fail "18.6 meta-update title non-string" 2 python3 "${baseDir}/scripts/task_tracking.py" meta-update acme-s4 fix_posting_logic --patch-json '{"set":{"title":123},"unset":[]}'
run_fail "18.6 meta-update title empty" 2 python3 "${baseDir}/scripts/task_tracking.py" meta-update acme-s4 fix_posting_logic --patch-json '{"set":{"title":""},"unset":[]}'

# 18.7 list auto-repairs non-object meta (preflight --fix)
python3 - <<'PY'
import json, os
path=os.path.join("/tmp/tt-root","acme-s4","backlog","index.json")
with open(path,"r",encoding="utf-8") as f: data=json.load(f)
data["bad-meta"]="oops"
with open(path,"w",encoding="utf-8") as f: json.dump(data,f)
PY
out=$(python3 "${baseDir}/scripts/task_tracking.py" list acme-s4 --limit 50 2>&1); code=$?
if [ $code -ne 0 ]; then log "FAIL: 18.7 list auto-repair non-object meta (exit $code) out=$out"; fail=$((fail+1));
else
  tmp=/tmp/tt-edge-out.json
  echo "$out" > $tmp
  python3 - <<'PY'
import json
with open("/tmp/tt-edge-out.json","r",encoding="utf-8") as f: obj=json.load(f)
items=obj.get("items",[])
for it in items:
    if it.get("task_id") == "bad-meta" and it.get("status") == "backlog":
        raise SystemExit(0)
raise SystemExit(1)
PY
  if [ $? -eq 0 ]; then log "PASS: 18.7 list auto-repairs non-object meta"; pass=$((pass+1)); else log "FAIL: 18.7 repaired task not found"; fail=$((fail+1)); fi
fi

# 18.8 integrity-check without index should not report orphan bodies
rm -f /tmp/tt-root/acme-s4/open/index.json
mkdir -p /tmp/tt-root/acme-s4/open
printf "x" > /tmp/tt-root/acme-s4/open/orphan1.md
printf "y" > /tmp/tt-root/acme-s4/open/orphan2.md
out=$(python3 "${baseDir}/scripts/task_tracking.py" integrity-check acme-s4 2>&1); code=$?
if [ $code -ne 0 ]; then log "FAIL: 18.8 integrity-check exit $code out=$out"; fail=$((fail+1));
else
  tmp=/tmp/tt-edge-out.json
  echo "$out" > $tmp
  python3 - <<'PY'
import json
with open("/tmp/tt-edge-out.json","r",encoding="utf-8") as f: obj=json.load(f)
issues=obj.get("issues",[])
# must contain INDEX_ERROR for open; must NOT contain ORPHAN_BODY for open
has_index=False
has_orphan=False
for it in issues:
    if it.get("type") == "INDEX_ERROR" and it.get("status") == "open":
        has_index=True
    if it.get("type") == "ORPHAN_BODY" and it.get("status") == "open":
        has_orphan=True
if has_index and not has_orphan and obj.get("ok") is False:
    raise SystemExit(0)
raise SystemExit(1)
PY
  if [ $? -eq 0 ]; then log "PASS: 18.8 no orphan flood when index missing"; pass=$((pass+1)); else log "FAIL: 18.8 orphan flood detected"; fail=$((fail+1)); fi
fi

run_fail "18.9 TASK_TRACKING_ROOT rejects '..'" 2 env TASK_TRACKING_ROOT=../escape python3 "${baseDir}/scripts/task_tracking.py" list acme-s4 --limit 1

log "RESULTS pass=$pass fail=$fail"
log "LOGFILE: $LOG"
exit 0
