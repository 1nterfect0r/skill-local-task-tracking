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
out=$(python3 "${baseDir}/scripts/task_tracking.py" list acme-s4 --limit 1 --offset 0 2>&1); code=$?
if [ $code -ne 0 ]; then log "FAIL: list pagination count/count_total (exit $code) out=$out"; fail=$((fail+1));
else
  echo "$out" > /tmp/tt-count.json
  python3 - <<'PY'
import json
with open('/tmp/tt-count.json','r',encoding='utf-8') as f: obj=json.load(f)
if obj.get('ok') is True and obj.get('count') == 1 and isinstance(obj.get('count_total'), int) and obj.get('count_total') >= 2:
    raise SystemExit(0)
raise SystemExit(1)
PY
  if [ $? -eq 0 ]; then log "PASS: list returns count + count_total semantics"; pass=$((pass+1)); else log "FAIL: list count/count_total semantics invalid"; fail=$((fail+1)); fi
fi
run_ok "show meta" python3 "${baseDir}/scripts/task_tracking.py" show acme-s4 adjust_tax_codes
run_ok_cmd "set-body" "python3 ${baseDir}/scripts/task_tracking.py set-body acme-s4 adjust_tax_codes --text $'L1\\nL2\\nL3\\nL4'"
run_ok "show body limits" python3 "${baseDir}/scripts/task_tracking.py" show acme-s4 adjust_tax_codes --body --max-body-lines 2 --max-body-chars 5
run_ok "move open->done" python3 "${baseDir}/scripts/task_tracking.py" move acme-s4 adjust_tax_codes done
run_ok "meta-update valid" python3 "${baseDir}/scripts/task_tracking.py" meta-update acme-s4 fix_posting_logic --patch-json '{"set":{"priority":"P1","assignee":"hannes"},"unset":["due_date"]}'
run_ok "set-body text" python3 "${baseDir}/scripts/task_tracking.py" set-body acme-s4 fix_posting_logic --text "Hello"
run_ok "integrity-check clean" python3 "${baseDir}/scripts/task_tracking.py" integrity-check acme-s4

log "== Regression checks for fixes =="
run_fail "meta-update invalid patch set=[]" 2 python3 "${baseDir}/scripts/task_tracking.py" meta-update acme-s4 fix_posting_logic --patch-json '{"set":[],"unset":[]}'
run_fail "list limit >1000" 2 python3 "${baseDir}/scripts/task_tracking.py" list acme-s4 --limit 1001
run_fail "list fields title forbidden" 2 python3 "${baseDir}/scripts/task_tracking.py" list acme-s4 --fields title --limit 10
run_fail "list invalid filter-mode" 2 python3 "${baseDir}/scripts/task_tracking.py" list acme-s4 --filter-mode xor --limit 10

# filter-mode semantics: and vs or, and default=and
out_and=$(python3 "${baseDir}/scripts/task_tracking.py" list acme-s4 --tag sap --assignee hannes --filter-mode and --limit 100 2>&1); code=$?
if [ $code -ne 0 ]; then log "FAIL: filter-mode and (exit $code) out=$out_and"; fail=$((fail+1));
else
  echo "$out_and" > /tmp/tt-filter-and.json
  python3 - <<'PY'
import json
with open('/tmp/tt-filter-and.json','r',encoding='utf-8') as f: obj=json.load(f)
if obj.get('ok') is True and obj.get('count') == 1:
    raise SystemExit(0)
raise SystemExit(1)
PY
  if [ $? -eq 0 ]; then log "PASS: filter-mode and count=1"; pass=$((pass+1)); else log "FAIL: filter-mode and unexpected count"; fail=$((fail+1)); fi
fi

out_or=$(python3 "${baseDir}/scripts/task_tracking.py" list acme-s4 --tag sap --assignee hannes --filter-mode or --limit 100 2>&1); code=$?
if [ $code -ne 0 ]; then log "FAIL: filter-mode or (exit $code) out=$out_or"; fail=$((fail+1));
else
  echo "$out_or" > /tmp/tt-filter-or.json
  python3 - <<'PY'
import json
with open('/tmp/tt-filter-or.json','r',encoding='utf-8') as f: obj=json.load(f)
if obj.get('ok') is True and obj.get('count') == 2:
    raise SystemExit(0)
raise SystemExit(1)
PY
  if [ $? -eq 0 ]; then log "PASS: filter-mode or count=2"; pass=$((pass+1)); else log "FAIL: filter-mode or unexpected count"; fail=$((fail+1)); fi
fi

out_default=$(python3 "${baseDir}/scripts/task_tracking.py" list acme-s4 --tag sap --assignee hannes --limit 100 2>&1); code=$?
if [ $code -ne 0 ]; then log "FAIL: filter-mode default (exit $code) out=$out_default"; fail=$((fail+1));
else
  echo "$out_default" > /tmp/tt-filter-default.json
  python3 - <<'PY'
import json
with open('/tmp/tt-filter-default.json','r',encoding='utf-8') as f: obj=json.load(f)
if obj.get('ok') is True and obj.get('count') == 1:
    raise SystemExit(0)
raise SystemExit(1)
PY
  if [ $? -eq 0 ]; then log "PASS: filter-mode default behaves as and"; pass=$((pass+1)); else log "FAIL: filter-mode default unexpected count"; fail=$((fail+1)); fi
fi

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

# corrupt due_date type (non-string) and verify list still does not crash
python3 - <<'PY'
import json, os
path=os.path.join("/tmp/tt-root","acme-s4","backlog","index.json")
with open(path,"r",encoding="utf-8") as f: data=json.load(f)
data["fix_posting_logic"]["due_date"]=12345
with open(path,"w",encoding="utf-8") as f: json.dump(data,f)
PY
out=$(python3 "${baseDir}/scripts/task_tracking.py" list acme-s4 --sort due_date --asc --limit 10 2>&1); code=$?
if [ $code -ne 0 ]; then log "FAIL: list due_date non-string (exit $code) out=$out"; fail=$((fail+1));
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
  if [ $? -eq 0 ]; then log "PASS: list due_date non-string treated as missing"; pass=$((pass+1)); else log "FAIL: list due_date non-string returned not ok"; fail=$((fail+1)); fi
fi

# corrupt tags type (non-list) and verify filter-mode behavior remains stable
python3 - <<'PY'
import json, os
path=os.path.join("/tmp/tt-root","acme-s4","done","index.json")
with open(path,"r",encoding="utf-8") as f: data=json.load(f)
data["adjust_tax_codes"]["tags"]=123
with open(path,"w",encoding="utf-8") as f: json.dump(data,f)
PY

out=$(python3 "${baseDir}/scripts/task_tracking.py" list acme-s4 --tag sap --assignee hannes --filter-mode or --limit 100 2>&1); code=$?
if [ $code -ne 0 ]; then log "FAIL: list malformed tags with OR (exit $code) out=$out"; fail=$((fail+1));
else
  tmp=/tmp/tt-tags-or.json
  echo "$out" > $tmp
  python3 - <<'PY'
import json
with open('/tmp/tt-tags-or.json','r',encoding='utf-8') as f: obj=json.load(f)
if obj.get('ok') is True and obj.get('count') == 2:
    raise SystemExit(0)
raise SystemExit(1)
PY
  if [ $? -eq 0 ]; then log "PASS: list malformed tags with OR stays functional"; pass=$((pass+1)); else log "FAIL: list malformed tags with OR unexpected count"; fail=$((fail+1)); fi
fi

out=$(python3 "${baseDir}/scripts/task_tracking.py" list acme-s4 --tag sap --filter-mode and --limit 100 2>&1); code=$?
if [ $code -ne 0 ]; then log "FAIL: list malformed tags with AND (exit $code) out=$out"; fail=$((fail+1));
else
  tmp=/tmp/tt-tags-and.json
  echo "$out" > $tmp
  python3 - <<'PY'
import json
with open('/tmp/tt-tags-and.json','r',encoding='utf-8') as f: obj=json.load(f)
if obj.get('ok') is True and obj.get('count') == 0:
    raise SystemExit(0)
raise SystemExit(1)
PY
  if [ $? -eq 0 ]; then log "PASS: list malformed tags with AND stays functional"; pass=$((pass+1)); else log "FAIL: list malformed tags with AND unexpected count"; fail=$((fail+1)); fi
fi

log "== Edge cases 18.x =="
run_fail "18.1 meta-update tags=null" 2 python3 "${baseDir}/scripts/task_tracking.py" meta-update acme-s4 fix_posting_logic --patch-json '{"set":{"tags":null},"unset":[]}'
run_fail "18.2 meta-update assignee non-string" 2 python3 "${baseDir}/scripts/task_tracking.py" meta-update acme-s4 fix_posting_logic --patch-json '{"set":{"assignee":123},"unset":[]}'
run_fail "18.3 meta-update due_date null" 2 python3 "${baseDir}/scripts/task_tracking.py" meta-update acme-s4 fix_posting_logic --patch-json '{"set":{"due_date":null},"unset":[]}'
run_fail "18.4 meta-update unset non-string" 2 python3 "${baseDir}/scripts/task_tracking.py" meta-update acme-s4 fix_posting_logic --patch-json '{"set":{},"unset":["due_date",123]}'
run_fail "18.5 meta-update priority null" 2 python3 "${baseDir}/scripts/task_tracking.py" meta-update acme-s4 fix_posting_logic --patch-json '{"set":{"priority":null},"unset":[]}'
run_fail "18.6 meta-update title non-string" 2 python3 "${baseDir}/scripts/task_tracking.py" meta-update acme-s4 fix_posting_logic --patch-json '{"set":{"title":123},"unset":[]}'
run_fail "18.6 meta-update title empty" 2 python3 "${baseDir}/scripts/task_tracking.py" meta-update acme-s4 fix_posting_logic --patch-json '{"set":{"title":""},"unset":[]}'

# integrity-check type hardening: normalize malformed known fields
python3 - <<'PY'
import json, os
path=os.path.join('/tmp/tt-root','acme-s4','done','index.json')
with open(path,'r',encoding='utf-8') as f: data=json.load(f)
m=data['adjust_tax_codes']
m['tags']='oops'
m['assignee']=123
m['priority']='PX'
m['due_date']=12345
m['created_at']=999
m['updated_at']={'bad': True}
with open(path,'w',encoding='utf-8') as f: json.dump(data,f)
PY
out=$(python3 "${baseDir}/scripts/task_tracking.py" integrity-check acme-s4 --fix 2>&1); code=$?
if [ $code -ne 0 ]; then log "FAIL: integrity-check type hardening --fix (exit $code) out=$out"; fail=$((fail+1));
else
  echo "$out" > /tmp/tt-fix.json
  python3 - <<'PY'
import json
with open('/tmp/tt-fix.json','r',encoding='utf-8') as f: obj=json.load(f)
fixed_types={x.get('type') for x in obj.get('fixed',[])}
need={'TAGS_NORMALIZED','ASSIGNEE_REMOVED','PRIORITY_REMOVED','DUE_DATE_REMOVED','FIELD_TYPE_FIXED'}
if obj.get('ok') is True and need.issubset(fixed_types):
    raise SystemExit(0)
raise SystemExit(1)
PY
  if [ $? -eq 0 ]; then log "PASS: integrity-check type hardening reports fixes"; pass=$((pass+1)); else log "FAIL: integrity-check type hardening fixed-set mismatch"; fail=$((fail+1)); fi
fi
python3 - <<'PY'
import json, os
path=os.path.join('/tmp/tt-root','acme-s4','done','index.json')
with open(path,'r',encoding='utf-8') as f: data=json.load(f)
m=data['adjust_tax_codes']
ok=(isinstance(m.get('created_at'),str)
    and isinstance(m.get('updated_at'),str)
    and isinstance(m.get('tags'),list)
    and 'assignee' not in m
    and 'priority' not in m
    and 'due_date' not in m)
raise SystemExit(0 if ok else 1)
PY
if [ $? -eq 0 ]; then log "PASS: integrity-check type hardening normalized metadata"; pass=$((pass+1)); else log "FAIL: integrity-check type hardening normalization mismatch"; fail=$((fail+1)); fi

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
