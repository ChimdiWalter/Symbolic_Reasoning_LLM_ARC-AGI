#!/usr/bin/env bash
# Item-2 v1.6: resume the frozen prospective run after an Athe reboot, doing
# exactly what RESUME.md and logs/v16_run_state.txt prescribe, and nothing else.
#
#   1. refuse if a writer or runner is already alive, or if the run has ended
#      (V16_POSTGEN_DONE / V16_POSTGEN_BLOCKED);
#   2. audit the saved corpus: contiguous slots, parseable records, freeze_ok
#      on every record, no stale partial files, no engine state files;
#   3. relaunch the SAME frozen generation script (it resumes at the first
#      missing slot; the wall cap counts from the recorded first start);
#   4. relaunch the post-generation runner on the NEW chain PID.
#
# Never a second writer (the generator's flock refuses one anyway), never
# pkill, never kill. Every decision is logged. `--check` audits and reports
# without launching anything.
set -u
cd "$(dirname "$0")/.." || exit 1
CHECK=0; [ "${1:-}" = "--check" ] && CHECK=1
D=logs/v16_autoresume
mkdir -p "$D"
LOG=$D/autoresume.log
say() { echo "$(date -u +%FT%TZ) $*" | tee -a "$LOG"; }
stop() { say "STOP: $*"; exit "${2:-0}"; }
C=outputs/tti/v16_test_corpus

say "autoresume start check=$CHECK boot=$(cat /proc/sys/kernel/random/boot_id) uptime=$(cut -d' ' -f1 /proc/uptime)s"
[ -e logs/V16_POSTGEN_DONE ] && stop "V16_POSTGEN_DONE exists; the run is complete; nothing to do"
[ -e logs/V16_POSTGEN_BLOCKED ] && stop "V16_POSTGEN_BLOCKED exists; a frozen blocker needs a person; nothing launched"

writer=$(ps -eo pid,args | awk '$2 ~ /python$/ && $3=="scripts/generate_v16_pairs.py" && $4=="full" {print $1}')
chain=$(ps -eo pid,args | awk '$2=="bash" && $3=="scripts/run_v16_generation.sh" {print $1}')
runner=$(ps -eo pid,args | awk '$2=="bash" && $3=="scripts/run_v16_post_generation.sh" {print $1}')
[ -n "$writer$chain" ] && stop "a generation writer is alive (chain [$chain] generator [$writer]); never a second writer"
if [ -n "$runner" ]; then
  [ -f logs/V16_GENERATION_DONE ] && stop "generation done and the runner [$runner] is alive; nothing to do"
  stop "a runner [$runner] is alive without a chain; leaving it for a person" 2
fi
[ -d "$C" ] || stop "no corpus directory; the run was never launched here" 2

#  --- audit ------------------------------------------------------------------
problems=0
for t in "$C"/full[0-9][0-9][0-9][0-9][0-9].json.tmp; do
  [ -e "$t" ] || continue
  final=${t%.tmp}
  if [ -e "$final" ]; then say "AUDIT: stale partial $t next to a final record; refusing"; problems=$((problems+1))
  elif [ "$CHECK" = 0 ]; then rm -f "$t"; say "AUDIT: removed partial $t (its slot will be recomputed)"
  else say "AUDIT: partial $t would be removed"; fi
done
for t in "$C"/*.tmp; do [ -e "$t" ] && { say "AUDIT: other partial file $t; refusing"; problems=$((problems+1)); }; done
for f in outputs/tti/v16_engine/library.json outputs/tti/v16_engine/learned_verbs.json; do
  [ -e "$f" ] && { say "AUDIT: engine state file $f present; refusing"; problems=$((problems+1)); }
done
audit=$(PYTHONDONTWRITEBYTECODE=1 python3 - "$C" <<'EOF'
import json, os, re, sys
d = sys.argv[1]
names = sorted(n for n in os.listdir(d) if re.match(r"^full\d{5}\.json$", n))
slots, bad, freeze_bad, groups, seen = [], [], 0, 0, set()
for n in names:
    try:
        r = json.load(open(os.path.join(d, n)))
    except Exception as e:
        bad.append(n); continue
    slots.append(r["slot"])
    if r.get("freeze_ok") is not True: freeze_bad += 1
    if r.get("admitted") and r["group"]["group_digest"] not in seen:
        seen.add(r["group"]["group_digest"]); groups += 1
contig = slots == list(range(len(slots)))
end = os.path.exists(os.path.join(d, "full_run_end.json"))
state = json.load(open(os.path.join(d, "full_run_state.json")))["first_started_utc"] if os.path.exists(os.path.join(d, "full_run_state.json")) else "MISSING"
print(json.dumps({"records": len(names), "contiguous": contig, "unparseable": bad[:5], "freeze_not_ok": freeze_bad,
                  "groups": groups, "run_end_exists": end, "first_start": state}))
EOF
)
say "AUDIT: $audit"
echo "$audit" | grep -q '"contiguous": true' || { say "AUDIT: slots not contiguous; refusing"; problems=$((problems+1)); }
echo "$audit" | grep -q '"unparseable": \[\]' || { say "AUDIT: unparseable record; refusing"; problems=$((problems+1)); }
echo "$audit" | grep -q '"freeze_not_ok": 0' || { say "AUDIT: a record failed its freeze check; the generator stopped itself; refusing"; problems=$((problems+1)); }
echo "$audit" | grep -q '"first_start": "MISSING"' && { say "AUDIT: run state missing; refusing"; problems=$((problems+1)); }
[ "$problems" -gt 0 ] && stop "$problems audit problem(s); nothing launched; a person must look" 2
[ "$CHECK" = 1 ] && stop "check only; the run could be resumed from here"

#  --- relaunch ---------------------------------------------------------------
say "relaunching the frozen generator (resumes at the first missing slot; cap from the recorded first start)"
setsid nohup scripts/run_v16_generation.sh >> logs/v16_generation_stdout.log 2>&1 < /dev/null &
sleep 20
chain=$(ps -eo pid,args | awk '$2=="bash" && $3=="scripts/run_v16_generation.sh" {print $1}')
writer=$(ps -eo pid,args | awk '$2 ~ /python$/ && $3=="scripts/generate_v16_pairs.py" && $4=="full" {print $1}')
if [ -z "$chain" ]; then
  #  a generator that found the target already reached, or the cap expired, exits within seconds
  if [ -f logs/V16_GENERATION_DONE ]; then
    say "generator exited at once with the DONE marker (target reached or cap expired); starting the runner on a short chain"
    setsid nohup scripts/run_v16_generation.sh >> logs/v16_generation_stdout.log 2>&1 < /dev/null &
    sleep 2
    chain=$(ps -eo pid,args | awk '$2=="bash" && $3=="scripts/run_v16_generation.sh" {print $1}')
  fi
  [ -z "$chain" ] && stop "no chain after relaunch; see logs/v16_chain.log and logs/v16_generation_stdout.log" 2
fi
say "chain PID $chain generator PID [${writer:-exited}]"
mkdir -p logs/v16_postgen
setsid nohup bash scripts/run_v16_post_generation.sh "$chain" >> logs/v16_postgen/runner.out 2>&1 < /dev/null &
sleep 3
runner=$(ps -eo pid,args | awk -v c="$chain" '$2=="bash" && $3=="scripts/run_v16_post_generation.sh" && $4==c {print $1}')
say "runner PID [${runner:-not running; see logs/v16_postgen/runner.out}]"
{
  echo
  echo "$(date -u +%FT%TZ) AUTORESUME after reboot (boot $(cat /proc/sys/kernel/random/boot_id)): chain PID $chain, generator PID ${writer:-exited at once}, runner PID ${runner:-none}. Audit: $audit"
} >> logs/v16_run_state.txt
say "autoresume done"
