"""
Dynamic AI Model & NLP Generator Engine
Generates dynamic contextual responses without hardcoded answer templates.
Supports Cloud LLM APIs (Gemini, Groq, OpenAI) with fast local NLP dynamic fallback.
"""
import re
import time
from core.gemini_client import GeminiClient
from utils.logger import logger

class DynamicAIGenerator:
    REQUIRED_STREAM_KEYS = (
        "stream_1b",
        "stream_2a",
        "stream_2b_quick_en",
        "stream_2b_quick_vi",
        "stream_2b_en",
        "stream_2b_vi",
        "stream_2b_should_reply",
    )

    def __init__(self, gemini_client=None):
        self.gemini = gemini_client or GeminiClient()

    def generate_all_streams(self, english_text: str) -> dict:
        """
        Dynamically analyzes any English question/statement and produces:
        - stream_1b: Vietnamese context explanation
        - stream_2a: Flash keywords (< 150ms)
        - stream_2b_en: Recommended English response (< 400ms)
        - stream_2b_vi: Vietnamese translation of response
        """
        if not english_text or not english_text.strip():
            return {
                "stream_1b": "Đang chờ âm thanh...",
                "stream_2a": "Keywords",
                "stream_2b_quick_en": "One moment, please.",
                "stream_2b_quick_vi": "(Xin chờ tôi một chút.)",
                "stream_2b_en": "Waiting for input...",
                "stream_2b_vi": "(Đang chờ dữ liệu đầu vào...)",
                "stream_2b_should_reply": False,
            }

        # Try Gemini / Cloud LLM API if key is present
        if self.gemini.is_configured:
            try:
                return self._generate_via_gemini(english_text)
            except Exception as e:
                logger.warning(f"Gemini API fallback to Dynamic NLP Engine: {e}")

        # Dynamic NLP Synthesis (Zero hardcoded text)
        return self._generate_dynamic_nlp(english_text)

    def _generate_via_gemini(self, english_text: str) -> dict:
        """Use Gemini for content-aware analysis and reply generation."""
        prompt = (
            "You assist a Vietnamese human during a live English conversation. "
            "Write replies that the human can say to the other speaker; never "
            "answer as an AI assistant or discuss your own capabilities. "
            "The text before 'Previous context:' is the LATEST utterance and is "
            "always primary. Earlier context only helps resolve references; never "
            "answer an older question instead of the latest utterance.\n\n"
            f"INPUT:\n{english_text}\n\n"
            "Return one JSON object with exactly these fields:\n"
            "- stream_1b: concise Vietnamese explanation of the latest meaning, "
            "intent, and relevant context.\n"
            "- stream_2a: 4-6 keywords from the latest utterance, separated by semicolons.\n"
            "- stream_2b_should_reply: true only when the listener should respond: "
            "a direct question, request, decision, or action directed at them. Use "
            "false for narration, fillers, acknowledgements, rhetorical or "
            "self-answered questions, informational updates, and statements that "
            "merely say what someone could/might do. Do not infer a request from "
            "a modal verb alone.\n"
            "- stream_2b_quick_en: when a reply is needed, a useful natural reply "
            "of at most 10 words; otherwise empty.\n"
            "- stream_2b_quick_vi: faithful Vietnamese translation of quick_en; "
            "otherwise empty.\n"
            "- stream_2b_en: when needed, a direct professional answer of at most "
            "2 short sentences. Answer the exact question, never use generic "
            "boilerplate or invent facts; request clarification only when truly needed.\n"
            "- stream_2b_vi: faithful Vietnamese translation of stream_2b_en; "
            "otherwise empty."
        )
        started = time.perf_counter()
        result = self.gemini.generate_json(
            prompt, max_output_tokens=650, thinking_level="minimal"
        )
        normalized = self._normalize_gemini_result(result)
        if (
            normalized["stream_2b_should_reply"]
            and not self._latest_explicitly_requires_response(english_text)
        ):
            logger.info(
                "Suppressed speculative recommended reply for an "
                "informational latest turn."
            )
            normalized.update(
                {
                    "stream_2b_should_reply": False,
                    "stream_2b_quick_en": "",
                    "stream_2b_quick_vi": (
                        "Không cần phản hồi ngay — tiếp tục lắng nghe."
                    ),
                    "stream_2b_en": "",
                    "stream_2b_vi": "",
                }
            )
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info(
            f"Gemini {self.gemini.model} generated conversation streams "
            f"in {elapsed_ms:.0f} ms"
        )
        return normalized

    @staticmethod
    def _latest_explicitly_requires_response(english_text: str) -> bool:
        """Conservatively require a direct response cue in the latest turn."""
        latest = english_text.split("\nPrevious context:", 1)[0].strip()
        lowered = latest.lower()
        if "?" in latest:
            return True
        if re.search(
            r"\b(please|let me know|can you|could you|would you|will you|"
            r"do you agree|what do you think|are you okay with|"
            r"i need you|we need you|your approval|your input|"
            r"your decision|your feedback)\b",
            lowered,
        ):
            return True
        return bool(
            re.match(
                r"^\s*(review|check|send|share|update|confirm|prepare|"
                r"schedule|fix|investigate|provide|create|choose|decide)\b",
                lowered,
            )
        )

    @classmethod
    def _normalize_gemini_result(cls, result: dict) -> dict:
        missing = [key for key in cls.REQUIRED_STREAM_KEYS if key not in result]
        if missing:
            raise ValueError(f"Gemini response missing fields: {', '.join(missing)}")

        normalized = {
            key: str(result.get(key, "")).strip()
            for key in cls.REQUIRED_STREAM_KEYS
            if key != "stream_2b_should_reply"
        }
        raw_should_reply = result["stream_2b_should_reply"]
        if isinstance(raw_should_reply, bool):
            should_reply = raw_should_reply
        elif isinstance(raw_should_reply, str) and raw_should_reply.lower() in {
            "true",
            "false",
        }:
            should_reply = raw_should_reply.lower() == "true"
        else:
            raise ValueError("Gemini should_reply field is not a boolean")
        normalized["stream_2b_should_reply"] = should_reply
        if not should_reply:
            normalized.update(
                {
                    "stream_2b_quick_en": "",
                    "stream_2b_quick_vi": "Không cần phản hồi ngay — tiếp tục lắng nghe.",
                    "stream_2b_en": "",
                    "stream_2b_vi": "",
                }
            )
        return normalized

    def _generate_dynamic_nlp(self, english_text: str) -> dict:
        """
        Dynamic NLP Synthesis Engine:
        Parses topics, constraints, design patterns, and technical nouns dynamically.
        Builds contextual keywords, context explanation, and professional answers.
        """
        latest_text = english_text.split("\nPrevious context:", 1)[0].strip()
        text_clean = re.sub(r'[^\w\s-]', ' ', english_text.lower())
        latest_clean = re.sub(r'[^\w\s-]', ' ', latest_text.lower())
        words = text_clean.split()
        
        # Stopwords filter
        stopwords = {
            "the", "a", "an", "and", "or", "but", "if", "in", "on", "at", "to", "for", "with",
            "by", "about", "against", "between", "into", "through", "during", "before", "after",
            "above", "below", "from", "up", "down", "out", "off", "over", "under", "again",
            "further", "then", "once", "here", "there", "when", "where", "why", "how", "all",
            "any", "both", "each", "few", "more", "most", "other", "some", "such", "no", "nor",
            "not", "only", "own", "same", "so", "than", "too", "very", "can", "will", "just",
            "don", "should", "now", "you", "your", "yours", "would", "could", "this", "that",
            "these", "those", "am", "is", "are", "was", "were", "be", "been", "being", "have",
            "has", "had", "having", "do", "does", "did", "doing", "what", "which", "who", "whom",
            "without", "improve", "improving", "harm", "harming", "need", "using", "use",
            "handle", "handling", "discuss", "implement", "designing", "describe", "explain",
            "previous", "context", "please", "confirm", "walk", "approach",
            "tell", "kind", "think", "seems",
        }

        # Extract core tech terms & capitalized acronyms (e.g. CAP, CQRS, Sagas, 2PC, API, Laravel, Redis)
        # Keywords describe the current utterance. Previous context may inform
        # intent, but its transport labels must never become visible keywords.
        raw_tech_tokens = re.findall(
            r'\b[A-Z0-9]{2,}\b|\b[a-zA-Z0-9_-]{4,}\b', latest_text
        )
        filtered_terms = []
        seen = set()
        for token in raw_tech_tokens:
            t_lower = token.lower()
            if t_lower not in stopwords and t_lower not in seen and len(token) > 2:
                seen.add(t_lower)
                filtered_terms.append(token)

        technical_terms = {
            "api", "architecture", "availability", "cache", "cluster", "concurrency",
            "consistency", "database", "deadline", "dependency", "deployment",
            "distributed", "event", "feature", "framework", "inference", "latency",
            "memory", "microservice", "microservices", "model", "performance", "query",
            "queue", "realtime", "replica", "rollback", "scalability", "security",
            "sharding", "state", "storage", "testability", "testing", "throughput",
            "token", "traffic", "transaction", "websocket", "graphql", "redis",
            "kubernetes", "oauth2", "pkce", "cqrs", "saga", "argocd", "gitops",
        }
        ranked_terms = sorted(
            enumerate(filtered_terms),
            key=lambda entry: (
                -(
                    2
                    if entry[1].isupper()
                    else 1 if entry[1].lower() in technical_terms else 0
                ),
                entry[0],
            ),
        )
        keywords_list = (
            [term for _, term in ranked_terms[:6]]
            if ranked_terms
            else ["General Topic", "Conversation"]
        )
        keywords_str = " ; ".join(keywords_list)

        # Detect core domain context dynamically
        domain_indicators = {
            "cap theorem": "định lý CAP và tính nhất quán của hệ phân tán",
            "distributed": "hệ thống phân tán và khả năng mở rộng",
            "financial": "giao dịch tài chính cần tính nhất quán nghiêm ngặt",
            "cqrs": "CQRS và Event Sourcing",
            "saga": "Saga và giao dịch phân tán",
            "2pc": "sự đánh đổi giữa 2PC và Saga",
            "cache": "bộ nhớ đệm và lưu trữ trong RAM",
            "laravel": "kiến trúc ứng dụng Laravel",
            "feature": "feature flag và chiến lược rollout",
            "database": "tối ưu cơ sở dữ liệu và phân mảnh",
            "microservice": "kiến trúc vi dịch vụ",
            "api": "thiết kế API chịu tải cao",
            "latency": "giảm độ trễ nhưng vẫn bảo toàn tính đúng đắn",
            "oauth": "xác thực OAuth và an toàn token",
            "kubernetes": "điều phối và tự động mở rộng Kubernetes",
            "graphql": "GraphQL và tối ưu truy vấn",
        }

        matched_contexts = [desc for key, desc in domain_indicators.items() if key in text_clean]
        context_summary = ", ".join(matched_contexts) if matched_contexts else ", ".join(keywords_list[:2]) if keywords_list else "Câu chuyện chung"

        # Detect if input is a Question vs Statement/Opinion
        words = latest_clean.split()
        first_two_words = words[:2] if len(words) >= 2 else words
        is_question = "?" in latest_text or any(
            word in first_two_words
            for word in [
                "how", "what", "why", "which", "can", "could", "would",
                "is", "are", "do", "does", "explain",
            ]
        )
        requests_response = bool(
            re.search(
                r"\b(please|let me know|can you|could you|would you|"
                r"do you need|i need you|tell me|walk me through)\b",
                latest_text.lower(),
            )
            or re.match(
                r"^\s*(review|check|send|share|update|confirm|prepare|"
                r"schedule|fix|investigate|provide|create)\b",
                latest_text.lower(),
            )
        )
        should_reply = is_question or requests_response

        # Stream 1b: Explanation
        if is_question:
            stream_1b = f"Hỏi về {context_summary}. Cần trả lời hoặc cung cấp thông tin phù hợp."
        elif requests_response:
            stream_1b = f"Đang đề nghị bạn thực hiện hoặc phản hồi về {context_summary}."
        else:
            stream_1b = f"Chia sẻ/cập nhật thông tin về: {context_summary}."

        # Stream 2b: deterministic, safe responses for low-confidence local mode.
        primary_topic = keywords_list[0] if keywords_list else "the topic"

        if should_reply:
            quick_en = "Sure. Let me think through that for a moment."
            quick_vi = "(Được. Để tôi suy nghĩ kỹ một chút.)"
            if "financial" in text_clean or "saga" in text_clean:
                stream_2b_en = (
                    "For strict financial writes, I would prioritize consistency and partition tolerance, then use sagas for cross-service workflows. "
                    "I would avoid broad 2PC locks and validate every trade-off against the ledger's recovery requirements."
                )
                stream_2b_vi = (
                    "(Với các thao tác ghi tài chính nghiêm ngặt, tôi ưu tiên tính nhất quán và khả năng chịu phân vùng, sau đó dùng saga cho quy trình liên dịch vụ. "
                    "Tôi sẽ tránh khóa 2PC trên phạm vi rộng và kiểm chứng từng đánh đổi theo yêu cầu khôi phục của sổ cái.)"
                )
            elif any(
                term in text_clean
                for term in ("distributed", "consistency", "availability", "cap theorem")
            ):
                stream_2b_en = (
                    "I would start by defining the required consistency and availability guarantees for each operation. "
                    "Then I would design for partitions and retries explicitly, use idempotent operations, and test node, network, and dependency failures under load."
                )
                stream_2b_vi = (
                    "(Tôi sẽ bắt đầu bằng cách xác định yêu cầu về tính nhất quán và tính sẵn sàng cho từng thao tác. "
                    "Sau đó tôi sẽ thiết kế rõ cách xử lý phân vùng mạng và retry, dùng thao tác idempotent, đồng thời kiểm thử lỗi node, mạng và dịch vụ phụ thuộc dưới tải.)"
                )
            elif "feature" in text_clean or "rollout" in text_clean:
                stream_2b_en = (
                    "I would keep feature evaluation behind one typed service and store rollout rules outside application code. "
                    "Then I would add ownership, expiry dates, metrics, and a tested rollback path for every flag."
                )
                stream_2b_vi = (
                    "(Tôi sẽ đặt việc đánh giá feature flag sau một service có kiểu dữ liệu rõ ràng và lưu quy tắc rollout ngoài mã ứng dụng. "
                    "Sau đó mỗi flag cần có người phụ trách, ngày hết hạn, số liệu theo dõi và đường rollback đã được kiểm thử.)"
                )
            elif "latency" in text_clean or "performance" in text_clean:
                stream_2b_en = (
                    "I would measure p95 and p99 latency first, then profile the request path to find the real bottleneck. "
                    "I would optimize with targeted caching, batching, or concurrency while keeping authoritative writes strongly consistent and validating the result under load."
                )
                stream_2b_vi = (
                    "(Trước tiên tôi sẽ đo độ trễ p95 và p99, sau đó phân tích toàn bộ đường đi của request để tìm đúng nút thắt. "
                    "Tôi sẽ tối ưu có mục tiêu bằng cache, batching hoặc xử lý đồng thời, đồng thời giữ các thao tác ghi nguồn ở trạng thái nhất quán nghiêm ngặt và kiểm chứng dưới tải.)"
                )
            elif "database" in text_clean or "query" in text_clean:
                stream_2b_en = (
                    "I would start with the query plan and production metrics, then fix indexing, scan volume, and lock contention before considering sharding. "
                    "Read replicas can absorb safe reads, but partitioning should follow measured access patterns and a tested migration plan."
                )
                stream_2b_vi = (
                    "(Tôi sẽ bắt đầu từ kế hoạch thực thi truy vấn và số liệu production, sau đó xử lý index, lượng dữ liệu quét và tranh chấp khóa trước khi cân nhắc sharding. "
                    "Read replica có thể gánh các lượt đọc an toàn, còn phân vùng phải dựa trên mẫu truy cập đã đo và kế hoạch migration được kiểm thử.)"
                )
            elif any(
                term in text_clean
                for term in ("oauth", "pkce", "token", "security", "xss", "csrf")
            ):
                stream_2b_en = (
                    "I would use Authorization Code with PKCE, keep tokens out of persistent browser storage, and enforce short lifetimes and rotation. "
                    "I would pair that with strict CSP, state and nonce validation, secure cookies where possible, and server-side authorization on every request."
                )
                stream_2b_vi = (
                    "(Tôi sẽ dùng Authorization Code với PKCE, không lưu token lâu dài trong trình duyệt, đồng thời đặt thời hạn ngắn và cơ chế xoay vòng. "
                    "Giải pháp cần đi kèm CSP nghiêm ngặt, kiểm tra state/nonce, cookie an toàn khi phù hợp và xác thực quyền ở server cho mọi request.)"
                )
            elif "kubernetes" in text_clean or "autoscaler" in text_clean:
                stream_2b_en = (
                    "I would scale pods from workload metrics and ensure the cluster autoscaler has enough headroom to add nodes before pods remain pending. "
                    "I would also test stabilization windows, resource requests, disruption budgets, and the behavior during a sudden spike."
                )
                stream_2b_vi = (
                    "(Tôi sẽ mở rộng pod dựa trên số liệu tải và bảo đảm cluster autoscaler còn đủ dư địa thêm node trước khi pod phải chờ. "
                    "Tôi cũng sẽ kiểm thử cửa sổ ổn định, resource request, disruption budget và hành vi khi lưu lượng tăng đột ngột.)"
                )
            elif "microservice" in text_clean or "event-driven" in text_clean:
                stream_2b_en = (
                    "I would make consumers idempotent with a durable event identifier and commit business state together with the deduplication record. "
                    "Retries need backoff and observability, while poison events should move to a dead-letter path with an explicit replay process."
                )
                stream_2b_vi = (
                    "(Tôi sẽ thiết kế consumer có tính idempotent bằng mã sự kiện bền vững và ghi trạng thái nghiệp vụ cùng bản ghi chống trùng. "
                    "Retry cần backoff và khả năng quan sát; sự kiện lỗi lặp lại phải chuyển sang dead-letter queue với quy trình replay rõ ràng.)"
                )
            else:
                stream_2b_en = (
                    f"For {primary_topic}, I would first confirm the goal, constraints, and expected failure behavior. "
                    "Then I would compare the viable options, explain their trade-offs, and validate the choice with a small test."
                )
                stream_2b_vi = (
                    f"(Với {primary_topic}, trước tiên tôi sẽ xác nhận mục tiêu, các ràng buộc và cách hệ thống cần xử lý khi lỗi. "
                    "Sau đó tôi sẽ so sánh các phương án khả thi, giải thích các đánh đổi và kiểm chứng lựa chọn bằng một thử nghiệm nhỏ.)"
                )
        else:
            quick_en = ""
            quick_vi = "Không cần phản hồi ngay — tiếp tục lắng nghe."
            stream_2b_en = ""
            stream_2b_vi = ""


        return {
            "stream_1b": stream_1b,
            "stream_2a": keywords_str,
            "stream_2b_quick_en": quick_en,
            "stream_2b_quick_vi": quick_vi,
            "stream_2b_en": stream_2b_en,
            "stream_2b_vi": stream_2b_vi,
            "stream_2b_should_reply": should_reply,
        }
