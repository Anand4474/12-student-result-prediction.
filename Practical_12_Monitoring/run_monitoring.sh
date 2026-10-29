#!/usr/bin/env bash
# Run from inside Practical_12_Monitoring/
docker network create mlops-monitoring 2>/dev/null || true

docker run -d --name prometheus --network mlops-monitoring -p 9090:9090 \
  -v "$PWD/prometheus.yml:/etc/prometheus/prometheus.yml:ro" \
  -v "$PWD/student_api_alerts.yml:/etc/prometheus/student_api_alerts.yml:ro" \
  prom/prometheus

docker run -d --name grafana --network mlops-monitoring -p 3000:3000 grafana/grafana

echo "Prometheus: http://localhost:9090  |  Grafana: http://localhost:3000 (data source URL: http://prometheus:9090)"
# Cleanup: docker rm -f grafana prometheus
