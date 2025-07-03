from fastapi import FastAPI, HTTPException
import joblib
import os
from contextlib import asynccontextmanager
from schema import PredictRequest, PredictResponse,BatchPredictRequest, BatchPredictResponse, HealthCheckResponse
from utils.logging import logger

from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import get_tracer_provider, set_tracer_provider

set_tracer_provider(
    TracerProvider(resource=Resource.create({SERVICE_NAME: "tsc"}))
)
tracer = get_tracer_provider().get_tracer("tsc", "0.1.2")
jaeger_exporter = JaegerExporter(
    agent_host_name="localhost",
    agent_port=6831,
)

span_processor = BatchSpanProcessor(jaeger_exporter)
get_tracer_provider().add_span_processor(span_processor)  # type: ignore

# Use decorator
from functools import wraps
def trace_span(span_name):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            with tracer.start_as_current_span(span_name) as span:
                return await func(*args, **kwargs)
        return wrapper
    return decorator


MODEL_DIR = './model'
MODEL_PATH = os.path.join(MODEL_DIR, 'model.pkl')
VECTORIZER_PATH = os.path.join(MODEL_DIR, 'vectorizer.pkl')

_sentiment_model = None
_tfidf_vectorizer = None

#@trace_span("model-loader")
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager to load models at startup and release resources on shutdown."""
    global _sentiment_model, _tfidf_vectorizer
    with tracer.start_as_current_span("model-loader") as span:
        print("Application startup: Loading sentiment model and TF-IDF vectorizer...")
        try:
            if not os.path.exists(MODEL_PATH) or not os.path.exists(VECTORIZER_PATH):
                span.set_attribute("error", True)
                span.record_exception(FileNotFoundError(f"Model or vectorizer file not found: {MODEL_PATH}, {VECTORIZER_PATH}"))
                raise FileNotFoundError(
                    f"Lỗi: Không tìm thấy file model hoặc vectorizer. "
                    f"Kiểm tra lại đường dẫn: {MODEL_PATH} và {VECTORIZER_PATH}"
                )

            _sentiment_model = joblib.load(MODEL_PATH)
            _tfidf_vectorizer = joblib.load(VECTORIZER_PATH)
            print("Application startup: Models loaded successfully.")
            span.set_attribute("model_loaded_status", "success")
        except Exception as e:
            print(f"Application startup error: Failed to load models - {e}")
            _sentiment_model = None
            _tfidf_vectorizer = None
            span.set_attribute("error", True)
            span.record_exception(e)
            span.set_attribute("load_error_message", str(e))
    yield 
    print("Application shutdown: Releasing resources...")

app = FastAPI(
    title="Simple Sentiment Analysis API",
    description="API để phân loại cảm xúc (Tích cực, Tiêu cực, Trung tính) dựa trên mô hình truyền thống.",
    version="1.0.0",
    lifespan=lifespan
)

@trace_span("check-models-loaded")
async def _check_models_loaded():
    if _sentiment_model is None or _tfidf_vectorizer is None:
        raise HTTPException(
            status_code=503,
            detail="Models not loaded. Server is not ready yet or failed to load models."
        )

@trace_span("predictor")
@app.post(
    "/predict/",
    response_model=PredictResponse,
    summary="Dự đoán cảm xúc cho một bình luận duy nhất",
    description="Phân tích cảm xúc của một bình luận sản phẩm và trả về danh mục dự đoán (POS, NEG, NEU)."
)
async def predict_single_comment(request: PredictRequest):
    logger.info("Make predictions...")
    _check_models_loaded() 
    comment_vectorized = _tfidf_vectorizer.transform([request.comment])
    predicted_label = _sentiment_model.predict(comment_vectorized)[0]
    return PredictResponse(
        original_comment=request.comment,
        predicted_sentiment=predicted_label
    )


@trace_span("batch-predictor")
@app.post(
    "/predict_batch/",
    response_model=BatchPredictResponse,
    summary="Dự đoán cảm xúc cho nhiều bình luận",
    description="Phân tích cảm xúc của một danh sách các bình luận và trả về các danh mục dự đoán cho từng bình luận."
)
async def predict_batch_comments(request: BatchPredictRequest):
    logger.info("Make batch predictions...")
    _check_models_loaded() 
    comments_vectorized = _tfidf_vectorizer.transform(request.comments)
    predicted_labels_raw = _sentiment_model.predict(comments_vectorized)
    results = [
        PredictResponse(original_comment=comment, predicted_sentiment=label)
        for comment, label in zip(request.comments, predicted_labels_raw)
    ]
    return BatchPredictResponse(predictions=results)

@app.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Endpoint kiểm tra trạng thái sức khỏe",
    description="Kiểm tra trạng thái của API và việc tải model."
)
async def health_check():
    models_are_loaded = (_sentiment_model is not None and _tfidf_vectorizer is not None)
    return HealthCheckResponse(
        status="ok" if models_are_loaded else "not ready",
        models_loaded=models_are_loaded
    )

