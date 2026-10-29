import logging
import os
import time
import uuid

import joblib
import pandas as pd
from fastapi import FastAPI, Request
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel

# ---------- Logging (Practical-11) ----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("student-api")

# ---------- Prometheus metrics (Practical-12) ----------
HTTP_REQUESTS = Counter(
    "student_api_http_requests_total",
    "Total HTTP requests received by the Student Result Prediction API",
    ["method", "path", "status"],
)
HTTP_LATENCY = Histogram(
    "student_api_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
)
PREDICTIONS = Counter(
    "student_api_predictions_total",
    "Total Student Result Prediction attempts",
    ["result"],
)
MODEL_LOADED = Gauge(
    "student_api_model_loaded",
    "Whether the Student Result Prediction model is loaded",
)

# ---------- Model loading ----------
# Use the same model artifact as Practical-7 to 11 (do not retrain).
MODEL_FILE = os.getenv("MODEL_FILE", "model.joblib")

try:
    model = joblib.load(MODEL_FILE)
    MODEL_LOADED.set(1)
    logger.info("event=model_loaded model_file=%s", MODEL_FILE)
except Exception:
    MODEL_LOADED.set(0)
    logger.exception("event=model_load_failed model_file=%s", MODEL_FILE)
    raise

app = FastAPI(title="Student Result Prediction API")


# Adjust field names to match your existing schema from earlier practicals.
class StudentResultInput(BaseModel):
    attendance: float
    internal_marks: float
    assignment_marks: float
    previous_score: float


@app.middleware("http")
async def observe_requests(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    path = request.url.path
    method = request.method
    start_time = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        duration = time.perf_counter() - start_time
        # Do not count Prometheus' own scrapes in user-traffic metrics
        if path != "/metrics":
            HTTP_REQUESTS.labels(method=method, path=path, status=str(status)).inc()
            HTTP_LATENCY.labels(method=method, path=path).observe(duration)
        logger.info(
            "event=http_request request_id=%s method=%s path=%s status=%s duration_ms=%.1f",
            request_id, method, path, status, duration * 1000,
        )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/predict")
def predict(data: StudentResultInput):
    try:
        input_df = pd.DataFrame([data.model_dump()])
        prediction = model.predict(input_df)
        PREDICTIONS.labels(result="success").inc()
        logger.info("event=prediction_succeeded")
        value = prediction[0]
        return {"prediction": value.item() if hasattr(value, "item") else value}
    except Exception:
        PREDICTIONS.labels(result="error").inc()
        logger.exception("event=prediction_failed")
        raise


@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
