from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from asktrainmind.app.config import AIConfig
from asktrainmind.app.excel_model import FunctionRecord


@dataclass
class AnalysisOutput:
    info_text: str
    differences_text: str
    banner: str | None = None


class LLMProvider(ABC):
    @abstractmethod
    def analyze(self, records: list[FunctionRecord]) -> AnalysisOutput:
        raise NotImplementedError


class NullProvider(LLMProvider):
    def analyze(self, records: list[FunctionRecord]) -> AnalysisOutput:
        configs: dict[str, list[str]] = {}
        for record in records:
            for doc in record.documents:
                for cfg, link in doc.config_links.items():
                    configs.setdefault(cfg, []).append(f"{record.id} / {doc.doc_id} -> {link}")

        info_lines = ["Sintesi deterministica (offline):"]
        for record in records:
            info_lines.append(f"- {record.id}: {record.funzione}")
            for doc in record.documents:
                info_lines.append(f"  - DOC {doc.doc_id}")
                for detail in doc.details:
                    vals = "; ".join(f"{k}: {v}" for k, v in detail.values.items())
                    info_lines.append(f"    - {detail.title}: {vals}")

        diff_lines = ["Differenze configurazioni (deterministiche):"]
        for cfg, items in sorted(configs.items()):
            diff_lines.append(f"- {cfg}: {len(items)} documenti")
        if not configs:
            diff_lines.append("- Nessun documento per configurazione disponibile")

        return AnalysisOutput(
            info_text="\n".join(info_lines),
            differences_text="\n".join(diff_lines),
            banner="AI provider non configurato — analisi deterministica mostrata.",
        )


class OpenAIProvider(LLMProvider):
    def __init__(self, config: AIConfig):
        self.config = config

    def analyze(self, records: list[FunctionRecord]) -> AnalysisOutput:
        from openai import OpenAI

        client = OpenAI(api_key=self.config.api_key)
        prompt = _prompt_from_records(records)
        completion = client.chat.completions.create(
            model=self.config.model or "gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        text = completion.choices[0].message.content or ""
        return AnalysisOutput(info_text=text, differences_text=text)


class AzureOpenAIProvider(LLMProvider):
    def __init__(self, config: AIConfig):
        self.config = config

    def analyze(self, records: list[FunctionRecord]) -> AnalysisOutput:
        from openai import AzureOpenAI

        client = AzureOpenAI(
            api_key=self.config.api_key,
            api_version="2024-10-01-preview",
            azure_endpoint=self.config.endpoint,
        )
        prompt = _prompt_from_records(records)
        completion = client.chat.completions.create(
            model=self.config.deployment or self.config.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        text = completion.choices[0].message.content or ""
        return AnalysisOutput(info_text=text, differences_text=text)


def _prompt_from_records(records: list[FunctionRecord]) -> str:
    lines = ["Genera due sezioni: INFO e DIFFERENZE."]
    for record in records:
        lines.append(f"ID {record.id} - {record.funzione}")
        for doc in record.documents:
            lines.append(f"DOC {doc.doc_id}")
            for detail in doc.details:
                lines.append(f"{detail.title}: {detail.values}")
    return "\n".join(lines)


class AnalysisEngine:
    def __init__(self, config: AIConfig):
        self.config = config

    def _build_provider(self) -> LLMProvider:
        provider = self.config.provider.lower().strip()
        if provider == "openai" and self.config.api_key:
            return OpenAIProvider(self.config)
        if provider == "azure" and self.config.api_key and self.config.endpoint:
            return AzureOpenAIProvider(self.config)
        return NullProvider()

    def analyze(self, records: list[FunctionRecord]) -> AnalysisOutput:
        provider = self._build_provider()
        try:
            return provider.analyze(records)
        except Exception:
            return NullProvider().analyze(records)
