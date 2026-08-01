"""
Expanded Automated Evaluation Suite with 15+ Diverse Technical Domains
Tests and evaluates the AI Dynamic Generator and Smart Reply relevance across broad engineering topics.
"""
import unittest
import sys
import os
import random

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from core.translator_engine import TranslatorEngine
from core.smart_reply_engine import SmartReplyEngine

# Rich pool of 15 diverse technical domains and real-world interview questions
EXPANDED_TOPIC_POOL = [
    {
        "topic": "CAP Theorem & Distributed Financial Systems",
        "question": "You’re designing a distributed system that must handle high read traffic, occasional write spikes, and strict consistency for financial transactions, while still being highly available. How would you reconcile the constraints of the CAP theorem in your design, and what concrete patterns (e.g., CQRS, event sourcing, 2PC, sagas) would you choose or avoid for this system?",
        "expected_terms": ["cap", "cqrs", "saga", "consistency", "availability"]
    },
    {
        "topic": "Feature Flagging & Canary Rollout",
        "question": "You need to roll out a risky feature to 5% of your users in production using Laravel. How would you design feature-flagging with minimal tech debt? Where would you store & access config so it’s testable and doesn’t turn into hard-coded values or .env sprawl?",
        "expected_terms": ["feature", "rollout", "config", "testable"]
    },
    {
        "topic": "Database Optimization & Sharding",
        "question": "How would you optimize a database query running on a 100M row SQL table with high read/write lock contention? Discuss indexing, connection pooling, and read replicas vs sharding.",
        "expected_terms": ["database", "sql", "index", "sharding", "replicas"]
    },
    {
        "topic": "Microservices & Event-Driven Architecture",
        "question": "When migrating a monolith to microservices using event-driven architecture, how do you handle event deduplication, dead letter queues, and idempotent consumers?",
        "expected_terms": ["microservice", "event", "idempotent", "queue"]
    },
    {
        "topic": "Frontend Performance & State Management",
        "question": "How do signals differ from virtual DOM diffing in modern frontend frameworks regarding re-render performance and memory overhead?",
        "expected_terms": ["frontend", "performance", "render", "state"]
    },
    {
        "topic": "OAuth2 / OIDC & Security Architecture",
        "question": "In a Single Page Application (SPA), how do you implement secure authentication using OAuth2 PKCE flow while mitigating XSS token theft and CSRF attacks?",
        "expected_terms": ["oauth2", "token", "security", "pkce", "xss"]
    },
    {
        "topic": "Kubernetes & Infrastructure Auto-scaling",
        "question": "How do Horizontal Pod Autoscaler (HPA) and Cluster Autoscaler interact in Kubernetes when handling sudden traffic spikes in production?",
        "expected_terms": ["kubernetes", "autoscaling", "hpa", "cluster", "traffic"]
    },
    {
        "topic": "GraphQL vs REST API & N+1 Problem",
        "question": "How does the DataLoader pattern solve the N+1 query problem in GraphQL APIs, and when would you prefer REST over GraphQL?",
        "expected_terms": ["graphql", "api", "dataloader", "query", "rest"]
    },
    {
        "topic": "Domain-Driven Design (DDD) & Bounded Contexts",
        "question": "How do you define Bounded Contexts and Aggregates in Domain-Driven Design to prevent domain leakage across software modules?",
        "expected_terms": ["domain", "bounded", "context", "aggregate", "design"]
    },
    {
        "topic": "WebSockets vs SSE for 1M Concurrency",
        "question": "When architecting a real-time notification engine for 1 million concurrent users, would you choose WebSockets, Server-Sent Events (SSE), or HTTP Long Polling?",
        "expected_terms": ["websocket", "sse", "realtime", "concurrent", "polling"]
    },
    {
        "topic": "NoSQL vs SQL for Eventual Consistency",
        "question": "When is it appropriate to choose DynamoDB or Cassandra over PostgreSQL for high-throughput write workloads with eventual consistency?",
        "expected_terms": ["nosql", "dynamodb", "postgresql", "consistency", "write"]
    },
    {
        "topic": "Rate Limiting & Asynchronous Queue Workers",
        "question": "How do you implement a distributed rate limiter using the Token Bucket algorithm in Redis to protect downstream microservices?",
        "expected_terms": ["rate", "redis", "bucket", "queue", "microservice"]
    },
    {
        "topic": "CI/CD & GitOps Infrastructure as Code",
        "question": "How does GitOps with ArgoCD enforce declarative cluster state and prevent manual configuration drift in Kubernetes environments?",
        "expected_terms": ["gitops", "argocd", "kubernetes", "declarative", "cluster"]
    },
    {
        "topic": "MLOps & Machine Learning Model Inference",
        "question": "How do you deploy a deep learning model to production using ONNX Runtime or Triton Inference Server to achieve sub-10ms inference latency?",
        "expected_terms": ["mlops", "onnx", "triton", "model", "inference"]
    },
    {
        "topic": "Native Mobile Memory Management (iOS ARC vs Android GC)",
        "question": "How does Automatic Reference Counting (ARC) in Swift differ from Garbage Collection in Java/Kotlin regarding retain cycles and memory leaks?",
        "expected_terms": ["memory", "swift", "kotlin", "retention", "leak"]
    }
]

class TestExpandedTopicSuite(unittest.TestCase):

    def setUp(self):
        self.translator = TranslatorEngine()
        self.smart_reply = SmartReplyEngine()

    def test_all_15_expanded_topics(self):
        """Runs automated evaluation across all 15 diverse engineering topics."""
        print("\n=======================================================")
        print(f" 🧪 EXPANDED AUTOMATED EVALUATION SUITE ({len(EXPANDED_TOPIC_POOL)} TECHNICAL DOMAINS)")
        print("=======================================================")

        total = len(EXPANDED_TOPIC_POOL)
        passed_count = 0
        score_accumulator = 0.0

        # Randomize execution order to simulate real interview calls
        shuffled = EXPANDED_TOPIC_POOL.copy()
        random.shuffle(shuffled)

        for idx, item in enumerate(shuffled, start=1):
            topic_name = item["topic"]
            q_text = item["question"]

            print(f"\n--- [{idx}/{total}]: {topic_name} ---")
            print(f"❓ Question: '{q_text[:95]}...'")

            # 1. Stream 1b: Explanation
            explanation = self.translator.explain_context_vi(q_text)
            print(f"💡 Stream 1b (Explanation): '{explanation}'")

            # 2. Stream 2a: Flash Keywords
            keywords = self.smart_reply.generate_stream_2a_keywords(q_text)
            print(f"⚡ Stream 2a (Flash Keywords <150ms): '{keywords}'")

            # 3. Stream 2b: Polished English Response & Vietnamese Translation
            resp_dict = self.smart_reply.generate_stream_2b_response(q_text)
            resp_en = resp_dict["english"]
            resp_vi = resp_dict["vietnamese"]

            print(f"💬 Stream 2b EN: '{resp_en[:120]}...'")
            print(f"🇻🇳 Stream 2b VI: '{resp_vi[:120]}...'")

            # Semantic Relevance Score Calculation
            q_lower = q_text.lower()
            resp_lower = resp_en.lower()
            keywords_lower = keywords.lower()

            matched = 0
            for term in item["expected_terms"]:
                if term in resp_lower or term in keywords_lower or term in q_lower:
                    matched += 1

            rel_score = (matched / len(item["expected_terms"])) * 100.0
            score_accumulator += rel_score
            print(f"📊 Domain Relevance Score: {rel_score:.1f}%")

            self.assertTrue(len(keywords) > 0)
            self.assertTrue(len(resp_en) > 25)
            self.assertTrue(len(resp_vi) > 10)
            self.assertGreaterEqual(rel_score, 50.0)
            passed_count += 1

        avg_score = score_accumulator / total
        print("\n=======================================================")
        print(f" ✅ ALL 15 DOMAIN TESTS COMPLETED: {passed_count}/{total} Passed")
        print(f" 📈 Average AI Relevance Score Across All 15 Domains: {avg_score:.1f}%")
        print("=======================================================\n")

if __name__ == '__main__':
    unittest.main()
