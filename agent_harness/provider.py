import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ProviderError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class NineRouterClient:
    MAX_MODEL_RESPONSE = 1_048_576
    MAX_MODELS = 1_000

    def __init__(self, base_url: str, api_key: str, timeout=60, retries=2, opener=urlopen):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.retries = max(0, retries)
        self.opener = opener

    def chat(self, model, messages, tools=None, *, max_tokens=4096):
        payload = {"model": model, "messages": messages, "max_tokens": max_tokens}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        body = json.dumps(payload).encode()
        request = Request(self.base_url + "/chat/completions", data=body, headers={
            "Authorization": "Bearer " + self.api_key, "Content-Type": "application/json",
        }, method="POST")
        for attempt in range(self.retries + 1):
            try:
                with self.opener(request, timeout=self.timeout) as response:
                    data = json.loads(response.read())
                if not isinstance(data.get("choices"), list) or not data["choices"]:
                    raise ProviderError("Provider response did not contain choices")
                return data
            except HTTPError as exc:
                # Do not include response body or request headers; they can contain secrets.
                status = exc.code
                exc.close()
                if status not in (408, 429, 500, 502, 503, 504) or attempt >= self.retries:
                    raise ProviderError(self._http_message(status), status) from None
            except (TimeoutError, URLError, OSError) as exc:
                if attempt >= self.retries:
                    raise ProviderError("9Router request failed or timed out") from None
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise ProviderError("9Router returned invalid JSON") from None
            if attempt < self.retries:
                time.sleep(min(0.25 * (2 ** attempt), 2))

    def list_models(self):
        """Return distinct model IDs from the bounded OpenAI-compatible catalog."""
        request = Request(self.base_url + "/models", headers={
            "Authorization": "Bearer " + self.api_key,
            "Accept": "application/json",
        }, method="GET")
        for attempt in range(self.retries + 1):
            try:
                with self.opener(request, timeout=self.timeout) as response:
                    raw = response.read(self.MAX_MODEL_RESPONSE + 1)
                if len(raw) > self.MAX_MODEL_RESPONSE:
                    raise ProviderError("9Router model catalog exceeds the 1 MiB limit")
                data = json.loads(raw)
                if not isinstance(data, dict) or not isinstance(data.get("data"), list):
                    raise ProviderError("9Router returned an invalid model catalog")
                models = []
                seen = set()
                for item in data["data"]:
                    model_id = item.get("id") if isinstance(item, dict) else None
                    if not isinstance(model_id, str) or not model_id.strip() or len(model_id) > 512:
                        raise ProviderError("9Router returned an invalid model ID")
                    if model_id not in seen:
                        seen.add(model_id)
                        models.append(model_id)
                        if len(models) > self.MAX_MODELS:
                            raise ProviderError("9Router model catalog contains too many models")
                if not models:
                    raise ProviderError("9Router returned no models")
                return models
            except HTTPError as exc:
                status = exc.code
                exc.close()
                if status not in (408, 429, 500, 502, 503, 504) or attempt >= self.retries:
                    raise ProviderError(self._http_message(status), status) from None
            except (TimeoutError, URLError, OSError):
                if attempt >= self.retries:
                    raise ProviderError("9Router request failed or timed out") from None
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise ProviderError("9Router returned invalid model catalog JSON") from None
            if attempt < self.retries:
                time.sleep(min(0.25 * (2 ** attempt), 2))

    @staticmethod
    def _http_message(status):
        if status in (401, 403): return "9Router authentication failed; verify the configured API key"
        if status == 404: return "9Router endpoint or model was not found; verify the endpoint and model ID"
        if status == 429: return "9Router rate limit reached"
        return f"9Router returned HTTP {status}"
