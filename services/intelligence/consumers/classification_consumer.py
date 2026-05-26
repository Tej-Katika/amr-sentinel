"""Classification consumer.

Consumes from `isolates.validated`, applies the breakpoint engine + AWaRe
classifier, writes the enriched event to TimescaleDB and re-publishes to
`isolates.classified`.

Run as: python -m intelligence.consumers.classification_consumer (PYTHONPATH=services)
"""
from __future__ import annotations

import json
import logging
import os
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg2

from ..breakpoints.aware import get_classifier as get_aware
from ..breakpoints.engine import BreakpointEngine
from ..db import database_url

log = logging.getLogger("classification-consumer")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

VALIDATED_TOPIC = "isolates.validated"
CLASSIFIED_TOPIC = "isolates.classified"
CONSUMER_GROUP = "intelligence-classification"

BREAKPOINT_CSV = Path(__file__).resolve().parents[3] / "data" / "breakpoints" / "eucast_seed.csv"


class ClassificationConsumer:
    def __init__(self) -> None:
        self.engine = BreakpointEngine()
        self.engine.load(str(BREAKPOINT_CSV))
        self.aware = get_aware()
        self.aware.load()
        self._running = True

    def _classify(self, event: dict) -> dict:
        result = self.engine.classify(
            organism_taxid=event["organism_taxid"],
            antibiotic_atc=event["antibiotic_atc"],
            method=event["measurement_type"],
            value=float(event["measurement_value"]),
            standard="EUCAST",
        )
        sir = result.sir if result else None
        bp_standard = result.standard if result else None
        bp_version = result.version if result else None
        aware = self.aware.lookup(event["antibiotic_atc"])

        return {
            **event,
            "sir_classification": sir,
            "breakpoint_standard": bp_standard,
            "breakpoint_version": bp_version,
            "aware_category": aware,
            "classified_at": datetime.utcnow().isoformat() + "Z",
        }

    def _persist(self, conn, event: dict) -> None:
        sql = """
            INSERT INTO isolate_events (
                event_id, facility_id, specimen_id, specimen_type,
                organism_taxid, organism_name, gram_stain,
                antibiotic_atc, antibiotic_name, drug_class,
                measurement_type, measurement_value, measurement_comparator,
                sir_classification, breakpoint_standard, breakpoint_version,
                aware_category,
                patient_age_group, patient_sex, ward_id, infection_origin,
                collection_date, ingested_at, classified_at, source_format
            ) VALUES (
                %(event_id)s, %(facility_id)s, %(specimen_id)s, %(specimen_type)s,
                %(organism_taxid)s, %(organism_name)s, %(gram_stain)s,
                %(antibiotic_atc)s, %(antibiotic_name)s, %(drug_class)s,
                %(measurement_type)s, %(measurement_value)s, %(measurement_comparator)s,
                %(sir_classification)s, %(breakpoint_standard)s, %(breakpoint_version)s,
                %(aware_category)s,
                %(patient_age_group)s, %(patient_sex)s, %(ward_id)s, %(infection_origin)s,
                %(collection_date)s, %(ingested_at)s, %(classified_at)s, %(source_format)s
            )
            ON CONFLICT (event_id, collection_date) DO NOTHING;
        """
        with conn.cursor() as cur:
            cur.execute(sql, event)
        conn.commit()

    def run(self) -> None:
        try:
            from confluent_kafka import Consumer, Producer  # type: ignore
        except ImportError:
            log.error("confluent-kafka not installed; cannot run consumer.")
            sys.exit(1)

        bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")
        consumer = Consumer({
            "bootstrap.servers": bootstrap,
            "group.id": CONSUMER_GROUP,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        })
        producer = Producer({"bootstrap.servers": bootstrap, "client.id": "classification"})
        consumer.subscribe([VALIDATED_TOPIC])

        signal.signal(signal.SIGTERM, lambda *_: self.stop())
        signal.signal(signal.SIGINT, lambda *_: self.stop())

        conn = psycopg2.connect(database_url())
        log.info("Classification consumer started. Topic=%s, group=%s", VALIDATED_TOPIC, CONSUMER_GROUP)

        try:
            while self._running:
                msg = consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    log.error("Consumer error: %s", msg.error())
                    continue
                try:
                    event = json.loads(msg.value())
                    classified = self._classify(event)
                    self._persist(conn, classified)
                    producer.produce(
                        CLASSIFIED_TOPIC,
                        key=classified["facility_id"].encode(),
                        value=json.dumps(classified).encode(),
                    )
                    producer.poll(0)
                    consumer.commit(msg, asynchronous=False)
                except Exception as exc:
                    log.exception("Failed to process message: %s", exc)
        finally:
            producer.flush(5)
            consumer.close()
            conn.close()
            log.info("Classification consumer stopped.")

    def stop(self) -> None:
        self._running = False


def main() -> None:
    ClassificationConsumer().run()


if __name__ == "__main__":
    main()
