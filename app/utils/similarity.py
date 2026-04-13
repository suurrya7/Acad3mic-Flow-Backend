import math
import collections
import re

def tokenize(text: str) -> list[str]:
    """Basic tokenizer: lowercases and extracts alphanumeric words."""
    if not text:
        return []
    return re.findall(r'\b\w+\b', text.lower())

def compute_tf(tokens: list[str]) -> dict[str, float]:
    """Computes Term Frequency for a list of tokens."""
    tf = collections.Counter(tokens)
    total_tokens = len(tokens)
    if total_tokens == 0:
        return {}
    return {word: count / total_tokens for word, count in tf.items()}

def compute_idf(corpus_tokens: list[list[str]]) -> dict[str, float]:
    """Computes Inverse Document Frequency for a corpus."""
    N = len(corpus_tokens)
    idf = {}
    
    # Count how many documents contain each word
    doc_freq = collections.Counter()
    for tokens in corpus_tokens:
        unique_tokens = set(tokens)
        for token in unique_tokens:
            doc_freq[token] += 1
            
    for word, count in doc_freq.items():
        # Prevent division by zero and smooth IDF
        idf[word] = math.log((1 + N) / (1 + count)) + 1
        
    return idf

def compute_tfidf(tf: dict[str, float], idf: dict[str, float]) -> dict[str, float]:
    """Computes TF-IDF vector."""
    return {word: tf_val * idf.get(word, 0.0) for word, tf_val in tf.items()}

def cosine_similarity(vec1: dict[str, float], vec2: dict[str, float]) -> float:
    """Computes cosine similarity between two vectors."""
    intersection = set(vec1.keys()) & set(vec2.keys())
    numerator = sum([vec1[x] * vec2[x] for x in intersection])
    
    sum1 = sum([val**2 for val in vec1.values()])
    sum2 = sum([val**2 for val in vec2.values()])
    
    denominator = math.sqrt(sum1) * math.sqrt(sum2)
    if not denominator:
        return 0.0
    else:
        return float(numerator) / denominator

def get_max_similarity(new_text: str, past_texts: list[str]) -> float:
    """
    Compares new_text against a list of past_texts using TF-IDF and Cosine Similarity.
    Returns the maximum similarity score (0.0 to 1.0).
    """
    if not new_text or not past_texts:
        return 0.0
        
    all_texts = [new_text] + past_texts
    tokenized_corpus = [tokenize(t) for t in all_texts]
    
    # Compute IDF over the combined corpus
    idf = compute_idf(tokenized_corpus)
    
    # Compute TF-IDF for new_text
    tf_new = compute_tf(tokenized_corpus[0])
    tfidf_new = compute_tfidf(tf_new, idf)
    
    max_sim = 0.0
    for i in range(1, len(tokenized_corpus)):
        tf_past = compute_tf(tokenized_corpus[i])
        tfidf_past = compute_tfidf(tf_past, idf)
        sim = cosine_similarity(tfidf_new, tfidf_past)
        if sim > max_sim:
            max_sim = sim
            
    return max_sim
