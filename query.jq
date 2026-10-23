  .[0].boot_time[$ARGS.named.boot | tonumber].boot_logs as $logs |
  (first($logs | to_entries[] |
    select(.value.name | contains("Starting qm.service")) ) | .key) // ($logs | length) as $start |
  (first($logs | to_entries[] |
    select((.value.name | contains("Failed to start qm.service.")) or (.value.name | contains("Started qm.service.")) ) | .key) // ($logs | length)
  ) as $end |
  $logs[$start - 5:$end + 5]