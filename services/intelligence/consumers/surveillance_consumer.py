"""Surveillance consumer.

Consumes from `isolates.classified` and runs CUSUM + BOCPD + clustering. Emits
alerts to `alerts.cusum` / `alerts.cluster` and persists to TimescaleDB.

Run as: python -m intelligence.consumers.surveillance_consumer (PYTHONPATH=services)
"""
from __future__ import annotations

import json
import logging
import os
import signal
import sys
from datetime import datetime
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor

from ..db import database_url
from ..surveillance.bocpd import BOCPD
from ..surveillance.clustering import ClusterDetectorState, update_cluster
from ..surveillance.cusum import CUSUMState, initialize_cusum, update_cusum
from ..surveillance.ensemble import AlertSeverity, fuse_alerts

log = logging.getLogger("surveillance-consumer")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

CLASSIFIED_TOPIC = "isolates.classified"
ALERTS_CUSUM_TOPIC = "alerts.cusum"
ALERTS_CLUSTER_TOPIC = "alerts.cluster"
CONSUMER_GROUP = "intelligence-surveillance"

DEFAULT_BASELINE = 0.10  # used until we have enough history


class SurveillanceConsumer:
    def __init__(self) -> None:
        self.cusum_states: dict[tuple, CUSUMState] = {}
        self.bocpd_states: dict[tuple, BOCPD] = {}
        self.cluster_state = ClusterDetectorState()
        self._running = True

    def stop(self) -> None:
        self._running = False

    def _key(self, event: dict) -> tuple[str, int, str]:
        return event["facility_id"], int(event["organism_taxid"]), event["antibiotic_atc"]

    def _load_or_init_cusum(self, conn, key: tuple) -> CUSUMState:
        if key in self.cusum_states:
            return self.cusum_states[key]
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM cusum_state WHERE facility_id=%s AND organism_taxid=%s AND antibiotic_atc=%s",
                key,
            )
            row = cur.fetchone()
        if row:
            state = CUSUMState(
                facility_id=row["facility_id"],
                organism_taxid=row["organism_taxid"],
                antibiotic_atc=row["antibiotic_atc"],
                cusum_sum=row["cusum_sum"],
                baseline_rate=row["baseline_rate"],
                reference_value=row["reference_value"],
                threshold=row["threshold"],
                observations=row["observations_count"],
            )
        else:
            params = initialize_cusum(DEFAULT_BASELINE)
            state = CUSUMState(
                facility_id=key[0],
                organism_taxid=key[1],
                antibiotic_atc=key[2],
                baseline_rate=params["p0"],
                reference_value=params["k"],
                threshold=params["h"],
            )
        self.cusum_states[key] = state
        return state

    def _load_or_init_bocpd(self, conn, key: tuple) -> BOCPD:
        if key in self.bocpd_states:
            return self.bocpd_states[key]
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT state_blob FROM bocpd_state WHERE facility_id=%s AND organism_taxid=%s AND antibiotic_atc=%s",
                key,
            )
            row = cur.fetchone()
        if row:
            bocpd = BOCPD.from_state_dict(row["state_blob"])
        else:
            bocpd = BOCPD()
        self.bocpd_states[key] = bocpd
        return bocpd

    def _persist_cusum(self, conn, state: CUSUMState) -> None:
        sql = """
            INSERT INTO cusum_state (
                facility_id, organism_taxid, antibiotic_atc,
                cusum_sum, baseline_rate, reference_value, threshold, observations_count
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (facility_id, organism_taxid, antibiotic_atc) DO UPDATE SET
                cusum_sum = EXCLUDED.cusum_sum,
                observations_count = EXCLUDED.observations_count,
                updated_at = NOW();
        """
        with conn.cursor() as cur:
            cur.execute(sql, (
                state.facility_id, state.organism_taxid, state.antibiotic_atc,
                state.cusum_sum, state.baseline_rate, state.reference_value,
                state.threshold, state.observations,
            ))
        conn.commit()

    def _persist_bocpd(self, conn, key: tuple, bocpd: BOCPD, cp_prob: float) -> None:
        sql = """
            INSERT INTO bocpd_state (
                facility_id, organism_taxid, antibiotic_atc, state_blob,
                hazard_rate, max_run_length, changepoint_prob
            ) VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s)
            ON CONFLICT (facility_id, organism_taxid, antibiotic_atc) DO UPDATE SET
                state_blob = EXCLUDED.state_blob,
                changepoint_prob = EXCLUDED.changepoint_prob,
                updated_at = NOW();
        """
        with conn.cursor() as cur:
            cur.execute(sql, (
                *key,
                json.dumps(bocpd.get_state_dict()),
                bocpd.hazard,
                bocpd.max_rl,
                cp_prob,
            ))
        conn.commit()

    def _insert_alert(
        self,
        conn,
        *,
        event: dict,
        alert_type: str,
        severity: AlertSeverity,
        details: Optional[dict] = None,
        current_rate: Optional[float] = None,
        baseline_rate: Optional[float] = None,
    ) -> str:
        sql = """
            INSERT INTO alerts (
                facility_id, organism_taxid, organism_name,
                antibiotic_atc, antibiotic_name,
                alert_type, severity, current_rate, baseline_rate, details
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING alert_id;
        """
        with conn.cursor() as cur:
            cur.execute(sql, (
                event["facility_id"],
                event["organism_taxid"],
                event["organism_name"],
                event.get("antibiotic_atc"),
                event.get("antibiotic_name"),
                alert_type,
                severity.value,
                current_rate,
                baseline_rate,
                json.dumps(details or {}),
            ))
            alert_id = str(cur.fetchone()[0])
        conn.commit()
        return alert_id

    def _process(self, conn, producer, event: dict) -> None:
        sir = event.get("sir_classification")
        if sir not in {"S", "I", "R"}:
            return

        key = self._key(event)
        observation = 1 if sir == "R" else 0

        cusum_state = self._load_or_init_cusum(conn, key)
        cusum_state, cusum_fired = update_cusum(cusum_state, observation)
        self._persist_cusum(conn, cusum_state)

        bocpd = self._load_or_init_bocpd(conn, key)
        bocpd_fired, cp_prob = bocpd.update(observation)
        self._persist_bocpd(conn, key, bocpd, cp_prob)

        severity = fuse_alerts(cusum_fired, bocpd_fired)
        if severity != AlertSeverity.NONE:
            details = {
                "cusum_fired": cusum_fired,
                "bocpd_fired": bocpd_fired,
                "bocpd_changepoint_prob": cp_prob,
                "cusum_observations": cusum_state.observations,
            }
            alert_id = self._insert_alert(
                conn,
                event=event,
                alert_type="ENSEMBLE",
                severity=severity,
                details=details,
                baseline_rate=cusum_state.baseline_rate,
            )
            payload = {
                "alert_id": alert_id,
                "alert_type": "ENSEMBLE",
                "severity": severity.value,
                "facility_id": event["facility_id"],
                "organism_taxid": event["organism_taxid"],
                "organism_name": event["organism_name"],
                "antibiotic_atc": event["antibiotic_atc"],
                "antibiotic_name": event["antibiotic_name"],
                "details": details,
                "triggered_at": datetime.utcnow().isoformat() + "Z",
            }
            producer.produce(
                ALERTS_CUSUM_TOPIC,
                key=event["facility_id"].encode(),
                value=json.dumps(payload).encode(),
            )

        cluster = update_cluster(
            self.cluster_state,
            facility_id=event["facility_id"],
            ward_id=event.get("ward_id"),
            organism_taxid=event["organism_taxid"],
            organism_name=event["organism_name"],
            sir_classification=sir,
            collection_date=event["collection_date"],
            specimen_id=event["specimen_id"],
        )
        if cluster:
            details = {
                "ward_id": cluster.ward_id,
                "isolate_count": cluster.isolate_count,
                "window_days": cluster.window_days,
                "earliest_collection_date": cluster.earliest_collection_date,
                "latest_collection_date": cluster.latest_collection_date,
            }
            alert_id = self._insert_alert(
                conn,
                event=event,
                alert_type="CLUSTER",
                severity=AlertSeverity.HIGH,
                details=details,
            )
            producer.produce(
                ALERTS_CLUSTER_TOPIC,
                key=event["facility_id"].encode(),
                value=json.dumps({
                    "alert_id": alert_id,
                    "alert_type": "CLUSTER",
                    "severity": "HIGH",
                    "facility_id": cluster.facility_id,
                    "organism_taxid": cluster.organism_taxid,
                    "organism_name": cluster.organism_name,
                    "details": details,
                    "triggered_at": datetime.utcnow().isoformat() + "Z",
                }).encode(),
            )

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
        producer = Producer({"bootstrap.servers": bootstrap, "client.id": "surveillance"})
        consumer.subscribe([CLASSIFIED_TOPIC])

        signal.signal(signal.SIGTERM, lambda *_: self.stop())
        signal.signal(signal.SIGINT, lambda *_: self.stop())

        conn = psycopg2.connect(database_url())
        log.info("Surveillance consumer started.")

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
                    self._process(conn, producer, event)
                    producer.poll(0)
                    consumer.commit(msg, asynchronous=False)
                except Exception as exc:
                    log.exception("Failed to process message: %s", exc)
        finally:
            producer.flush(5)
            consumer.close()
            conn.close()
            log.info("Surveillance consumer stopped.")


def main() -> None:
    SurveillanceConsumer().run()


if __name__ == "__main__":
    main()
