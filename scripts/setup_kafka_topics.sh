#!/usr/bin/env bash
# Create AMR Sentinel Kafka topics.
# Run once after docker compose up.

set -euo pipefail

KAFKA_BOOTSTRAP="${KAFKA_BOOTSTRAP:-localhost:29092}"
KAFKA_CONTAINER="${KAFKA_CONTAINER:-amr_kafka}"

# topic:partitions:replication
topics=(
    "isolates.raw:3:1"
    "isolates.validated:6:1"
    "isolates.classified:6:1"
    "isolates.genomic:3:1"
    "alerts.cusum:3:1"
    "alerts.cluster:3:1"
    "predictions.resistance:3:1"
    "stewardship.recommendations:3:1"
    "dlq.validation_failures:1:1"
)

create_topic() {
    local topic="$1" partitions="$2" replication="$3"

    if command -v kafka-topics >/dev/null 2>&1; then
        kafka-topics --create \
            --bootstrap-server "$KAFKA_BOOTSTRAP" \
            --topic "$topic" \
            --partitions "$partitions" \
            --replication-factor "$replication" \
            --if-not-exists
    else
        # Fall back to running inside the kafka container
        docker exec "$KAFKA_CONTAINER" kafka-topics --create \
            --bootstrap-server kafka:9092 \
            --topic "$topic" \
            --partitions "$partitions" \
            --replication-factor "$replication" \
            --if-not-exists
    fi
}

for topic_config in "${topics[@]}"; do
    IFS=':' read -r topic partitions replication <<< "$topic_config"
    create_topic "$topic" "$partitions" "$replication"
    echo "Created topic: $topic (partitions=$partitions, replication=$replication)"
done

echo "All Kafka topics created."
