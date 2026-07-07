from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from core.llm_client import get_llm


class ContractAnalyzer:

    _METHOD_PATTERNS = {
        "수의계약": re.compile(r"수의계약"),
        "일반경쟁": re.compile(r"일반\s*경쟁|일반경쟁입찰"),
        "제한경쟁": re.compile(r"제한경쟁"),
        "지명경쟁": re.compile(r"지명경쟁"),
        "협상": re.compile(r"협상\s*에\s*의한\s*계약|협상"),
    }

    _SEMANTIC_SERVICE_TERMS = (
        "플랫폼 구축",
        "정보시스템 구축",
        "시스템 구축",
        "ai 챗봇 구축",
        "ai 구축",
        "시스템 개발",
        "웹사이트 개편",
        "모바일 앱 개발",
        "db 구축",
        "정보화사업",
        "운영",
        "유지관리",
        "유지보수",
        "연구",
        "교육",
    )

    _RISK_PATTERNS: dict[str, re.Pattern[str]] = {
        "분할계약": re.compile(r"분할\s*계약|쪼개기\s*계약"),
        "동일업체": re.compile(r"동일\s*업체|동일업체|특정\s*업체\s*반복"),
        "수의계약": re.compile(r"수의\s*계약|수의계약"),
        "협상": re.compile(r"협상\s*에\s*의한\s*계약|협상"),
        "제한경쟁": re.compile(r"제한\s*경쟁|제한경쟁"),
        "개인정보": re.compile(r"개인정보|주민등록번호|민감정보"),
        "AI": re.compile(r"\bAI\b|인공지능|챗봇|머신러닝|딥러닝", re.IGNORECASE),
        "유지보수": re.compile(r"유지\s*보수|유지보수|유지관리"),
    }

    _VENDOR_PATTERNS = [
        re.compile(r"(?P<name>[가-힣A-Za-z0-9&·\-]{2,}(?:\s+[가-힣A-Za-z0-9&·\-]{1,})?)\s*(?P<suffix>주식회사|㈜|\(주\))"),
        re.compile(r"(?P<prefix>주식회사|㈜|\(주\))\s*(?P<name>[가-힣A-Za-z0-9&·\-]{2,}(?:\s+[가-힣A-Za-z0-9&·\-]{1,})?)"),
        re.compile(r"(?P<name>[가-힣A-Za-z0-9&·\-]{2,}(?:\s+[가-힣A-Za-z0-9&·\-]{1,})?)\s*주식회사"),
    ]

    def analyze(self, text: str):

        cleaned_text = self._clean_text(text)
        llm_data = self._extract_with_llm(cleaned_text)

        result = {
            "contract_type": None,
            "vendor": None,
            "amount": None,
            "title": None,
            "business_name": None,
            "task_scope": None,
            "task_content": None,
            "risk_factors": [],
            "estimated": False,
            "contract_start": None,
            "contract_end": None,
            "contract_method": None,
            "period": {
                "start": None,
                "end": None,
            },
        }

        result["vendor"] = self._choose_text(llm_data.get("vendor"), self._extract_vendor(cleaned_text))
        result["amount"] = self._normalize_amount(llm_data.get("amount_text"), cleaned_text)
        result["contract_start"] = self._normalize_date(llm_data.get("contract_start"))
        result["contract_end"] = self._normalize_date(llm_data.get("contract_end"))

        if not result["contract_start"] or not result["contract_end"]:

            start, end = self._extract_period(cleaned_text)
            result["contract_start"] = result["contract_start"] or start
            result["contract_end"] = result["contract_end"] or end

        result["period"]["start"] = result["contract_start"]
        result["period"]["end"] = result["contract_end"]
        result["contract_method"] = self._choose_text(llm_data.get("contract_method"), self._extract_method(cleaned_text))
        result["business_name"] = self._choose_text(llm_data.get("business_name"), llm_data.get("title"))
        result["task_content"] = self._choose_text(llm_data.get("task_content"), llm_data.get("task_scope"))
        result["title"] = self._choose_text(result["business_name"], self._extract_title(cleaned_text, result))
        result["task_scope"] = self._choose_text(result["task_content"], self._infer_task_scope(cleaned_text))
        result["contract_type"] = self._normalize_contract_type(
            llm_data.get("contract_type"),
            cleaned_text,
            result.get("title"),
            result.get("task_scope"),
        )
        result["estimated"] = self._to_bool(llm_data.get("estimated")) or self._is_estimated(cleaned_text)
        result["risk_factors"] = self._merge_risk_factors(llm_data.get("risk_factors"), cleaned_text)

        return result

    def _extract_with_llm(self, text: str) -> dict[str, Any]:

        prompt = (
            "다음 계약 문장에서 항목을 의미적으로 추출하라.\n"
            "반드시 JSON 객체만 출력하고 다른 설명은 쓰지 마라.\n"
            "키는 아래를 정확히 사용하라:\n"
            "contract_type, vendor, amount_text, contract_start, contract_end, contract_method, title, task_scope, risk_factors, estimated\n"
            "규칙:\n"
            "1) contract_type은 용역/공사/물품 중 하나 또는 null\n"
            "2) 플랫폼 구축, 시스템 구축, AI 구축, 시스템 개발, 웹사이트 개편, 모바일 앱 개발, DB 구축, 운영, 유지관리, 연구, 교육은 용역으로 판단\n"
            "3) amount_text는 원문 금액 표현을 그대로 유지\n"
            "4) 날짜는 YYYY-MM-DD 형식 권장\n"
            "5) risk_factors는 문자열 배열\n"
            "문장:\n"
            f"{text}"
        )

        try:

            response = get_llm().invoke(prompt)
            content = str(getattr(response, "content", "")).strip()

        except Exception:

            return {}

        parsed = self._parse_json_object(content)

        if isinstance(parsed, dict):

            return parsed

        return {}

    def _parse_json_object(self, raw: str) -> dict[str, Any] | None:

        if not raw:

            return None

        candidate = raw.strip()

        fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", candidate)
        if fenced:
            candidate = fenced.group(1).strip()

        try:

            value = json.loads(candidate)
            if isinstance(value, dict):
                return value

        except Exception:

            pass

        brace = re.search(r"\{[\s\S]*\}", candidate)
        if not brace:
            return None

        try:

            value = json.loads(brace.group(0))
            if isinstance(value, dict):
                return value

        except Exception:

            return None

        return None

    def _clean_text(self, text: str) -> str:

        return re.sub(r"\s+", " ", str(text)).strip()

    def _extract_contract_type(self, text: str) -> str | None:

        for contract_type in ("용역", "물품", "공사"):

            if contract_type in text:

                return contract_type

        return None

    def _extract_vendor(self, text: str) -> str | None:

        matches: list[tuple[int, int, str]] = []

        for pattern in self._VENDOR_PATTERNS:

            for match in pattern.finditer(text):

                vendor = self._normalize_vendor(match)

                if vendor:

                    matches.append((match.start(), len(vendor), vendor))

        if not matches:

            return None

        matches.sort(key=lambda item: (item[0], -item[1]))

        return matches[0][2]

    def _normalize_vendor(self, match: re.Match[str]) -> str | None:

        group_dict = match.groupdict()

        suffix = group_dict.get("suffix")
        prefix = group_dict.get("prefix")
        name = (group_dict.get("name") or "").strip()

        if suffix:

            return self._clean_vendor_tail(f"{name} {suffix}")

        if prefix:

            return self._clean_vendor_tail(f"{prefix} {name}")

        if name:

            return self._clean_vendor_tail(f"{name} 주식회사")

        return None

    def _clean_vendor_tail(self, vendor: str) -> str:

        vendor = re.sub(r"\s+", " ", vendor).strip()
        vendor = vendor.replace("주식회사 주식회사", "주식회사")
        return vendor

    def _extract_amount(self, text: str) -> int | None:

        patterns = [
            (re.compile(r"([\d,]+)\s*억원"), 100000000),
            (re.compile(r"([\d,]+)\s*만원"), 10000),
            (re.compile(r"([\d,]+)\s*원"), 1),
        ]

        for pattern, multiplier in patterns:

            match = pattern.search(text)

            if match:

                value = int(match.group(1).replace(",", ""))

                return value * multiplier

        return None

    def _extract_period(self, text: str) -> tuple[str | None, str | None]:

        patterns = [
            re.compile(
                r"(?P<sy>\d{4})\s*[.\-/년]\s*(?P<sm>\d{1,2})\s*[.\-/월]\s*(?P<sd>\d{1,2})\s*일?\s*(?:부터|~|-|시작)\s*(?P<ey>\d{4})\s*[.\-/년]\s*(?P<em>\d{1,2})\s*[.\-/월]\s*(?P<ed>\d{1,2})\s*일?\s*(?:까지|종료|종료일까지|까지입니다|까지임)?"
            ),
            re.compile(
                r"(?P<sy>\d{4})\s*년\s*(?P<sm>\d{1,2})\s*월\s*(?P<sd>\d{1,2})\s*일\s*부터\s*(?P<ey>\d{4})\s*년\s*(?P<em>\d{1,2})\s*월\s*(?P<ed>\d{1,2})\s*일\s*까지"
            ),
        ]

        for pattern in patterns:

            match = pattern.search(text)

            if match:

                start = self._format_date(match.group("sy"), match.group("sm"), match.group("sd"))
                end = self._format_date(match.group("ey"), match.group("em"), match.group("ed"))

                return start, end

        return None, None

    def _format_date(self, year: str, month: str, day: str) -> str:

        return datetime(int(year), int(month), int(day)).strftime("%Y-%m-%d")

    def _extract_method(self, text: str) -> str | None:

        for method, pattern in self._METHOD_PATTERNS.items():

            if pattern.search(text):

                return method

        return None

    def _extract_title(self, text: str, result: dict[str, Any]) -> str | None:

        vendor = result.get("vendor") or ""
        contract_type = result.get("contract_type") or ""

        candidates = []

        title_patterns = [
            re.compile(r"([^.\n\r]{2,120}?(?:용역|공사|물품)\s*계약(?:서|을|에|으로|을 체결|을 체결하려고|을 체결합니다)?)(?:[.\n\r]|$)"),
            re.compile(r"([^.\n\r]{2,120}?(?:용역|공사|물품)\s*업무자동화[^.\n\r]{0,40}?계약(?:서|을|에|으로)?)(?:[.\n\r]|$)"),
        ]

        for pattern in title_patterns:

            for match in pattern.finditer(text):

                candidate = self._normalize_title(match.group(1), vendor, contract_type)

                if candidate:

                    candidates.append(candidate)

        if candidates:

            candidates.sort(key=lambda value: (len(value), value))

            return candidates[-1]

        fallback = self._title_from_sentence(text, vendor)

        if fallback:

            return fallback

        return None

    def _normalize_title(self, title: str, vendor: str, contract_type: str) -> str:

        title = self._clean_text(title)

        if vendor:

            title = title.replace(vendor, "")
            title = title.replace(vendor.replace("주식회사 ", ""), "")

        title = re.sub(r"^(?:와|과|및|그리고)\s+", "", title)
        title = re.sub(r"(을|를)?\s*체결하려고 합니다\.?$", "", title)
        title = re.sub(r"(을|를)?\s*체결합니다\.?$", "", title)
        title = re.sub(r"(을|를)?\s*체결하려 합니다\.?$", "", title)
        title = re.sub(r"(을|를)?\s*체결 예정입니다\.?$", "", title)

        if contract_type and contract_type not in title:

            title = f"{title} {contract_type}"

        title = re.sub(r"\s+", " ", title).strip(" ,.-")

        if "계약" not in title:

            title = f"{title} 계약".strip()

        return title

    def _title_from_sentence(self, text: str, vendor: str) -> str | None:

        sentences = [sentence.strip() for sentence in re.split(r"[.\n\r]", text) if sentence.strip()]

        for sentence in sentences:

            if "계약" in sentence and any(keyword in sentence for keyword in ("용역", "물품", "공사")):

                candidate = sentence

                if vendor:

                    candidate = candidate.replace(vendor, "")

                candidate = re.sub(r"^(?:와|과|및|그리고)\s+", "", candidate)
                candidate = re.sub(r"(을|를)?\s*체결하려고 합니다\.?$", "", candidate)
                candidate = re.sub(r"(을|를)?\s*체결합니다\.?$", "", candidate)
                candidate = re.sub(r"(을|를)?\s*체결하려 합니다\.?$", "", candidate)
                candidate = re.sub(r"(을|를)?\s*체결 예정입니다\.?$", "", candidate)
                candidate = re.sub(r"\s+", " ", candidate).strip(" ,.-")

                if candidate:

                    return candidate

        return None

    def _normalize_contract_type(self, llm_value: Any, text: str, title: Any, task_scope: Any) -> str | None:

        if isinstance(llm_value, str):

            candidate = llm_value.strip()
            if candidate in {"용역", "공사", "물품"}:
                return candidate

        semantic_source = " ".join(
            item for item in [text, str(title or ""), str(task_scope or "")] if item
        )

        lowered = semantic_source.lower()

        if any(term.lower() in lowered for term in self._SEMANTIC_SERVICE_TERMS):
            return "용역"

        heuristic = self._extract_contract_type(semantic_source)
        if heuristic:
            return heuristic

        if any(term in semantic_source for term in ("개발", "구축", "운영", "유지관리", "유지보수", "연구", "교육")):
            return "용역"

        return None

    def _normalize_amount(self, llm_amount_text: Any, text: str) -> int | None:

        candidates: list[str] = []

        if isinstance(llm_amount_text, (int, float)):
            return int(llm_amount_text)

        if isinstance(llm_amount_text, str) and llm_amount_text.strip():
            candidates.append(llm_amount_text.strip())

        amount_spans = re.findall(
            r"\d+(?:[\.,]\d+)?\s*억\s*\d*(?:\s*[천백십])?\s*만?\s*원?|\d+(?:,\d{3})+\s*원|\d+(?:\s*[천백십])\s*만\s*원|\d+\s*만\s*원",
            text,
        )
        candidates.extend(amount_spans)

        for candidate in candidates:

            parsed = self._parse_korean_currency(candidate)
            if parsed is not None:
                return parsed

        return self._extract_amount(text)

    def _parse_korean_currency(self, value: str) -> int | None:

        raw = value.strip()
        if not raw:
            return None

        normalized = raw.replace(",", "").replace(" ", "")
        normalized = normalized.replace("억원", "억").replace("만원", "만").replace("원", "")

        if re.fullmatch(r"\d+", normalized):
            return int(normalized)

        total = 0.0

        eok_match = re.search(r"(\d+(?:\.\d+)?)억", normalized)
        if eok_match:
            total += float(eok_match.group(1)) * 100000000
            normalized = normalized[eok_match.end():]

        man_match = re.search(r"(\d+(?:\.\d+)?)(천|백|십)?만", normalized)
        if man_match:
            number = float(man_match.group(1))
            unit = man_match.group(2)
            multiplier = {None: 1, "십": 10, "백": 100, "천": 1000}[unit]
            total += number * multiplier * 10000

        if total > 0:
            return int(total)

        return None

    def _infer_task_scope(self, text: str) -> str | None:

        sentences = [sentence.strip() for sentence in re.split(r"[.\n\r]", text) if sentence.strip()]

        for sentence in sentences:
            if any(keyword in sentence for keyword in ("구축", "개발", "운영", "유지관리", "유지보수", "연구", "교육", "개편")):
                return self._truncate(sentence, 140)

        return None

    def _merge_risk_factors(self, llm_factors: Any, text: str) -> list[str]:

        factors: list[str] = []

        if isinstance(llm_factors, list):
            for item in llm_factors:
                if isinstance(item, str) and item.strip():
                    factors.append(item.strip())

        for risk_name, pattern in self._RISK_PATTERNS.items():
            if pattern.search(text):
                factors.append(risk_name)

        if any(term in text for term in ("구축", "정보시스템", "플랫폼")):
            factors.append("정보시스템 구축")

        seen: set[str] = set()
        unique: list[str] = []

        for factor in factors:
            normalized = re.sub(r"\s+", " ", factor).strip()
            if not normalized:
                continue
            if normalized not in seen:
                seen.add(normalized)
                unique.append(normalized)

        return unique

    def _is_estimated(self, text: str) -> bool:

        return any(token in text for token in ("추정", "예상", "견적", "약 "))

    def _to_bool(self, value: Any) -> bool:

        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes", "y"}

        return False

    def _choose_text(self, preferred: Any, fallback: str | None) -> str | None:

        if isinstance(preferred, str) and preferred.strip():
            return preferred.strip()

        return fallback

    def _normalize_date(self, value: Any) -> str | None:

        if not isinstance(value, str) or not value.strip():
            return None

        text = value.strip()

        match = re.search(r"(\d{4})[-./년\s]+(\d{1,2})[-./월\s]+(\d{1,2})", text)
        if not match:
            return None

        try:
            return self._format_date(match.group(1), match.group(2), match.group(3))
        except Exception:
            return None

    def _truncate(self, text: str, limit: int) -> str:

        cleaned = self._clean_text(text)
        if len(cleaned) <= limit:
            return cleaned

        return cleaned[: limit - 1].rstrip() + "…"