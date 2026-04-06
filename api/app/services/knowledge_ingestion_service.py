from __future__ import annotations

import mimetypes
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qsl, urlparse, urlunparse, urlencode

import httpx

from app.config import get_settings
from app.repositories.document_repository import DocumentRepository, make_chunk_records, make_document_record
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.source_repository import SourceRepository
from app.schemas.knowledge import (
    KnowledgeCandidate,
    KnowledgeIngestRequest,
    KnowledgeIngestionRunResponse,
)
from app.schemas.source import SourceConfig, SourceCreateRequest
from app.utils import checksum_for_bytes, truncate_text, utc_now_iso


DISCOVERY_AGENT_ID = "support-agent"


@dataclass
class ExtractedWebDocument:
    url: str
    canonical_url: str
    title: str
    text: str
    preview: str
    mime_type: str
    extension: str
    file_size: int
    published_at: str | None
    language: str | None


class KnowledgeIngestionService:
    source_mode = "knowledge_ingestion"

    def __init__(
        self,
        *,
        discovery_client: "KnowledgeDiscoveryClient | None" = None,
        fetcher: "KnowledgeFetcher | None" = None,
        source_repository: Optional[SourceRepository] = None,
        document_repository: Optional[DocumentRepository] = None,
        knowledge_repository: Optional[KnowledgeRepository] = None,
    ) -> None:
        self.settings = get_settings()
        self.discovery_client = discovery_client or KnowledgeDiscoveryClient()
        self.fetcher = fetcher or KnowledgeFetcher()
        self.source_repository = source_repository or SourceRepository()
        self.document_repository = document_repository or DocumentRepository()
        self.knowledge_repository = knowledge_repository or KnowledgeRepository()

    def ingest(self, payload: KnowledgeIngestRequest) -> KnowledgeIngestionRunResponse:
        source, resolution = self._resolve_source(payload)
        run_id = self.knowledge_repository.create_run(
            source_id=source.id,
            topic=payload.topic,
            query=payload.query,
            agent_id=DISCOVERY_AGENT_ID,
            metadata={
                "domains": payload.domains,
                "keywords": payload.keywords,
                "must_include": payload.must_include,
                "must_exclude": payload.must_exclude,
                "business_type": payload.business_type,
                "auto_publish": payload.auto_publish,
                "source_resolution": resolution["source_resolution"],
                "created_source_id": resolution["created_source_id"],
                "merged_source_id": resolution["merged_source_id"],
            },
        )

        candidates = self._discover_candidates(payload)
        accepted_count = 0
        updated_count = 0
        rejected_count = 0

        for candidate in candidates:
            try:
                extracted = self.fetcher.fetch(candidate.url)
            except Exception as error:  # noqa: BLE001
                rejected_count += 1
                self.knowledge_repository.add_item(
                    run_id=run_id,
                    candidate_url=candidate.url,
                    normalized_url=_normalize_url(candidate.url),
                    title=candidate.title,
                    status="rejected",
                    reject_reason=f"抓取失敗：{error}",
                    document_id=None,
                    trust_score=None,
                    relevance_score=None,
                    duplicate_score=None,
                    checksum=None,
                    source_domain=candidate.source_domain,
                    metadata={"stage": "fetch"},
                )
                continue

            trust_score = _score_trust(extracted.canonical_url, candidate.source_name)
            relevance_score = _score_relevance(
                title=extracted.title or candidate.title,
                snippet=candidate.snippet,
                text=extracted.text,
                topic=payload.topic,
                query=payload.query,
                keywords=payload.keywords,
                must_include=payload.must_include,
                must_exclude=payload.must_exclude,
            )
            duplicate_score = self._duplicate_score(extracted.canonical_url, extracted.text)

            reject_reason = _reject_reason(
                trust_score=trust_score,
                relevance_score=relevance_score,
                duplicate_score=duplicate_score,
                text=extracted.text,
            )
            if reject_reason:
                rejected_count += 1
                self.knowledge_repository.add_item(
                    run_id=run_id,
                    candidate_url=candidate.url,
                    normalized_url=extracted.canonical_url,
                    title=extracted.title or candidate.title,
                    status="rejected",
                    reject_reason=reject_reason,
                    document_id=None,
                    trust_score=trust_score,
                    relevance_score=relevance_score,
                    duplicate_score=duplicate_score,
                    checksum=checksum_for_bytes(extracted.text.encode("utf-8")),
                    source_domain=_domain_for_url(extracted.canonical_url),
                    metadata={"published_at": extracted.published_at, "language": extracted.language},
                )
                continue

            document = self._build_document_record(
                source_id=source.id,
                payload=payload,
                candidate=candidate,
                extracted=extracted,
                trust_score=trust_score,
                relevance_score=relevance_score,
                duplicate_score=duplicate_score,
            )
            document_id, status = self.document_repository.upsert_knowledge_document(source.id, document)
            if status == "updated":
                updated_count += 1
            else:
                accepted_count += 1

            self.knowledge_repository.add_item(
                run_id=run_id,
                candidate_url=candidate.url,
                normalized_url=extracted.canonical_url,
                title=document["filename"],
                status=status,
                reject_reason=None,
                document_id=document_id,
                trust_score=trust_score,
                relevance_score=relevance_score,
                duplicate_score=duplicate_score,
                checksum=document["checksum"],
                source_domain=_domain_for_url(extracted.canonical_url),
                metadata=document["metadata"],
            )

        self.knowledge_repository.finish_run(
            run_id=run_id,
            status="completed",
            total_candidates=len(candidates),
            accepted_count=accepted_count,
            updated_count=updated_count,
            rejected_count=rejected_count,
            metadata={
                "source_id": source.id,
                "source_name": source.name,
                "source_resolution": resolution["source_resolution"],
                "created_source_id": resolution["created_source_id"],
                "merged_source_id": resolution["merged_source_id"],
            },
        )
        return self.knowledge_repository.list_runs(source_id=source.id, limit=1)[0]

    def list_runs(self, *, source_id: str | None = None, limit: int = 20) -> list[KnowledgeIngestionRunResponse]:
        return self.knowledge_repository.list_runs(source_id=source_id, limit=limit)

    def list_document_versions(self, document_id: str) -> list[dict[str, object]]:
        return self.document_repository.list_versions(document_id)

    def refresh_external_source(self, source_id: str) -> KnowledgeIngestionRunResponse:
        source = self.source_repository.get(source_id)
        urls = source.config.urls or source.config.extra.get("urls") or []
        if source.config.url:
            urls = [source.config.url, *urls]

        payload = KnowledgeIngestRequest(
            topic=source.name,
            query=str(source.config.extra.get("query") or source.name),
            source_id=source.id,
            source_name=source.name,
            source_type="url_list" if len(urls) > 1 else "web_page",
            urls=urls,
            domains=list(source.config.extra.get("domains") or []),
            keywords=list(source.config.extra.get("keywords") or []),
            must_include=list(source.config.extra.get("must_include") or []),
            must_exclude=list(source.config.extra.get("must_exclude") or []),
            business_type=source.config.extra.get("business_type"),
            limit=min(len(urls), self.settings.openclaw_knowledge_default_limit) or self.settings.openclaw_knowledge_default_limit,
        )
        return self.ingest(payload)

    def _resolve_source(self, payload: KnowledgeIngestRequest):
        if payload.source_id:
            source = self.source_repository.get(payload.source_id)
            return source, {
                "source_resolution": "explicit_source",
                "created_source_id": None,
                "merged_source_id": source.id,
            }

        merge_key = self._build_merge_key(payload)
        existing = self.source_repository.find_by_merge_key(merge_key)
        if existing is not None:
            source = self.source_repository.merge_extra_config(
                existing.id,
                source_name=payload.source_name or existing.name,
                url=payload.urls[0] if payload.urls else None,
                urls=payload.urls,
                extra_updates={
                    "merge_key": merge_key,
                    "topic": payload.topic,
                    "domains": self._resolve_domains(payload),
                    "keywords": payload.keywords,
                    "must_include": payload.must_include,
                    "must_exclude": payload.must_exclude,
                    "query": payload.query,
                    "business_type": payload.business_type,
                    "time_window_days": payload.time_window_days,
                    "created_from": "web_search",
                },
            )
            return source, {
                "source_resolution": "merged",
                "created_source_id": None,
                "merged_source_id": source.id,
            }

        urls = payload.urls[:]
        if payload.source_type == "web_page" and urls:
            primary_url = urls[0]
        else:
            primary_url = urls[0] if urls else None
        source_payload = SourceCreateRequest(
            name=payload.source_name or f"Knowledge: {payload.topic}",
            type=payload.source_type,
            config=SourceConfig(
                url=primary_url,
                urls=urls,
                extra={
                    "merge_key": merge_key,
                    "topic": payload.topic,
                    "domains": self._resolve_domains(payload),
                    "keywords": payload.keywords,
                    "must_include": payload.must_include,
                    "must_exclude": payload.must_exclude,
                    "query": payload.query,
                    "business_type": payload.business_type,
                    "time_window_days": payload.time_window_days,
                    "created_from": "web_search",
                },
            ),
            role_hint="member",
        )
        source = self.source_repository.create(source_payload)
        return source, {
            "source_resolution": "created",
            "created_source_id": source.id,
            "merged_source_id": None,
        }

    def _resolve_domains(self, payload: KnowledgeIngestRequest) -> list[str]:
        resolved = [str(domain).strip().lower() for domain in payload.domains if str(domain).strip()]
        if not resolved:
            for url in payload.urls:
                domain = _domain_for_url(url)
                if domain and domain not in resolved:
                    resolved.append(domain)
        return resolved

    def _build_merge_key(self, payload: KnowledgeIngestRequest) -> str:
        normalized_topic = re.sub(r"\s+", " ", payload.topic.strip().lower())
        domains = sorted(self._resolve_domains(payload))
        return f"{payload.source_type}|{normalized_topic}|{'|'.join(domains)}"

    def _discover_candidates(self, payload: KnowledgeIngestRequest) -> list[KnowledgeCandidate]:
        if payload.urls:
            return [
                KnowledgeCandidate(
                    title=_filename_for_url(url),
                    url=url,
                    source_name=_domain_for_url(url),
                    source_domain=_domain_for_url(url),
                    reason="使用者或 support-agent 指定 URL 候選。",
                )
                for url in payload.urls[: payload.limit]
            ]

        return self.discovery_client.search(
            topic=payload.topic,
            query=payload.query,
            keywords=payload.keywords,
            domains=payload.domains,
            must_include=payload.must_include,
            must_exclude=payload.must_exclude,
            time_window_days=payload.time_window_days,
            limit=payload.limit,
        )

    def _duplicate_score(self, canonical_url: str, text: str) -> float:
        normalized_text = text[:5000].strip()
        checksum = checksum_for_bytes(normalized_text.encode("utf-8"))
        existing = self.document_repository.find_existing_document(
            canonical_url=canonical_url,
            checksum=checksum,
        )
        if existing is None:
            return 0.0
        return 1.0 if existing["checksum"] == checksum else 0.75

    def _build_document_record(
        self,
        *,
        source_id: str,
        payload: KnowledgeIngestRequest,
        candidate: KnowledgeCandidate,
        extracted: ExtractedWebDocument,
        trust_score: float,
        relevance_score: float,
        duplicate_score: float,
    ) -> dict[str, object]:
        checksum = checksum_for_bytes(extracted.text.encode("utf-8"))
        topic_tags = _topic_tags(payload.topic, payload.keywords, extracted.title, extracted.text)
        credibility_tier = _credibility_tier(trust_score)
        tags = [{"tag_type": "topic", "tag_value": tag} for tag in topic_tags]
        tags.extend(
            [
                {"tag_type": "domain", "tag_value": _domain_for_url(extracted.canonical_url)},
                {"tag_type": "format", "tag_value": extracted.extension},
                {"tag_type": "business_type", "tag_value": payload.business_type or _business_type_from_text(extracted.text, payload.topic)},
            ]
        )

        metadata = {
            "source_name": candidate.source_name,
            "source_domain": _domain_for_url(extracted.canonical_url),
            "source_type": _classify_source_type(candidate.source_name, extracted.canonical_url),
            "format_type": extracted.extension,
            "language": extracted.language,
            "credibility_tier": credibility_tier,
            "topic_tags": topic_tags,
            "time_bucket": _time_bucket(extracted.published_at),
            "duplicate_score": duplicate_score,
        }
        business_type = payload.business_type or _business_type_from_text(extracted.text, payload.topic)
        now = utc_now_iso()
        return make_document_record(
            source_id=source_id,
            relative_path=_relative_path_for_url(extracted.canonical_url),
            filename=_best_title(extracted.title, candidate.title),
            extension=extracted.extension,
            mime_type=extracted.mime_type,
            file_size=extracted.file_size,
            checksum=checksum,
            modified_at=extracted.published_at or now,
            content_preview=extracted.preview,
            extracted_text=extracted.text,
            chunks=make_chunk_records(extracted.text),
            document_kind="external_web",
            source_url=candidate.url,
            canonical_url=extracted.canonical_url,
            published_at=extracted.published_at,
            language=extracted.language,
            status="active",
            trust_score=trust_score,
            relevance_score=relevance_score,
            duplicate_group_id=_domain_for_url(extracted.canonical_url),
            business_type=business_type,
            metadata=metadata,
            first_seen_at=now,
            last_seen_at=now,
            last_checked_at=now,
            tags=_dedupe_tags(tags),
        )


class KnowledgeDiscoveryClient:
    SEARCH_URL = "https://html.duckduckgo.com/html/"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(
            timeout=get_settings().openclaw_knowledge_discovery_timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": "OpenClaw-Smart-Office/0.1"},
        )

    def search(
        self,
        *,
        topic: str,
        query: str,
        keywords: list[str],
        domains: list[str],
        must_include: list[str],
        must_exclude: list[str],
        time_window_days: int | None,
        limit: int,
    ) -> list[KnowledgeCandidate]:
        final_query = _build_discovery_query(topic, query, keywords, domains, must_include, must_exclude, time_window_days)
        response = self.client.post(self.SEARCH_URL, data={"q": final_query})
        response.raise_for_status()
        parser = _DuckDuckGoHtmlParser(limit=limit)
        parser.feed(response.text)
        return parser.results


class KnowledgeFetcher:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(
            timeout=get_settings().openclaw_knowledge_fetch_timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": "OpenClaw-Smart-Office/0.1"},
        )

    def fetch(self, url: str) -> ExtractedWebDocument:
        response = self.client.get(url)
        response.raise_for_status()
        payload = response.content
        content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
        resolved_url = str(response.url)
        canonical_url = _normalize_url(_extract_canonical_url(response.text) or resolved_url)
        extension = _detect_extension(resolved_url, content_type)

        if extension == "pdf":
            from app.parsers.file_parser import FileParser

            parsed = FileParser().parse(Path("download.pdf"), payload)
            text = parsed.text
            title = _best_title(_filename_for_url(resolved_url), _filename_for_url(resolved_url))
            mime_type = parsed.mime_type
        elif extension in {"html", "htm"} or content_type in {"text/html", ""}:
            title = _extract_html_title(response.text) or _filename_for_url(resolved_url)
            text = _extract_text_from_html(response.text)
            mime_type = "text/html"
            extension = "html"
        else:
            text = payload.decode("utf-8", errors="replace")
            title = _filename_for_url(resolved_url)
            mime_type = content_type or "text/plain"
            extension = extension or "txt"

        normalized_text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        return ExtractedWebDocument(
            url=resolved_url,
            canonical_url=canonical_url,
            title=title,
            text=normalized_text,
            preview=normalized_text[:320],
            mime_type=mime_type,
            extension=extension,
            file_size=len(payload),
            published_at=_extract_published_at(response.text),
            language=_detect_language(normalized_text),
        )


class _DuckDuckGoHtmlParser(HTMLParser):
    def __init__(self, *, limit: int) -> None:
        super().__init__()
        self.limit = limit
        self.results: list[KnowledgeCandidate] = []
        self._inside_title = False
        self._inside_snippet = False
        self._current_title: list[str] = []
        self._current_snippet: list[str] = []
        self._current_url: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        class_name = attr_map.get("class", "") or ""
        if tag == "a" and "result__a" in class_name and len(self.results) < self.limit:
            self._inside_title = True
            self._current_title = []
            href = attr_map.get("href") or ""
            self._current_url = href
        elif tag == "a" and "result__snippet" in class_name and len(self.results) < self.limit:
            self._inside_snippet = True
            self._current_snippet = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._inside_title:
            self._inside_title = False
        elif tag == "a" and self._inside_snippet:
            self._inside_snippet = False
            if self._current_url and self._current_title:
                url = _duckduckgo_result_url(self._current_url)
                title = unescape("".join(self._current_title)).strip()
                snippet = unescape("".join(self._current_snippet)).strip()
                self.results.append(
                    KnowledgeCandidate(
                        title=title or _filename_for_url(url),
                        url=url,
                        snippet=snippet,
                        source_name=_domain_for_url(url),
                        source_domain=_domain_for_url(url),
                        reason="由外網搜尋候選來源命中。",
                    )
                )
                self._current_url = None
                self._current_title = []
                self._current_snippet = []

    def handle_data(self, data: str) -> None:
        if self._inside_title:
            self._current_title.append(data)
        elif self._inside_snippet:
            self._current_snippet.append(data)


def _build_discovery_query(
    topic: str,
    query: str,
    keywords: list[str],
    domains: list[str],
    must_include: list[str],
    must_exclude: list[str],
    time_window_days: int | None,
) -> str:
    tokens = [query.strip() or topic.strip(), *keywords]
    tokens.extend(f'"{item}"' for item in must_include if item.strip())
    tokens.extend(f"-{item}" for item in must_exclude if item.strip())
    tokens.extend(f"site:{domain}" for domain in domains if domain.strip())
    if time_window_days:
        tokens.append(f"after:{(datetime.now(timezone.utc) - timedelta(days=time_window_days)).date().isoformat()}")
    return " ".join(item for item in tokens if item).strip()


def _extract_text_from_html(html: str) -> str:
    cleaned = re.sub(r"(?is)<(script|style).*?>.*?</\\1>", " ", html)
    cleaned = re.sub(r"(?is)<br\\s*/?>", "\n", cleaned)
    cleaned = re.sub(r"(?is)</p>", "\n", cleaned)
    cleaned = re.sub(r"(?is)<[^>]+>", " ", cleaned)
    cleaned = unescape(cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    return cleaned


def _extract_html_title(html: str) -> str | None:
    match = re.search(r"(?is)<title>(.*?)</title>", html)
    if not match:
        return None
    return unescape(match.group(1)).strip()


def _extract_canonical_url(html: str) -> str | None:
    match = re.search(r'(?is)<link[^>]+rel=["\\\']canonical["\\\'][^>]+href=["\\\'](.*?)["\\\']', html)
    return match.group(1).strip() if match else None


def _extract_published_at(html: str) -> str | None:
    patterns = [
        r'(?is)<meta[^>]+property=["\\\']article:published_time["\\\'][^>]+content=["\\\'](.*?)["\\\']',
        r'(?is)<meta[^>]+name=["\\\']pubdate["\\\'][^>]+content=["\\\'](.*?)["\\\']',
        r'(?is)<time[^>]+datetime=["\\\'](.*?)["\\\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            return match.group(1).strip()
    return None


def _normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if not k.lower().startswith("utm_")]
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, "", urlencode(query), ""))


def _duckduckgo_result_url(url: str) -> str:
    if url.startswith("//"):
        return f"https:{url}"
    return url


def _detect_extension(url: str, content_type: str) -> str:
    path = urlparse(url).path
    extension = Path(path).suffix.lower().lstrip(".")
    if extension:
        return extension
    guessed = mimetypes.guess_extension(content_type or "")
    return (guessed or ".txt").lstrip(".")


def _filename_for_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    if not path:
        return _domain_for_url(url)
    return Path(path).name or _domain_for_url(url)


def _relative_path_for_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.strip("/") or "index"
    return f"{parsed.netloc}/{path}"


def _domain_for_url(url: str) -> str:
    return urlparse(url).netloc.lower()


def _best_title(primary: str, fallback: str) -> str:
    return truncate_text(primary.strip() or fallback.strip() or "untitled")


def _score_trust(url: str, source_name: str) -> float:
    domain = _domain_for_url(url)
    if any(token in domain for token in ["gov", "edu", "openai.com", "anthropic.com", "microsoft.com", "google.com", "docs."]):
        return 0.95
    if any(token in domain for token in ["reuters", "bloomberg", "cnbc", "wsj", "arstechnica"]):
        return 0.85
    if "official" in source_name.lower():
        return 0.85
    if domain:
        return 0.65
    return 0.35


def _score_relevance(
    *,
    title: str,
    snippet: str,
    text: str,
    topic: str,
    query: str,
    keywords: list[str],
    must_include: list[str],
    must_exclude: list[str],
) -> float:
    haystack = " ".join([title, snippet, text[:4000]]).lower()
    score = 0.0
    for token in [topic, query, *keywords]:
        normalized = token.strip().lower()
        if not normalized:
            continue
        if normalized in haystack:
            score += 0.2
            continue
        parts = [part for part in re.split(r"[\s/_-]+", normalized) if len(part) >= 2]
        matched_parts = sum(1 for part in parts if part in haystack)
        if parts and matched_parts:
            score += min(0.18, 0.08 * matched_parts)
    for token in must_include:
        if token.strip().lower() in haystack:
            score += 0.1
    for token in must_exclude:
        if token.strip().lower() in haystack:
            score -= 0.3
    return max(0.0, min(score, 1.0))


def _reject_reason(*, trust_score: float, relevance_score: float, duplicate_score: float, text: str) -> str | None:
    if len(text.strip()) < 160:
        return "內容太短或提取結果不足，不適合入庫。"
    if trust_score < 0.55:
        return "來源可信度偏低。"
    if relevance_score < 0.2:
        return "與目標主題相關性不足。"
    if duplicate_score >= 1.0:
        return "與既有知識內容完全重複。"
    return None


def _topic_tags(topic: str, keywords: list[str], title: str, text: str) -> list[str]:
    tokens = [topic, *keywords]
    haystack = f"{title} {text[:1200]}".lower()
    tags: list[str] = []
    if topic.strip():
        tags.append(topic.strip())
    tags.extend(item.strip() for item in keywords if item.strip() and item.strip().lower() in haystack)
    if len(tags) == 0 and topic.strip():
        tags.append(topic.strip())
    return list(dict.fromkeys(tags))


def _classify_source_type(source_name: str, url: str) -> str:
    domain = _domain_for_url(url)
    if any(token in domain for token in ["docs.", "openai.com", "anthropic.com", "microsoft.com", "google.com"]):
        return "official"
    if any(token in domain for token in ["reuters", "bloomberg", "cnbc", "arstechnica", "wsj"]):
        return "mainstream_media"
    if "blog" in domain:
        return "vendor_blog"
    if any(token in domain for token in ["reddit", "x.com", "twitter", "discord"]):
        return "social"
    if source_name:
        return "community"
    return "unknown"


def _credibility_tier(score: float) -> str:
    if score >= 0.85:
        return "high"
    if score >= 0.6:
        return "medium"
    return "low"


def _business_type_from_text(text: str, topic: str) -> str:
    haystack = f"{topic} {text[:1000]}".lower()
    mappings = {
        "support": ["support", "customer", "ticket", "客服"],
        "product": ["product", "roadmap", "feature", "功能"],
        "engineering": ["engineering", "api", "sdk", "framework", "程式", "開發"],
        "compliance": ["policy", "law", "regulation", "合規", "法遵"],
        "operations": ["ops", "operation", "workflow", "流程", "維運"],
        "market": ["market", "industry", "競爭", "市場"],
        "finance": ["finance", "pricing", "funding", "財務"],
        "security": ["security", "cve", "漏洞", "攻擊"],
    }
    for business_type, tokens in mappings.items():
        if any(token in haystack for token in tokens):
            return business_type
    return "operations"


def _time_bucket(published_at: str | None) -> str:
    if not published_at:
        return "recent"
    try:
        published = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except ValueError:
        return "recent"
    delta = datetime.now(timezone.utc) - published.astimezone(timezone.utc)
    if delta.days <= 1:
        return "breaking"
    if delta.days <= 30:
        return "recent"
    return "archived"


def _detect_language(text: str) -> str:
    if not text:
        return "unknown"
    cjk_count = sum(1 for char in text[:1000] if "\u4e00" <= char <= "\u9fff")
    if cjk_count > 40:
        return "zh"
    return "en"


def _dedupe_tags(tags: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, str]] = []
    for tag in tags:
        pair = (tag["tag_type"], tag["tag_value"])
        if pair in seen or not tag["tag_value"]:
            continue
        seen.add(pair)
        deduped.append(tag)
    return deduped
