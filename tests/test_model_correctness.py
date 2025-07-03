import pytest
import os
import pickle
import sys
import joblib


# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'api')))
CURRENT_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_BASE_DIR = os.path.join(CURRENT_TEST_DIR, '..', 'model') 
SENTIMENT_MODEL_PATH = os.path.join(MODEL_BASE_DIR, 'model.pkl') # Hoặc sentiment_model.pkl
TFIDF_VECTORIZER_PATH = os.path.join(MODEL_BASE_DIR, 'vectorizer.pkl') # Hoặc tfidf_vectorizer.pkl

@pytest.fixture(scope="session")
def loaded_models():
    sentiment_model = None
    tfidf_vectorizer = None
    if not os.path.exists(SENTIMENT_MODEL_PATH):
        pytest.fail(f"Model file not found at: {SENTIMENT_MODEL_PATH}. Please ensure your model is trained and saved.")
    if not os.path.exists(TFIDF_VECTORIZER_PATH):
        pytest.fail(f"Vectorizer file not found at: {TFIDF_VECTORIZER_PATH}. Please ensure your vectorizer is saved.")

    try:
        print(f"Attempting to load sentiment model from: {os.path.abspath(SENTIMENT_MODEL_PATH)}")
        with open(SENTIMENT_MODEL_PATH, 'rb') as f:
            sentiment_model = joblib.load(f) # <--- SỬA TỪ pickle.load() SANG joblib.load()
        print("Sentiment model loaded successfully!")

        print(f"Attempting to load TF-IDF vectorizer from: {os.path.abspath(TFIDF_VECTORIZER_PATH)}")
        with open(TFIDF_VECTORIZER_PATH, 'rb') as f:
            tfidf_vectorizer = joblib.load(f) # <--- SỬA TỪ pickle.load() SANG joblib.load()
        print("TF-IDF vectorizer loaded successfully!")

        print("\nModels loaded successfully for testing.")
        return sentiment_model, tfidf_vectorizer
    except Exception as e:
        pytest.fail(f"Failed to load models: {e}")

def test_model_and_vectorizer_loaded(loaded_models):
    """
    Kiểm tra xem model và vectorizer có được tải thành công không.
    """
    sentiment_model, tfidf_vectorizer = loaded_models
    assert sentiment_model is not None, "Sentiment model was not loaded."
    assert tfidf_vectorizer is not None, "TF-IDF vectorizer was not loaded."

    #Kiểm tra loại đối tượng cơ bản (ví dụ: nếu bạn dùng LogisticRegression và TfidfVectorizer)
    from sklearn.linear_model import LogisticRegression
    from sklearn.feature_extraction.text import TfidfVectorizer
    assert isinstance(sentiment_model, LogisticRegression)
    assert isinstance(tfidf_vectorizer, TfidfVectorizer)

def test_positive_sentiment(loaded_models):
    sentiment_model, tfidf_vectorizer = loaded_models
    text = "rất tốt, tối thích nó"
    processed_text = [text.lower()]
    text_vectorized = tfidf_vectorizer.transform(processed_text)
    prediction = sentiment_model.predict(text_vectorized)[0]
    assert prediction == "POS", f"Expected positive sentiment (POS) for '{text}', but got {prediction}"
def test_negative_sentiment(loaded_models):
    sentiment_model, tfidf_vectorizer = loaded_models
    text = "rất tệ, tôi không thích nó"
    processed_text = [text.lower()]
    text_vectorized = tfidf_vectorizer.transform(processed_text)
    prediction = sentiment_model.predict(text_vectorized)[0]
    assert prediction == "NEG", f"Expected negative sentiment (NEG) for '{text}', but got {prediction}" 
def test_neutral_sentiment(loaded_models):
    sentiment_model, tfidf_vectorizer = loaded_models
    text = "bình thường, dùng tạm được"
    processed_text = [text.lower()]
    text_vectorized = tfidf_vectorizer.transform(processed_text)
    prediction = sentiment_model.predict(text_vectorized)[0]
    assert prediction == "NEU", f"Expected neutral sentiment (NEU) for '{text}', but got {prediction}"  