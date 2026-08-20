LOGFILE="I:/Coding/visioret/model/checkpoints/train_full.log"
START_LINE_NUM=$(grep -n "smoke_test=False" "$LOGFILE" | tail -1 | cut -d: -f1)
START_TS=$(sed -n "${START_LINE_NUM}p" "$LOGFILE" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}')
START_EPOCH=$(date -d "$START_TS" +%s)
DEADLINE=$((START_EPOCH + 4*3600))
echo "Watching from line $START_LINE_NUM. Start=$START_TS Deadline_epoch=$DEADLINE"

while true; do
  if tail -n "+$START_LINE_NUM" "$LOGFILE" | grep -q "Run finished"; then
    echo "NATURAL_COMPLETION"
    exit 0
  fi
  NOW=$(date +%s)
  if [ "$NOW" -ge "$DEADLINE" ]; then
    echo "TIME_LIMIT_REACHED"
    exit 0
  fi
  sleep 60
done
